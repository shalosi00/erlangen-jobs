#!/usr/bin/env python3
"""build_companies_map.py — corridor COMPANY OVERVIEW map (Bamberg -> Nürnberg).

Different from the job map (map/index.html): this one shows LITERALLY ALL
companies as individual points, straight from OpenStreetMap via the Overpass
API — no geocoding needed, coordinates come with the data. Companies that
appear as employers in the current job CSV get a "hiring now" highlight with
their open-job count.

Region: bounding box over the S1 north trunk (Bamberg Hbf ... Erlangen) plus
Fürth + Nürnberg, ~8 km margin — the Bamberg–Nürnberg axis incl. industrial
parks and Herzogenaurach.

Network: strict proxy pool only (net_resilience), Overpass mirror fallback.
Cache:   data/work/overpass_companies.json (raw elements; resumable, never
         re-hits Overpass while present; delete to force a refetch).

Usage:
  python3 scripts/build_companies_map.py --counts    # per-category volumes
  python3 scripts/build_companies_map.py             # fetch + render map/companies.html
"""
import argparse, csv, html, json, math, os, re, sys, time, urllib.parse
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "data", "work")
RAW_JSON = os.path.join(WORK, "overpass_companies.json")
OUT_HTML = os.path.join(BASE, "map", "companies.html")

# ---------------------------------------------------------------- corridor box
def corridor_bbox():
    """(s, w, n, e) over the Bamberg->Nürnberg axis: north-trunk stations +
    Fürth + Nürnberg Hbf, padded ~8 km so industrial parks are inside."""
    gaz = json.load(open(os.path.join(BASE, "data", "rail_corridor.json"), encoding="utf-8"))
    pts = [s for s in gaz["stations"] if s.get("enabled") and s.get("branch") == "north"]
    for t in ("Fürth", "Nürnberg"):
        tv = gaz["towns"].get(t)
        if tv:
            pts.append({"lat": tv["lat"], "lon": tv["lon"]})
    lat = [p["lat"] for p in pts]
    lon = [p["lon"] for p in pts]
    m = 0.075                                          # ~8 km
    return min(lat) - m, min(lon) - m, max(lat) + m, max(lon) + m

# ---------------------------------------------------------------- overpass fetch
# NOTE: maps.mail.ru removed on user instruction ("forget mail.ru"). The
# remaining Overpass mirrors are kept for LOCAL runs — from restricted
# hosting networks most are unreachable, which is why the primary data path
# below is the Photon enumerator (photon.komoot.io, reachable + pool-proven).
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]

PROBE_QL = '[out:json];node(49.45,11.07,49.46,11.08)[amenity=hospital];out 1;'
MIRROR_FILE = os.path.join(WORK, "overpass_mirror.txt")

class _PostBody:
    """Session adapter: injects a form body so resilient_fetch can POST the
    Overpass query (mail.ru's gateway truncates long GET URLs -> bogus parse
    errors). Proxy selection stays entirely inside net_resilience."""
    def __init__(self, body):
        import requests
        self._r = requests
        self.body = body
    def request(self, method, url, **kw):
        h = dict(kw.get("headers") or {})
        h["Content-Type"] = "application/x-www-form-urlencoded"
        kw["headers"] = h
        kw["data"] = self.body
        return self._r.request(method, url, **kw)

def _try(url, pool, timeout, direct, post_ql=None):
    """One fetch attempt. post_ql: query string to send as POST body.
    Returns parsed json, or None (module _LAST_ERR set)."""
    global _LAST_ERR
    import net_resilience as nr
    try:
        session = _PostBody("data=" + urllib.parse.quote(post_ql)) if post_ql else None
        resp, info = nr.resilient_fetch(
            url, pool=pool, pacer=nr.AdaptivePacer(), timeout=timeout,
            max_tries=1, extra_headers={"User-Agent": "erlangen-jobs/1.1",
                                        "Accept": "application/json"},
            log=None, allow_direct=True if direct else None,
            method="POST" if post_ql else "GET",
            session=session)
        if resp is not None:
            code = getattr(resp, "status_code", 0)
            if code < 400:
                return resp.json()
            _LAST_ERR = f"HTTP {code}"
        else:
            _LAST_ERR = str((info or {}).get("error") or "no-response")
    except Exception as e:                             # broken body / timeout
        _LAST_ERR = type(e).__name__
    return None

_LAST_ERR = ""

