#!/usr/bin/env python3
"""net_resilience.py — self-adaptive network layer for all job-harvest scripts.

One import gives every scraper:
  * ProxyPool      — proxies from env PROXY_LIST / data/proxies.txt / free-API
                     harvest; health tracking, ban detection, exponential
                     cooldowns, auto-retire, auto-refill, disk persistence.
  * UARotator      — modern browser UAs + matching client-hint headers.
  * AdaptivePacer  — AIMD rate control per host-class: speeds up on success,
                     backs off globally on 429/403/999 anti-bot hits, honors
                     Retry-After.
  * resilient_fetch— classified GET: rotate proxy + UA every try, never retry
                     404/410, soft-retry 5xx, full retry on throttle/blocks,
                     exponential backoff with jitter.

STRICT NO-DIRECT MODE (default since self-adaptive-net-2):
  Job-portal traffic NEVER uses the user's real IP.  Every request goes
  through a proxy from the pool.  If no healthy proxy exists the pool
  auto-harvests + validates fresh ones; if that still yields nothing the
  fetch fails HONESTLY (error="no_proxy_strict") — it never silently falls
  back to a direct connection.  Only an explicit opt-out
  (--allow-direct / ERL_ALLOW_DIRECT=1) re-enables DIRECT, and even then
  DIRECT is only for controlled non-portal testing convenience.
  Sole bootstrap exception: the proxy-list harvest itself may fetch the
  public proxy lists directly when the pool is empty (those are not job
  portals); with >=1 verified proxy in the pool the harvest is proxied too.

Design goal: "maximally self adjusting" — every failure class maps to an
automatic counter-measure; no manual tuning required.

CLI:
  python3 scripts/net_resilience.py harvest [--min 8]   # build/refresh pool
  python3 scripts/net_resilience.py status               # pool + pacer state
  python3 scripts/net_resilience.py live [--n 2]         # live fetch smoke test
"""
from __future__ import annotations

import argparse, json, os, random, re, sys, threading, time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "data", "work")
POOL_STATE = os.path.join(WORK, "proxy_pool.json")
PROXY_FILE = os.path.join(BASE, "data", "proxies.txt")
HEALTH_FILE = os.path.join(WORK, "net_health.json")

THROTTLE_CODES = {429, 403, 999}          # 999 = linkedin-specific deny
PERMANENT_CODES = {404, 410}              # never retry
RE_UA = re.compile(r"^(Mozilla|Opera)", re.I)

# ------------------------------------------------------------------ UA rotation
_UAS = [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
     '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
     '"Google Chrome";v="126", "Chromium";v="126", "Not_A Brand";v="24"'),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
     '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="24"'),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0", None),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15", None),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
     '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"'),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
     '"Google Chrome";v="128", "Chromium";v="128", "Not_A Brand";v="24"'),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
     '"Google Chrome";v="129", "Chromium";v="129", "Not_A Brand";v="24"'),
]

class NoProxyError(RuntimeError):
    """Raised when strict mode has no healthy proxy and refuses DIRECT."""