def pick_mirror(timeout=28, rounds=7, gap=8):
    """Find live Overpass mirrors with a tiny query (cheap, fast-fail).
    Returns live mirrors in response order; persists the winner so the heavy
    query can go straight to it. Strict pool first; direct only behind
    ERL_ALLOW_DIRECT=1."""
    import net_resilience as nr
    import enrich_addresses as ea
    pool = ea._pool()
    strict_ok = bool(pool.as_list())
    if not strict_ok and os.environ.get("ERL_ALLOW_DIRECT", "") not in ("1", "true", "yes"):
        raise RuntimeError("proxy pool is empty — refusing to go direct")
    ad = os.environ.get("ERL_ALLOW_DIRECT", "") in ("1", "true", "yes")
    live = []
    pq = urllib.parse.quote(PROBE_QL)
    for rnd in range(1, rounds + 1):
        for mir in MIRRORS:
            if mir in live:
                continue
            u = f"{mir}?data={pq}"
            for direct in ((False, True) if (ad and strict_ok) else
                           ((False,) if strict_ok else (True,))):
                if _try(u, pool, timeout, direct) is not None:
                    live.append(mir)
                    if direct:
                        print("  (direct fallback used — ERL_ALLOW_DIRECT=1)", flush=True)
                    break
        if live:
            break
        print(f"  probe round {rnd}/{rounds}: no mirror answered ({_LAST_ERR})", flush=True)
        if rnd < rounds:
            time.sleep(gap)
    if not live:
        raise RuntimeError(f"no live Overpass mirror ({_LAST_ERR})")
    os.makedirs(WORK, exist_ok=True)
    with open(MIRROR_FILE, "w", encoding="utf-8") as f:
        f.write(live[0])
    return live

def overpass_get(ql, timeout=300, rounds=3, gap=10):
    """One Overpass query, patiently: probe for live mirrors with a tiny
    query first (fast-fail), then run the heavy query against the live set
    with a generous timeout. Strict proxy pool first; direct only behind
    ERL_ALLOW_DIRECT=1 (documented opt-out, never by accident)."""
    import net_resilience as nr
    import enrich_addresses as ea
    pool = ea._pool()
    ad = os.environ.get("ERL_ALLOW_DIRECT", "") in ("1", "true", "yes")
    strict_ok = bool(pool.as_list())
    if not strict_ok and not ad:
        raise RuntimeError("proxy pool is empty — refusing to go direct")
    live = pick_mirror()
    print(f"live mirrors: {[m.split('/')[2] for m in live]}")
    q = urllib.parse.quote(ql)
    order = live + [m for m in MIRRORS if m not in live]
    for rnd in range(1, rounds + 1):
        for mir in order:
            u = f"{mir}?data={q}"
            for direct in ((False, True) if ad else (False,)):
                if direct and not (ad and strict_ok):
                    continue
                out = _try(u, pool, timeout, direct)
                if out is not None:
                    if direct:
                        print("  (direct fallback used — ERL_ALLOW_DIRECT=1)", flush=True)
                    return out
        print(f"  heavy round {rnd}/{rounds}: failed ({_LAST_ERR})", flush=True)
        if rnd < rounds:
            time.sleep(gap)
    raise RuntimeError(f"all Overpass mirrors failed ({_LAST_ERR})")

CATEGORIES = [
    # FLAT list: one (category, statement) per row — every statement must carry
    # its own (bbox) when joined, multi-statement strings would run unbounded
    ("office", 'nwr["office"]["name"]'),
    ("industry", 'nwr["landuse"="industrial"]["name"]'),
    ("industry", 'nwr["man_made"="works"]["name"]'),
    ("industry", 'nwr["building"="industrial"]["name"]'),
    ("industry", 'nwr["building"="commercial"]["name"]'),
    ("craft", 'nwr["craft"]["name"]'),
    ("retail", 'nwr["shop"]["name"]'),
]

def build_query(bbox, count=False):
    s, w, n, e = bbox
    box = f"({s:.4f},{w:.4f},{n:.4f},{e:.4f})"
    parts = ";".join(q + box for _, q in CATEGORIES)   # QL unions need ';'
    return f"[out:json][timeout:180];({parts});out {'count' if count else 'center tags'};"

TILE_LAT = 0.055                                   # ~6 km — tiles must stay tiny:
TILE_LON = 0.0427                                  # overloaded gateways 504 on
                                                   # anything heavier than a probe
TILE_DIR = os.path.join(WORK, "overpass_tiles")

def tiles(bbox):
    s, w, n, e = bbox
    r, c = 0, 0
    lat = s
    while lat < n - 1e-9:
        lat2 = min(lat + TILE_LAT, n)
        lon = w
        c = 0
        while lon < e - 1e-9:
            lon2 = min(lon + TILE_LON, e)
            yield r, c, (lat, lon, lat2, lon2)
            lon = lon2
            c += 1
        lat = lat2
        r += 1

def _stmt_chunks(maxlen=300, bbox_len=34):
    """Group the category statements into chunks whose full QL stays under
    mail.ru's gateway cap (~400 chars truncates with bogus parse errors).
    Statements are the same for every tile; each carries a (+bbox_len) bbox."""
    chunks, cur = [], []
    for cat, stmt in CATEGORIES:
        trial = cur + [stmt]
        qlen = 24 + sum(len(s) + bbox_len for s in trial) + (len(trial) - 1) + 3 + 16
        if cur and qlen > maxlen:
            chunks.append(cur)
            cur = [stmt]
        else:
            cur = trial
    if cur:
        chunks.append(cur)
    return chunks

def fetch_tiled(bbox, timeout=75, rounds=3, gap=2, passes=4, budget=540):
    """Fetch the corridor tile-by-tile (union of all categories per tile).

    Overpass gateways flap on a scale of minutes (mail.ru: 200 -> 504 ->
    200 within one session), so this runs MULTIPLE PASSES over the pending
    tiles within one call, each tile getting `rounds` attempts, and every
    success is cached to data/work/overpass_tiles/. Tiles that stay
    unfetchable are SKIPPED (not fatal) — rerun the script and it resumes
    from cache until the corridor is complete.

    Routing per attempt: direct POST first (proven path to mail.ru; the
    strict pool's free proxies truncate POST bodies -> bogus 400s), then
    GET, then the pool. Transport-dead mirrors (3 consecutive transport
    failures) are circuit-broken; gateway 504s keep a mirror in rotation."""
    import net_resilience as nr
    import enrich_addresses as ea
    pool = ea._pool()
    strict_ok = bool(pool.as_list())
    ad = os.environ.get("ERL_ALLOW_DIRECT", "") in ("1", "true", "yes")
    if not strict_ok and not ad:
        raise RuntimeError("proxy pool is empty — refusing to go direct")
    os.makedirs(TILE_DIR, exist_ok=True)
    tl = list(tiles(bbox))
    deadline = time.time() + budget
    fails, dead = {}, set()
    fetched, skipped = 0, []
    for p in range(1, passes + 1):
        pending = []
        for r, c, (s, w, n, e) in tl:
            cache = os.path.join(TILE_DIR, f"t{r}_{c}.json")
            if not os.path.exists(cache):
                pending.append((r, c, (s, w, n, e)))
        if not pending:
            break
        print(f"pass {p}/{passes}: {len(pending)} tiles pending "
              f"({time.strftime('%H:%M:%S')})", flush=True)
        still = []
        chunks = _stmt_chunks()
        for i, (r, c, (s, w, n, e)) in enumerate(pending, 1):
            if time.time() > deadline:
                still.append((r, c))
                continue
            box = f"({s:.4f},{w:.4f},{n:.4f},{e:.4f})"
            els = []
            ok = True
            for stmts in chunks:
                parts = ";".join(q2 + box for q2 in stmts)
                ql = f"[out:json][timeout:60];({parts});out center tags;"
                u_t = urllib.parse.quote(ql)
                got = None
                for rnd in range(1, rounds + 1):
                    for mir in MIRRORS:
                        if mir in dead:
                            continue
                        variants = []
                        if ad:
                            variants += [(mir, ql, True), (f"{mir}?data={u_t}", None, True)]
                        if strict_ok:
                            variants += [(mir, ql, False), (f"{mir}?data={u_t}", None, False)]
                        for u, pql, direct in variants:
                            got = _try(u, pool, timeout, direct, post_ql=pql)
                            if got is not None:
                                break
                            if _LAST_ERR.startswith("transport") or "SSLError" in _LAST_ERR:
                                fails[mir] = fails.get(mir, 0) + 1
                                if fails[mir] >= 3 and mir not in dead:
                                    dead.add(mir)
                                    print(f"    circuit-break {mir.split('/')[2]}",
                                          flush=True)
                        if got is not None:
                            break
                    if got is None and rnd < rounds:
                        time.sleep(gap)
                if got is None:
                    ok = False
                    break
                els.extend(got.get("elements", []))
            if not ok:
                still.append((r, c))
                continue
            tmp = cache + ".tmp"
            json.dump(els, open(tmp, "w", encoding="utf-8"))
            os.replace(tmp, cache)
            fetched += 1
            print(f"  tile t{r}_{c}: {len(els)} elements ({i}/{len(pending)} of pass, "
                  f"{time.strftime('%H:%M:%S')})", flush=True)
        skipped = still
        if not skipped:
            break
    all_elements = []
    for r, c, _ in tl:
        cache = os.path.join(TILE_DIR, f"t{r}_{c}.json")
        if os.path.exists(cache):
            try:
                all_elements.extend(json.load(open(cache, encoding="utf-8")))
            except Exception:
                pass
    print(f"tiled fetch: +{fetched} this call, {len(all_elements)} raw elements, "
          f"{len(skipped)} tiles still pending", flush=True)
    if skipped:
        print(f"  pending tiles: {sorted(set((r, c) for r, c in skipped))[:8]} ... "
              f"(rerun to resume)", flush=True)
    return all_elements