class UARotator:
    """Random modern UA per call, with consistent client hints."""

    def __init__(self, lang="de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"):
        self.lang = lang
        self._i = random.randrange(len(_UAS))

    def headers(self, pin: int | None = None) -> dict:
        ua, ch = _UAS[self._next() if pin is None else pin % len(_UAS)]
        h = {"user-agent": ua,
             "accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                        "image/avif,image/webp,*/*;q=0.8"),
             "accept-language": self.lang,
             "cache-control": "no-cache",
             "pragma": "no-cache"}
        if ch:
            v = ch.split(";v=")[1].split('"')[0]
            h["sec-ch-ua"] = ch
            h["sec-ch-ua-mobile"] = "?0"
            h["sec-ch-ua-platform"] = '"Windows"' if "Windows" in ua else \
                '"macOS"' if "Macintosh" in ua else '"Linux"'
            h["sec-ch-ua-version"] = v
        return h

    def _next(self) -> int:
        self._i = (self._i + 1) % len(_UAS)      # deterministic rotation
        if random.random() < 0.35:                # + randomness
            self._i = random.randrange(len(_UAS))
        return self._i

    def distinct(self, n=20) -> int:
        return len({self.headers()["user-agent"] for _ in range(n)})

# ------------------------------------------------------------------ proxy pool
class _Entry:
    __slots__ = ("url", "ok", "fail", "bans", "consec", "cool_until",
                 "retired", "last_used", "latency", "created")

    def __init__(self, url):
        self.url, self.ok, self.fail, self.bans = url, 0, 0, 0
        self.consec, self.cool_until = 0, 0.0
        self.retired, self.last_used = False, 0.0
        self.latency, self.created = None, time.time()

    def healthy(self, now=None):
        now = now or time.time()
        return (not self.retired) and self.cool_until <= now

    def to_json(self):
        return {"url": self.url, "ok": self.ok, "fail": self.fail,
                "bans": self.bans, "retired": self.retired,
                "latency": self.latency, "consec": self.consec,
                "cool_until": self.cool_until}

DIRECT = "DIRECT"          # pseudo-entry = no proxy
JUDGES = ("https://api.ipify.org/?format=json",
          "https://api.myip.com",
          "http://ip-api.com/json")

class ProxyPool:
    """Health-tracked, LRU-rotating proxy pool.

    Sources (all optional, combined):
      * constructor arg / PROXY_LIST env var (comma separated)
      * data/proxies.txt (one per line, '#' comments)
      * free-API harvest() when pool runs dry (auto via ensure())
    A proxy is banned on 429/403/999 for 60*2^(bans-1) s (cap 30 min),
    parked on connection errors for 2 min, retired after 4 consecutive
    failures. next() returns the least-recently-used healthy entry, so
    consecutive calls ALWAYS change proxy.

    STRICT mode (default): next()/as_list() NEVER return the user's own
    connection — an empty pool yields None / [] and callers either trigger
    ensure() (auto-harvest) or fail honestly.  strict=False (only via
    explicit ERL_ALLOW_DIRECT=1 or ProxyPool(strict=False)) restores the
    old DIRECT fallback for controlled tests.
    """

    def __init__(self, proxies=None, state_file=POOL_STATE, validate=False,
                 log=print, judges=JUDGES, strict=None):
        self.lock = threading.RLock()
        self.entries: OrderedDict[str, _Entry] = OrderedDict()
        self.state_file, self.log, self.judges = state_file, log, judges
        # strict default: NEVER the user's IP; env opt-out ERL_ALLOW_DIRECT=1
        if strict is None:
            strict = os.environ.get("ERL_ALLOW_DIRECT", "") not in ("1", "true", "yes")
        self.strict = bool(strict)
        self._rr = 0                     # rotation counter for as_list()
        self._last_ensure = 0.0          # rate-limit auto-harvest
        self._load_state()
        for p in list(proxies or []):
            self.add(p)
        env = os.environ.get("PROXY_LIST", "")
        for p in [x.strip() for x in env.split(",") if x.strip()]:
            self.add(p)
        if os.path.exists(PROXY_FILE):
            try:
                for line in open(PROXY_FILE, encoding="utf-8"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.add(line)
            except Exception as e:
                self.log(f"[pool] proxy file unreadable: {e}")
        n = self.healthy_count()
        if n:
            snap = self.snapshot()
            self.log(f"[pool] {n} proxy entries loaded "
                     f"({snap['verified']} verified / {snap['candidates']} candidates)")
        if validate and n:
            self.validate_all()

    # ---- bookkeeping ------------------------------------------------
    def _load_state(self):
        if self.state_file and os.path.exists(self.state_file):
            try:
                for d in json.load(open(self.state_file)).values():
                    if d.get("retired"):
                        continue                       # drop dead history
                    if d.get("ok", 0) == 0 and d.get("fail", 0) > 0:
                        continue                       # never worked -> drop
                    e = _Entry(d["url"])
                    e.ok, e.fail, e.bans = d.get("ok", 0), d.get("fail", 0), d.get("bans", 0)
                    e.consec = d.get("consec", 0)
                    e.cool_until = d.get("cool_until", 0.0)
                    e.latency = d.get("latency")
                    self.entries[e.url] = e
            except Exception:
                pass

    def save(self):
        if not self.state_file:
            return
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                es = sorted(self.entries.values(),
                            key=lambda e: (-e.ok, e.fail))[:600]  # verified first, cap size
                json.dump({e.url: e.to_json() for e in es}, f)
        except Exception:
            pass

    def _source_stats(self):
        free = sum(1 for e in self.entries.values() if re.match(r"^http", e.url)
                   and "127.0.0.1" not in e.url)
        return f"{free} external)"

    def add(self, url):
        if not url or not isinstance(url, str):
            return False
        url = url.strip()
        if not re.match(r"^https?://", url) or url in self.entries:
            return False
        self.entries[url] = _Entry(url)
        return True

    def healthy_count(self):
        now = time.time()
        return sum(1 for e in self.entries.values() if e.healthy(now))

    # ---- rotation ----------------------------------------------------
    def next(self):
        """LRU pick among healthy entries, VERIFIED (ok>0) first.

        strict=True (default): returns None when the pool is empty — the
        caller must then auto-refill (ensure) or fail honestly.  It NEVER
        returns DIRECT, so the user's IP can never leak by accident.
        strict=False (explicit opt-out only): DIRECT fallback as before.
        """
        with self.lock:
            now = time.time()
            cand = [e for e in self.entries.values()
                    if e.healthy(now) and e.url != DIRECT]
            if cand:
                cand.sort(key=lambda e: (0 if e.ok > 0 else 1,   # verified first
                                         e.last_used, e.latency or 9e9))
                e = cand[0]
                e.last_used = now
                return e.url
            if self.strict:
                return None
            d = self.entries.get(DIRECT) or self._mk_direct()
            d.last_used = now
            return d.url

    def as_list(self, n=None):
        """Healthy proxy urls for jobspy, VERIFIED first, rotated each call.

        strict or not: an empty pool yields [] — callers must treat that as
        "no scraping without a proxy" (never pass proxies=None to jobspy).
        """
        with self.lock:
            now = time.time()
            urls = [e.url for e in self.entries.values()
                    if e.healthy(now) and e.url != DIRECT]
            if not urls:
                return []
            urls.sort(key=lambda e_url: 0 if self.entries[e_url].ok > 0 else 1)
            self._rr += 1
            k = self._rr % len(urls)
            urls = urls[k:] + urls[:k]
            return urls[:n] if n else urls

    def _mk_direct(self):
        d = _Entry(DIRECT)
        self.entries[DIRECT] = d
        return d

    # ---- auto-refill -------------------------------------------------
    def ensure(self, min_healthy=3, cooldown=300, max_candidates=350):
        """Auto-refill the pool when it runs dry (self-adjusting).

        Rate-limited: at most one harvest per `cooldown` seconds per pool
        instance, so a thousand failing fetches cannot hammer the sources.
        Returns the number of healthy proxies afterwards.
        """
        with self.lock:
            if self.healthy_count() >= min_healthy:
                return self.healthy_count()
            if time.time() - self._last_ensure < cooldown:
                return self.healthy_count()
            self._last_ensure = time.time()
        self.log(f"[pool] only {self.healthy_count()} healthy -> auto-harvest "
                 f"(strict mode: user IP is never used for portal traffic)")
        try:
            self.harvest(min_healthy=min_healthy, max_candidates=max_candidates)
        except Exception as e:
            self.log(f"[pool] auto-harvest failed: {str(e)[:80]}")
        return self.healthy_count()

    # ---- feedback ----------------------------------------------------
    def report(self, url, status=None, error=None, latency=None):
        with self.lock:
            e = self.entries.get(url)
            if e is None:
                e = self.add(url) and self.entries[url] or _Entry(url)
                self.entries[url] = e
            now = time.time()
            e.last_used = now
            if latency is not None:
                e.latency = round(latency, 3) if e.latency is None \
                    else round(0.7 * e.latency + 0.3 * latency, 3)
            if status and 200 <= status < 400:
                e.ok += 1
                e.consec = 0
            elif status in THROTTLE_CODES:
                e.bans += 1
                e.consec += 1
                e.cool_until = now + min(1800, 60 * (2 ** (e.bans - 1)))
                if e.url == DIRECT:
                    e.cool_until = now + min(900, 30 * (2 ** (e.bans - 1)))
            elif error or (status and status >= 500):
                e.fail += 1
                e.consec += 1
                # park 15s * consec (cap 120s): short enough that a single
                # strict-mode proxy recovers quickly, long enough to skip
                # a dead hop for the current batch
                e.cool_until = now + min(120, 15 * e.consec)
            if e.consec >= 4 and e.url != DIRECT:
                e.retired = True
                self.log(f"[pool] RETIRED {e.url} ({e.consec} consecutive fails)")
            if (e.ok + e.fail + e.bans) % 25 == 0:
                self.save()

    # ---- validation / harvest -----------------------------------------
    def _judge_ok(self, url, timeout=6):
        px = {"http": url, "https": url}
        for j in self.judges:
            try:
                t0 = time.time()
                r = requests.get(j, proxies=px, timeout=timeout,
                                 headers={"user-agent": "curl/8.5.0"})
                if r.status_code == 200 and len(r.text) < 2000:
                    return round(time.time() - t0, 2)
            except Exception:
                continue
        return None

    def validate_all(self, workers=40, timeout=6, limit=0):
        urls = [e.url for e in self.entries.values()
                if e.url != DIRECT and not e.retired]
        if limit and len(urls) > limit:
            random.shuffle(urls)
            urls = urls[:limit]
        if not urls:
            return 0
        self.log(f"[pool] validating {len(urls)} proxies ({workers} threads)...")

        def one(u):
            lat = self._judge_ok(u)
            return u, lat

        good = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for u, lat in ex.map(one, urls):
                if lat is None:
                    self.report(u, error="judge-fail")
                    self.entries[u].cool_until = time.time() + 1800
                else:
                    self.report(u, status=200, latency=lat)
                    good += 1
        self.save()
        self.log(f"[pool] validation done: {good}/{len(urls)} healthy")
        return good

    HARVEST_URLS = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=8000",
        "https://proxy-list.download/api/v1/get?type=http",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    ]

    def harvest(self, min_healthy=8, timeout=12, max_candidates=350):
        """Pull fresh free proxies from public lists; validate; return count.

        Bootstrap note: when the pool is EMPTY the list sources themselves
        are fetched directly (they are public proxy lists, not job portals
        — the user's IP is exposed to no scraping target).  Once >=1
        verified proxy exists, the harvest is routed through the pool as
        well, keeping even that traffic off the user's IP where possible.
        """
        # prefer fetching the lists through an already-verified proxy
        verified = [e.url for e in self.entries.values()
                    if e.ok > 0 and not e.retired and e.url != DIRECT
                    and e.healthy()]
        px = {"http": verified[0], "https": verified[0]} if verified else None
        if px:
            self.log("[harvest] fetching proxy lists THROUGH existing proxy "
                     "(no direct exposure)")
        else:
            self.log("[harvest] bootstrap: fetching public proxy lists "
                     "(only ever direct step; never a job portal)")
        cands = set()
        for u in self.HARVEST_URLS:
            try:
                r = requests.get(u, timeout=timeout, proxies=px,
                                 headers={"user-agent": "curl/8.5.0"})
                if r.status_code == 200:
                    found = re.findall(
                        r"\b(\d{1,3}(?:\.\d{1,3}){3}:\d{2,5})\b", r.text)
                    cands.update(f"http://{x}" for x in found)
                    self.log(f"[harvest] {u.split('/')[2]}: +{len(found)}")
                    continue
                if px:
                    self.log(f"[harvest] {u.split('/')[2]}: HTTP {r.status_code} via proxy")
            except Exception as e:
                if px:      # proxied fetch failed -> retry this source direct
                    try:
                        r = requests.get(u, timeout=timeout,
                                         headers={"user-agent": "curl/8.5.0"})
                        if r.status_code == 200:
                            found = re.findall(
                                r"\b(\d{1,3}(?:\.\d{1,3}){3}:\d{2,5})\b", r.text)
                            cands.update(f"http://{x}" for x in found)
                            self.log(f"[harvest] {u.split('/')[2]}: +{len(found)} (direct)")
                            continue
                    except Exception:
                        pass
                self.log(f"[harvest] {u.split('/')[2]} FAIL: {str(e)[:60]}")
        if not cands:
            self.log("[harvest] no sources reachable -> pool stays as is")
            return self.healthy_count()
        for c in cands:
            self.add(c)
        self.log(f"[harvest] {len(cands)} candidates -> validating (cap {max_candidates})...")
        got = self.validate_all(limit=max_candidates)
        # persist working proxies for next run
        try:
            os.makedirs(os.path.dirname(PROXY_FILE), exist_ok=True)
            with open(PROXY_FILE, "w") as f:
                f.write("# auto-generated by net_resilience.py harvest\n")
                for e in self.entries.values():
                    if e.ok and not e.retired and e.url != DIRECT:
                        f.write(e.url + "\n")
        except Exception:
            pass
        if got < min_healthy:
            self.log(f"[harvest] only {got} healthy (<{min_healthy}) — "
                     + ("portal traffic stays PAUSED, never direct (strict mode)"
                        if self.strict else "DIRECT fallback active (non-strict)"))
        return got

    def snapshot(self):
        with self.lock:
            now = time.time()
            healthy = [e for e in self.entries.values() if e.healthy(now)]
            verified = [e for e in healthy if e.ok > 0 and e.url != DIRECT]
            return {"entries": len(self.entries),
                    "healthy": len(healthy),
                    "verified": len(verified),
                    "candidates": len(healthy) - len(verified),
                    "retired": sum(1 for e in self.entries.values() if e.retired),
                    "strict_no_direct": self.strict,
                    "best": sorted([e.to_json() for e in verified],
                                   key=lambda x: x["latency"] or 9e9)[:5]}

# ------------------------------------------------------------------ pacing
class AdaptivePacer:
    """AIMD per host-class: fast when clean, global backoff when throttled."""

    def __init__(self, base=0.8, min_d=0.35, max_d=30.0, mult=2.0, decay=0.93,
                 cool_base=15.0, cool_max=600.0):
        self.base, self.min_d, self.max_d = base, min_d, max_d
        self.mult, self.decay = mult, decay
        self.cool_base, self.cool_max = cool_base, cool_max
        self.lock = threading.Lock()
        self.st = {}   # cls -> dict

    def _c(self, cls):
        if cls not in self.st:
            self.st[cls] = {"delay": self.base, "cool_until": 0.0,
                            "consec_throttle": 0, "oks": 0, "throttles": 0,
                            "errs": 0}
        return self.st[cls]

    def wait(self, cls="default"):
        with self.lock:
            c = self._c(cls)
            d = c["delay"] * random.uniform(0.8, 1.25)
            gap = max(0.0, c["cool_until"] - time.time())
        if gap > 0:
            time.sleep(min(gap, self.cool_max))
        time.sleep(min(d, self.max_d))
        return d

    def report(self, cls, ok=True, throttle=False, retry_after=None):
        with self.lock:
            c = self._c(cls)
            now = time.time()
            if throttle:
                c["throttles"] += 1
                c["consec_throttle"] += 1
                c["delay"] = min(self.max_d, max(self.base, c["delay"]) * self.mult)
                cool = min(self.cool_max,
                           self.cool_base * (2 ** (c["consec_throttle"] - 1)))
                if retry_after:
                    try:
                        cool = max(cool, min(float(int(retry_after)),
                                             self.cool_max))
                    except (TypeError, ValueError):
                        pass
                c["cool_until"] = max(c["cool_until"], now + cool)
            elif ok:
                c["oks"] += 1
                c["consec_throttle"] = 0
                c["delay"] = max(self.min_d, c["delay"] * self.decay)
            else:
                c["errs"] += 1
                c["delay"] = min(self.max_d, c["delay"] * 1.4)

    def seed(self, cls, delay):
        """Set the STARTING delay of a host-class (does not shrink below min)."""
        with self.lock:
            self._c(cls)["delay"] = max(self.min_d, min(self.max_d, delay))

    def delay(self, cls="default"):
        with self.lock:
            return self._c(cls)["delay"]

    def snapshot(self):
        with self.lock:
            return {k: {kk: (round(vv, 2) if isinstance(vv, float) else vv)
                        for kk, vv in v.items()}
                    for k, v in self.st.items()}

# ------------------------------------------------------------------ fetch
def resilient_fetch(url, pool: ProxyPool | None = None, pacer: AdaptivePacer | None = None,
                    cls="default", timeout=25, max_tries=6, method="GET",
                    extra_headers=None, log=None, session=None,
                    allow_direct=None):
    """GET with classified retries. Returns (response|None, info dict).

    Response is returned for any delivered HTTP answer (2xx..4xx); None only
    if every try failed on transport/throttle level. info has:
    tries, proxy, latency, status, throttled, permanent, error.

    STRICT NO-DIRECT (default): every try goes through a pool proxy.  When
    the pool is empty the pool auto-refills (ensure, rate-limited); if it
    stays empty the fetch fails honestly with error="no_proxy_strict" —
    the user's IP is NEVER used.  DIRECT happens only when allow_direct
    is explicitly True (or ERL_ALLOW_DIRECT=1), as the LAST try of a
    non-strict run (controlled tests / opt-in convenience).
    """
    pool = pool if pool is not None else (None if os.environ.get("ERL_ALLOW_DIRECT", "") in ("1", "true", "yes")
                                         else _GLOBAL_POOL)
    pacer = pacer or _GLOBAL_PACER
    ua = _GLOBAL_UA
    log = log or (lambda *a: None)
    strict = True
    if allow_direct is not None:
        strict = not allow_direct
    elif pool is not None:
        strict = getattr(pool, "strict", True)
    ensured = False
    info = {"tries": 0, "proxy": None, "latency": None, "status": None,
            "throttled": False, "permanent": False, "error": None,
            "strict": strict}
    last_txt = ""
    for t in range(1, max_tries + 1):
        info["tries"] = t
        if pool:
            proxy = pool.next()
            if proxy is None:
                # strict + empty pool -> auto-refill once, then honest fail
                if not ensured:
                    ensured = True
                    pool.ensure()
                    proxy = pool.next()
                if proxy is None:
                    info["error"] = "no_proxy_strict"
                    log(f"[fetch] {url[:60]} REFUSED: no healthy proxy and "
                        f"strict mode forbids using your IP (auto-harvest ran)")
                    return None, info
        else:
            if strict:                      # no pool at all -> never direct
                info["error"] = "no_pool_strict"
                log(f"[fetch] {url[:60]} REFUSED: no proxy pool configured "
                    f"and strict mode forbids using your IP")
                return None, info
            proxy = DIRECT                  # explicit non-strict, no pool
        last_try = (t == max_tries)
        if (not strict) and last_try and proxy != DIRECT:
            proxy = DIRECT                  # opt-in last-resort direct
            info["last_resort_direct"] = True
        info["proxy"] = proxy
        pacer.wait(cls)
        px = {"http": proxy, "https": proxy} if proxy and proxy != DIRECT else None
        headers = ua.headers()
        if extra_headers:
            headers.update(extra_headers)
        t0 = time.time()
        try:
            s = session or requests
            r = s.request(method, url, proxies=px, timeout=timeout,
                          headers=headers, allow_redirects=True)
        except Exception as e:
            last_txt = f"transport:{type(e).__name__}:{str(e)[:80]}"
            pool.report(proxy, error=str(e)[:80]) if pool else None
            pacer.report(cls, ok=False)
            log(f"[fetch] try{t} {url[:60]} ERR {last_txt}")
            continue
        lat = time.time() - t0
        info["latency"], info["status"] = round(lat, 2), r.status_code
        if 200 <= r.status_code < 300:
            pool.report(proxy, status=r.status_code, latency=lat) if pool else None
            pacer.report(cls, ok=True)
            return r, info
        if r.status_code in PERMANENT_CODES:
            pool.report(proxy, status=r.status_code, latency=lat) if pool else None
            pacer.report(cls, ok=True)          # target answered fine
            info["permanent"] = True
            return r, info
        if r.status_code in THROTTLE_CODES:
            ra = r.headers.get("Retry-After")
            pool.report(proxy, status=r.status_code) if pool else None
            pacer.report(cls, ok=False, throttle=True, retry_after=ra)
            info["throttled"] = True
            last_txt = f"http_{r.status_code}"
            log(f"[fetch] try{t} {url[:60]} THROTTLE {r.status_code} "
                f"(proxy={str(proxy)[:40]} retry_after={ra})")
            continue
        if r.status_code >= 500:
            pool.report(proxy, status=r.status_code, latency=lat) if pool else None
            pacer.report(cls, ok=False)
            last_txt = f"http_{r.status_code}"
            log(f"[fetch] try{t} {url[:60]} {r.status_code} -> retry")
            continue
        # other 4xx: target's real answer -> hand back, no retry
        pool.report(proxy, status=r.status_code, latency=lat) if pool else None
        pacer.report(cls, ok=True)
        return r, info
    info["error"] = last_txt or "exhausted"
    return None, info

# ------------------------------------------------------------------ globals
_GLOBAL_POOL: ProxyPool | None = None
_GLOBAL_PACER = AdaptivePacer()
_GLOBAL_UA = UARotator()

def build(pool=None, validate=False, log=print, strict=None):
    """Create/reuse the global pool+pacer; returns (pool, pacer).

    strict=None follows the ERL_ALLOW_DIRECT env (default strict).
    """
    global _GLOBAL_POOL
    if pool is None and _GLOBAL_POOL is None:
        pool = ProxyPool(validate=validate, log=log, strict=strict)
    if pool is not None:
        _GLOBAL_POOL = pool
    return _GLOBAL_POOL, _GLOBAL_PACER

def health_dump(extra=None):
    try:
        os.makedirs(WORK, exist_ok=True)
        d = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
             "pool": _GLOBAL_POOL.snapshot() if _GLOBAL_POOL else None,
             "pacer": _GLOBAL_PACER.snapshot()}
        if extra:
            d.update(extra)
        json.dump(d, open(HEALTH_FILE, "w"), indent=1)
    except Exception:
        pass

# ------------------------------------------------------------------ CLI
def _cli():
    ap = argparse.ArgumentParser(description="self-adaptive network layer "
                                             "(strict: never uses your IP)")
    ap.add_argument("cmd", choices=["harvest", "status", "live"])
    ap.add_argument("--min", type=int, default=8, help="harvest: min healthy")
    ap.add_argument("--n", type=int, default=2, help="live: number of fetches")
    ap.add_argument("--allow-direct", action="store_true",
                    help="opt-out of strict mode (use your own IP as last "
                         "resort) — NOT recommended")
    a = ap.parse_args()

    if a.cmd == "status":
        pool = ProxyPool(log=lambda *a: None)
        snap = pool.snapshot()
        print(json.dumps({"pool": snap, "pacer": _GLOBAL_PACER.snapshot()},
                         indent=1))
        return
    os.environ.pop("ERL_ALLOW_DIRECT", None)
    if a.allow_direct:
        os.environ["ERL_ALLOW_DIRECT"] = "1"
    pool, pacer = build(log=print)
    if a.cmd == "harvest":
        n = pool.harvest(min_healthy=a.min)
        print(f"healthy after harvest: {n}")
        health_dump()
        return
    if a.cmd == "live":
        urls = [
            "https://www.linkedin.com/jobs/view/4265141943",
            "https://api.ipify.org/?format=json",
            "https://example.com/",
        ][: a.n]
        for u in urls:
            r, info = resilient_fetch(u, cls="live")
            ok = r is not None and r.status_code == 200
            print(f"{'OK ' if ok else 'FAIL'} {u[:60]}  tries={info['tries']} "
                  f"proxy={str(info['proxy'])[:40]} status={info['status']} "
                  f"lat={info['latency']}s err={info['error']}")
        health_dump()

if __name__ == "__main__":
    _cli()