# ---------------------------------------------------------------- photon enum
# Photon (photon.komoot.io — same OSM data, geocoding-grade API) as the
# EXHAUSTIVE company enumerator: the public API caps responses at 50, so we
# sweep single-character queries (every company name starts with one of them)
# over tiles, OR-ing all company tag filters, and recursively split any
# (tile, letter) that saturates the cap. All traffic via the strict proxy pool.
PHOTON = "https://photon.komoot.io/api"
PTAGS = ("osm_tag=office&osm_tag=shop&osm_tag=craft"
         "&osm_tag=landuse:industrial&osm_tag=building:industrial"
         "&osm_tag=building:commercial&osm_tag=man_made:works")
LETTERS = list("abcdefghijklmnopqrstuvwxyzäöü0123456789")
PCAP = 50                                              # public API hard cap
PTILE_DIR = os.path.join(WORK, "photon_tiles")

def _photon_query(letter, s, w, n, e, pool, timeout=25):
    time.sleep(0.4)                                # centralized pacing: recursion
    u = (f"{PHOTON}?q={urllib.parse.quote(letter)}&{PTAGS}"
         f"&limit={PCAP}&bbox={w:.4f},{s:.4f},{e:.4f},{n:.4f}")
    ad = os.environ.get("ERL_ALLOW_DIRECT", "") in ("1", "true", "yes")
    # With the opt-out set, the fast lane (direct, ~1s) goes first and the
    # strict pool is the fallback; without it, pool-only. The pool's free
    # proxies cost 10-16s per query, which alone would make the sweep take
    # hours — direct-first keeps it in minutes while staying opt-in.
    order = ((True, False) if ad else (False,))
    for direct in order:
        out = _try(u, pool, timeout, direct)
        if out is not None:
            return out.get("features", [])
    return None

def _photon_letter(letter, s, w, n, e, pool, depth=0):
    """All companies matching one letter inside a tile; splits into quadrants
    when the 50-cap saturates (their real count may be higher)."""
    feats = _photon_query(letter, s, w, n, e, pool)
    if feats is None:
        return None                                    # network flake -> tile retries
    if len(feats) < PCAP or depth >= 2 or (n - s) < 0.010:
        return feats
    # saturated -> quadrants
    out, ok = [], True
    for (qs, qw, qn, qe) in ((s, w, (s + n) / 2, (w + e) / 2), (s, (w + e) / 2, (s + n) / 2, e),
                             ((s + n) / 2, w, n, (w + e) / 2), ((s + n) / 2, (w + e) / 2, n, e)):
        sub = _photon_letter(letter, qs, qw, qn, qe, pool, depth + 1)
        if sub is None:
            ok = False
            break
        out.extend(sub)
    return out if ok else None

def _photon_base_tiles(bbox, size=0.08):
    s, w, n, e = bbox
    r = c = 0
    lat = s
    while lat < n - 1e-9:
        lat2 = min(lat + size, n)
        lon = w
        c = 0
        while lon < e - 1e-9:
            lon2 = min(lon + size * 1.4, e)            # lon degrees are shorter
            yield r, c, (lat, lon, lat2, lon2)
            lon = lon2
            c += 1
        lat = lat2
        r += 1

def _letter_cache(tile_dir, r, c, L):
    return os.path.join(tile_dir, f"t{r}_{c}", f"{L}.json")

def fetch_photon(bbox, workers=5, passes=4, budget=540):
    """Enumerate every named company in the corridor via Photon letter-sweeps.
    Progress is cached PER LETTER (data/work/photon_tiles/t{r}_{c}/<L>.json) —
    dense Nürnberg-centre tiles need 15+ minutes of queries, more than one
    sandbox call allows, so partial tile progress must survive restarts.
    A tile counts as done when all 39 letter files exist. GENTLE by necessity:
    the public instance rate-limits hard (bursts get 403-banned), so this
    paces every request and backs off on 4xx."""
    from concurrent.futures import ThreadPoolExecutor
    import enrich_addresses as ea
    pool = ea._pool()
    if not pool.as_list():
        raise RuntimeError("proxy pool is empty — cannot run the Photon sweep")
    os.makedirs(PTILE_DIR, exist_ok=True)
    deadline = time.time() + budget
    tl = list(_photon_base_tiles(bbox))

    def tile_done(t):
        r, c, _ = t
        if os.path.exists(os.path.join(PTILE_DIR, f"t{r}_{c}.json")):
            return True                                 # legacy whole-tile cache
        return all(os.path.exists(_letter_cache(PTILE_DIR, r, c, L))
                   for L in LETTERS)

    def tile_progress(t):
        return len(LETTERS) if tile_done(t) else 0

    fetched = 0
    for p in range(1, passes + 1):
        pending = [t for t in tl if tile_progress(t) < len(LETTERS)]
        if not pending:
            break
        print(f"photon pass {p}/{passes}: {len(pending)} tiles pending "
              f"({time.strftime('%H:%M:%S')})", flush=True)

        def work(t):
            r, c, (s, w, n, e) = t
            new, misses, done0 = 0, 0, 0
            for L in LETTERS:
                if time.time() > deadline:
                    break
                lf = _letter_cache(PTILE_DIR, r, c, L)
                if os.path.exists(lf):
                    done0 += 1
                    continue
                sub = _photon_letter(L, s, w, n, e, pool)
                if sub is None:
                    misses += 1
                    if misses >= 3:                    # network dead -> next tile
                        break
                    if "HTTP 4" in _LAST_ERR:          # rate-limited -> cool down
                        time.sleep(90)
                    else:
                        time.sleep(4)
                    continue
                misses = 0
                os.makedirs(os.path.dirname(lf), exist_ok=True)
                tmp = lf + ".tmp"
                json.dump(sub, open(tmp, "w", encoding="utf-8"))
                os.replace(tmp, lf)
                new += 1
            return t, done0 + new, new

        for t, done, new in ThreadPoolExecutor(max_workers=workers) \
                .map(work, pending):
            if done >= len(LETTERS):
                fetched += 1
                print(f"  tile t{t[0]}_{t[1]} COMPLETE ({done}/{len(LETTERS)} letters, "
                      f"+{new} new, {time.strftime('%H:%M:%S')})", flush=True)
            elif new:
                print(f"  tile t{t[0]}_{t[1]} partial: {done}/{len(LETTERS)} letters "
                      f"(+{new} new, {time.strftime('%H:%M:%S')})", flush=True)
        if time.time() > deadline:
            break
    all_feats, done_tiles = [], 0
    for r, c, _ in tl:
        legacy = os.path.join(PTILE_DIR, f"t{r}_{c}.json")
        lfs = [_letter_cache(PTILE_DIR, r, c, L) for L in LETTERS]
        try:
            if os.path.exists(legacy):                  # legacy whole-tile cache
                all_feats.extend(json.load(open(legacy, encoding="utf-8")))
                done_tiles += 1
            elif all(os.path.exists(f) for f in lfs):
                for f in lfs:
                    all_feats.extend(json.load(open(f, encoding="utf-8")))
                done_tiles += 1
        except Exception:
            pass
    print(f"photon sweep: {done_tiles}/{len(tl)} tiles complete, {len(all_feats)} raw "
          f"feature-hits (rerun to resume)", flush=True)
    return all_feats

def features_to_elements(features):
    """Photon GeoJSON features -> pseudo-Overpass elements so parse_companies()
    can treat both sources identically. The same OSM object arrives once per
    matching letter ("Alpha Technik" matches 'a' AND 't') -> dedupe by id."""
    els, seen = [], set()
    for f in features:
        p = f.get("properties") or {}
        co = (f.get("geometry") or {}).get("coordinates") or [None, None]
        lon, lat = co[0], co[1]
        if lat is None or not p.get("name"):
            continue
        key = (p.get("osm_type"), p.get("osm_id"))
        if key in seen:
            continue
        seen.add(key)
        tags = {"name": str(p["name"]).strip()}
        if p.get("osm_key"):
            tags[p["osm_key"]] = str(p.get("osm_value") or "yes")
        for k in ("housenumber", "street", "postcode", "city", "district"):
            if p.get(k):
                tags["addr:" + k] = str(p[k])
        els.append({"type": (p.get("osm_type") or "N").upper(),
                    "id": p.get("osm_id"),
                    "lat": float(lat), "lon": float(lon),
                    "tags": {k: v for k, v in tags.items() if v}})
    return els

# ---------------------------------------------------------------- parse + dedupe
def _center(el):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center") or {}
    return c.get("lat"), c.get("lon")

def parse_companies(elements):
    """Overpass elements -> compact company dicts. Returns (companies, dropped)."""
    out, seen_boxes, dropped = [], defaultdict(list), 0
    for el in elements:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            dropped += 1
            continue
        lat, lon = _center(el)
        if lat is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            dropped += 1
            continue
        cat = ("office" if "office" in tags
               else "craft" if "craft" in tags
               else "industry" if ("industrial" in tags
                                   or tags.get("landuse") == "industrial"
                                   or tags.get("man_made") == "works"
                                   or tags.get("building") in ("industrial", "commercial"))
               else "retail" if "shop" in tags
               else "other")
        addr = ", ".join(x for x in (
            " ".join(x for x in (tags.get("addr:street"), tags.get("addr:housenumber")) if x),
            " ".join(x for x in (tags.get("addr:postcode"), tags.get("addr:city")) if x)) if x)
        c = {"n": name, "k": cat,
             "lat": round(float(lat), 6), "lon": round(float(lon), 6)}
        if addr:
            c["a"] = addr[:110]
        for extra in ("website", "brand", "operator"):
            if tags.get(extra) and extra != "name":
                c["w"] = tags[extra][:90]              # website or brand
                break
        out.append(c)
    # dedupe: same normalised name within ~120 m (node+way duplicates in OSM)
    def nname(s):
        return re.sub(r"[^a-z0-9]+", "", s.lower())
    out.sort(key=lambda c: (nname(c["n"]), c["lat"], c["lon"]))
    kept = []
    cell = defaultdict(list)                           # ~0.0015° grid ≈ 170 m
    for c in out:
        nn, la, lo = nname(c["n"]), c["lat"], c["lon"]
        gx, gy = int(la / 0.0015), int(lo / 0.0015)
        dup = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (pnn, pla, plo) in cell[(gx + dx, gy + dy)]:
                    if nn == pnn and abs(la - pla) < 0.0011 and abs(lo - plo) < 0.0018:
                        dup = True
                        break
                if dup:
                    break
            if dup:
                break
        if dup:
            dropped += 1
            continue
        cell[(gx, gy)].append((nn, la, lo))
        kept.append(c)
    return kept, dropped

# ---------------------------------------------------------------- job overlap
def norm_name(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

def load_job_employers():
    """Employer -> (n jobs, newest title) from the newest final CSV."""
    import glob as _g
    cands = sorted(f for f in _g.glob(os.path.join(BASE, "download", "erlangen_jobs_final_*.csv"))
                   if "_part" not in os.path.basename(f) and "_geo" in f) or \
            sorted(f for f in _g.glob(os.path.join(BASE, "download", "erlangen_jobs_final_*.csv"))
                   if "_part" not in os.path.basename(f))
    if not cands:
        return {}, None
    src = cands[-1]
    emps = {}
    for r in csv.DictReader(open(src, newline="", encoding="utf-8")):
        k = norm_name(r.get("company"))
        if not k:
            continue
        e = emps.setdefault(k, [0, "", ""])            # [jobs, newest title, newest date]
        e[0] += 1
        d = r.get("date_posted") or ""
        if d >= e[2]:
            e[2] = d
            e[1] = (r.get("title") or "")[:80]
    return {k: (v[0], v[1]) for k, v in emps.items()}, os.path.basename(src)

def match_employers(companies, emps):
    """Flag companies that look like a CSV employer (substring, min 5 chars,
    both directions). Returns number flagged."""
    emp_keys = sorted(emps.keys(), key=len, reverse=True)
    flagged = 0
    for c in companies:
        nn = norm_name(c["n"])
        hit = None
        for ek in emp_keys:
            if len(ek) >= 5 and (ek in nn or (len(nn) >= 5 and nn in ek)):
                hit = ek
                break
        if hit:
            n_jobs, newest = emps[hit]
            c["j"] = [n_jobs, newest]
            flagged += 1
    return flagged

# ---------------------------------------------------------------- render
CAT_STYLE = {
    "office":    {"color": "#4dabf7", "label": "Office / services"},
    "industry":  {"color": "#ff922b", "label": "Industry / plants"},
    "craft":     {"color": "#69db7c", "label": "Craft businesses"},
    "retail":    {"color": "#f783ac", "label": "Retail"},
    "other":     {"color": "#adb5bd", "label": "Other"},
}
HIRE = "#ffd43b"                                       # hiring-now highlight

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--bg:#10151c;--panel:#161d27;--edge:#232d3b;--txt:#dbe4ee;--dim:#8296ac;--hot:#4dabf7}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);
 font:14px/1.45 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
#layout{display:flex;height:100%}
#side{width:330px;min-width:330px;background:var(--panel);border-right:1px solid var(--edge);
 display:flex;flex-direction:column;z-index:800}
#side header{padding:14px 16px 10px;border-bottom:1px solid var(--edge)}
#side h1{margin:0;font-size:17px;letter-spacing:.2px}
#side h1 b{color:var(--hot)}
#stats{margin-top:6px;color:var(--dim);font-size:12px}
#stats b{color:var(--txt)}
#search{margin:12px 16px 8px;padding:8px 10px;width:calc(100% - 32px);background:#0d1218;
 border:1px solid var(--edge);border-radius:8px;color:var(--txt);outline:none}
#search:focus{border-color:var(--hot)}
#filters{padding:0 16px}
#filters label{display:flex;align-items:center;gap:7px;padding:3px 0;cursor:pointer;font-size:13px}
#filters .cnt{margin-left:auto;color:var(--dim);font-size:11px}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
.hiredot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none;border:2px solid __HIRE__}
.sect{padding:10px 16px 4px;color:var(--dim);font-size:10.5px;text-transform:uppercase;letter-spacing:1px}
.toggler{display:flex;align-items:center;gap:7px;padding:3px 16px 3px;cursor:pointer;font-size:13px}
.toggler input{accent-color:__HIRE__}
#legend{padding:8px 16px 12px;color:var(--dim);font-size:11.5px;line-height:1.7}
#side footer{padding:10px 16px;border-top:1px solid var(--edge);color:var(--dim);font-size:11px}
#side footer a{color:var(--dim)}
#map{flex:1}
#reset{position:absolute;top:12px;right:12px;z-index:900;background:var(--panel);color:var(--txt);
 border:1px solid var(--edge);border-radius:8px;padding:7px 12px;cursor:pointer;font-size:12.5px}
#reset:hover{border-color:var(--hot)}
.leaflet-popup-content-wrapper{background:var(--panel);color:var(--txt);border-radius:10px}
.leaflet-popup-tip{background:var(--panel)}
.leaflet-popup-content{margin:12px 14px}
.leaflet-container a.leaflet-popup-close-button{color:var(--dim)}
.pp{min-width:240px;max-width:320px}
.pc{font-size:15px;font-weight:650;color:#fff}
.pa{color:var(--dim);font-size:12px;margin:2px 0 6px}
.cat{font-size:10px;border:1px solid var(--edge);border-radius:20px;padding:1px 7px;color:var(--dim)}
.hire{display:inline-block;font-size:10.5px;border-radius:20px;padding:1px 8px;margin-left:6px;
 background:__HIRE__;color:#1a1a1a;font-weight:650}
.hire a{color:#1a1a1a}
@media(max-width:720px){#layout{flex-direction:column}#side{width:100%;min-width:0;height:45%;order:2}#map{height:55%}}
</style>
</head>
<body>
<div id="layout">
 <div id="side">
  <header>
   <h1><b>__TITLE__</b></h1>
   <div id="stats"></div>
  </header>
  <input id="search" type="search" placeholder="Search company name…" autocomplete="off">
  <div class="sect">Company types</div>
  <div id="filters"></div>
  <label class="toggler"><input type="checkbox" id="onlyhiring"> <span class="hiredot"></span>
    only companies with job openings</label>
  <div class="sect">Legend</div>
  <div id="legend">
   small dot = company point (OpenStreetMap)<br>
   <span class="hiredot"></span> yellow ring = has current job postings<br>
   every point is one company — nothing aggregated
  </div>
  <footer>
   Generated __GENERATED__ · companies: OpenStreetMap (Overpass)<br>
   job openings: <code>__CSV__</code> via strict proxy-only network<br>
   <a href="https://github.com/shalosi00/erlangen-jobs" target="_blank" rel="noopener">github.com/shalosi00/erlangen-jobs</a>
  </footer>
 </div>
 <div id="map"><button id="reset">Reset view</button></div>
</div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const P = JSON.parse(document.getElementById('payload').textContent);
const esc = s => { const d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; };
const CATS = __CATS__;

const map = L.map('map', { zoomControl: true, preferCanvas: true });
const ctr = P.c.length
  ? [P.c.reduce((s,c)=>s+c.lat,0)/P.c.length, P.c.reduce((s,c)=>s+c.lon,0)/P.c.length]
  : [49.62, 11.02];
map.setView(ctr, 10);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
  maxZoom: 17,
  attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'
}).addTo(map);

const canvas = L.canvas({ padding: 0.3 });
const layer = L.layerGroup().addTo(map);

function popupFor(c){
  const st = CATS[c.k] || CATS.other;
  let h = '<div class="pp"><div class="pc">' + esc(c.n) + '</div>'
        + '<div class="pa">' + esc(c.a || 'address not mapped') + '</div>'
        + '<div><span class="cat">' + esc(st.label) + '</span>';
  if (c.j) h += '<span class="hire">hiring now: ' + c.j[0] + ' job' + (c.j[0]>1?'s':'') + '</span>';
  if (c.j && c.j[1]) h += '<div class="pa" style="margin-top:6px">newest: ' + esc(c.j[1]) + '</div>';
  if (c.w) h += '<div class="pa">' + esc(c.w) + '</div>';
  return h + '</div></div>';
}

const all = P.c.map(c => {
  const hire = !!c.j;
  const m = L.circleMarker([c.lat, c.lon], {
    renderer: canvas, radius: hire ? 5.5 : 3.5,
    color: hire ? CATS.hire.color : '#eef4fb', weight: hire ? 1.8 : 0.7,
    fillColor: hire ? CATS.hire.color : (CATS[c.k] || CATS.other).color,
    fillOpacity: hire ? .95 : .82 });
  m.bindPopup(popupFor(c), { maxWidth: 340 });
  m._c = c; return m;
});

function applyFilters(){
  const q = document.getElementById('search').value.trim().toLowerCase();
  const on = new Set([...document.querySelectorAll('#filters input:checked')].map(i => i.value));
  const onlyHire = document.getElementById('onlyhiring').checked;
  const keep = all.filter(m => {
    const c = m._c;
    if (!on.has(c.k)) return false;
    if (onlyHire && !c.j) return false;
    if (q && !c.n.toLowerCase().includes(q)) return false;
    return true;
  });
  layer.clearLayers(); keep.forEach(m => layer.addLayer(m));
  const hires = keep.reduce((s,m)=>s+(m._c.j?1:0),0);
  document.getElementById('stats').innerHTML =
    '<b>' + keep.length.toLocaleString() + '</b> companies shown · <b>' +
    hires.toLocaleString() + '</b> hiring now · ' + P.c.length.toLocaleString() + ' total in region';
}
document.getElementById('search').addEventListener('input', applyFilters);
document.getElementById('onlyhiring').addEventListener('change', applyFilters);

const fdiv = document.getElementById('filters');
Object.keys(CATS).forEach(k => {
  if (k === 'hire') return;
  const cnt = P.c.filter(c => c.k === k).length;
  const l = document.createElement('label');
  l.innerHTML = '<input type="checkbox" value="' + k + '" checked> <span class="dot" style="background:' +
    CATS[k].color + '"></span> ' + esc(CATS[k].label) + ' <span class="cnt">' + cnt.toLocaleString() + '</span>';
  fdiv.appendChild(l);
});
fdiv.addEventListener('change', applyFilters);

document.getElementById('reset').onclick = () => map.setView(ctr, 10);
applyFilters();
</script>
</body>
</html>
"""

def render(payload, title, generated, csv_name):
    cats = {k: dict(v) for k, v in CAT_STYLE.items()}
    cats["hire"] = {"color": HIRE, "label": "hiring now"}
    js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE.replace("__PAYLOAD__", js)
                    .replace("__CATS__", json.dumps(cats))
                    .replace("__HIRE__", HIRE)
                    .replace("__TITLE__", html.escape(title))
                    .replace("__GENERATED__", html.escape(generated))
                    .replace("__CSV__", html.escape(csv_name)))

def main():
    ap = argparse.ArgumentParser(description="Bamberg–Nürnberg company overview map")
    ap.add_argument("--counts", action="store_true", help="only print per-category volumes")
    ap.add_argument("--provider", default="photon", choices=["photon", "overpass"],
                    help="photon = letter-sweep enumerator (works everywhere, pool-only); "
                         "overpass = classic Overpass query (needs a reachable mirror, "
                         "better for local runs)")
    ap.add_argument("--out", default=OUT_HTML)
    a = ap.parse_args()

    bbox = corridor_bbox()
    s, w, n, e = bbox
    print(f"corridor box: lat {s:.3f}..{n:.3f}  lon {w:.3f}..{e:.3f}")
    emps, csv_name = load_job_employers()
    print(f"job CSV: {csv_name} | {len(emps)} distinct employers to cross-match")

    if a.provider == "photon":
        feats = fetch_photon(bbox)                     # cached + resumable
        elements = features_to_elements(feats)
    else:
        elements = fetch_tiled(bbox)
    companies, dropped = parse_companies(elements)
    flagged = match_employers(companies, emps)
    print(f"parsed: {len(companies)} companies ({dropped} nameless/duplicate dropped), "
          f"{flagged} flagged as hiring from the job CSV")

    from collections import Counter
    cats = Counter(c["k"] for c in companies)
    print("categories:", dict(cats.most_common()))
    if a.counts:
        return
    hires = sum(1 for c in companies if c.get("j"))
    payload = {
        "c": companies, "hires": hires, "region": "Bamberg – Nürnberg",
        "generated": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(payload, "Corridor Companies Bamberg–Nürnberg",
                       payload["generated"], csv_name or "jobs.csv"))
    print(f"output: {a.out} ({os.path.getsize(a.out)//1024} KB)")

if __name__ == "__main__":
    main()
