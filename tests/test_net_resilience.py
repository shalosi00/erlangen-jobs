#!/usr/bin/env python3
"""test_net_resilience.py — offline unit tests for the self-adaptive network layer.

Uses a local HTTP test server (scripted status sequences) + a local fake
HTTP proxy (absolute-URI GET) so NO external network is needed.

Focus since self-adaptive-net-2 (strict no-IP mode):
  * empty strict pool NEVER yields a direct request (hit-counter proof)
  * no pool -> refused (no_pool_strict)
  * auto-refill via ensure() rescues fetches when proxies vanish
  * explicit allow_direct=True opt-out still works (controlled tests only)

Run:  python3 scripts/test_net_resilience.py
Exit 0 = all PASS.
"""
import json, os, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import net_resilience
from net_resilience import (AdaptivePacer, ProxyPool, UARotator,
                            resilient_fetch)

TMP = tempfile.mkdtemp(prefix="netres_test_")
# ISOLATION: tests must not pick up the real proxy file / env pool
net_resilience.PROXY_FILE = os.path.join(TMP, "no_proxies_here.txt")
os.environ.pop("PROXY_LIST", None)
os.environ.pop("ERL_ALLOW_DIRECT", None)
PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  ({extra})" if extra else ""))

# ------------------------------------------------------------------ test servers
HITS = {"direct": 0, "proxied": 0}      # how requests reached the target

class SeqHandler(BaseHTTPRequestHandler):
    # path -> list of (status, body); last item repeats
    SEQ = {}
    log_message = lambda *a, **k: None

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("http://"):          # absolute URI => proxied call
            HITS["proxied"] += 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"PROXY-OK")
            return
        HITS["direct"] += 1
        seq = self.SEQ.get(path, [(200, b"ok")])
        status, body = seq.pop(0) if len(seq) > 1 else seq[0]
        self.send_response(status)
        if status == 429:
            self.send_header("Retry-After", "1")
        self.end_headers()
        self.wfile.write(body)

def start_server(seqs):
    SeqHandler.SEQ = seqs
    srv = ThreadingHTTPServer(("127.0.0.1", 0), SeqHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"

def no_harvest(pool):
    """Suppress auto-harvest (offline tests): ensure() becomes a no-op."""
    pool._last_ensure = time.time() + 10_000

# ------------------------------------------------------------------ tests
def main():
    print("== net_resilience unit tests ==")

    # --- 1) UA rotator ---------------------------------------------------
    ua = UARotator()
    h1, h2 = ua.headers(), ua.headers()
    check("ua: distinct UAs over 20 picks", ua.distinct(20) >= 3)
    check("ua: headers carry user-agent + accept-language",
          "user-agent" in h1 and "accept-language" in h1)
    check("ua: client hints consistent with UA",
          ("sec-ch-ua" in h2) == ("Chrome" in h2["user-agent"] or "Edge" in h2["user-agent"]))

    # --- 2) pacer AIMD ----------------------------------------------------
    p = AdaptivePacer(base=0.5, min_d=0.1, max_d=4.0, mult=2.0, decay=0.5,
                      cool_base=0.05, cool_max=0.2)
    d0 = p.delay("t")
    for _ in range(3):
        p.report("t", throttle=True)
    d1 = p.delay("t")
    check("pacer: 3 throttles multiply delay (0.5->4.0 cap)",
          d1 == 4.0, f"{d0}->{d1}")
    p.report("t", ok=True)
    check("pacer: success decays delay", p.delay("t") == 2.0, f"{p.delay('t')}")
    snap = p.snapshot()["t"]
    check("pacer: counters tracked", snap["throttles"] == 3 and snap["oks"] == 1)
    p_ra = AdaptivePacer(base=0.05, min_d=0.01, max_d=1.0, cool_base=0.05,
                         cool_max=600)   # high cap so Retry-After is visible
    p_ra.report("ra", throttle=True, retry_after="5")
    c = p_ra.st["ra"]["cool_until"]
    check("pacer: Retry-After honored in cooldown", c - time.time() >= 4.5,
          f"cool={c - time.time():.1f}s")

    # --- 3) fetch: 429,429,200 -> succeeds on try 3 (explicit non-strict) --
    srv, B = start_server({"/flaky": [(429, b"slow down"), (429, b"still"), (200, b"fine")]})
    pacer = AdaptivePacer(base=0.02, min_d=0.01, max_d=0.05, mult=2.0,
                          cool_base=0.05, cool_max=0.15)
    r, info = resilient_fetch(f"{B}/flaky", pool=None, pacer=pacer, cls="f1",
                              max_tries=6, allow_direct=True)
    check("fetch: recovers after 2x429", r is not None and r.status_code == 200)
    check("fetch: took 3 tries", info["tries"] == 3, f"tries={info['tries']}")
    check("fetch: throttled flag set", info["throttled"])
    check("fetch: pacer slowed then recovered", pacer.delay("f1") > 0.02)

    # --- 4) fetch: 404 never retried ---------------------------------------
    start_server({"/gone": [(404, b"nope")]})
    r, info = resilient_fetch(f"{B}/gone", pool=None, pacer=pacer, cls="f2",
                              max_tries=4, allow_direct=True)
    check("fetch: 404 returned without retry",
          r is not None and r.status_code == 404 and info["tries"] == 1
          and info["permanent"])

    # --- 5) fetch: 500 then 200 --------------------------------------------
    start_server({"/err5xx": [(500, b"boom"), (200, b"recovered")]})
    r, info = resilient_fetch(f"{B}/err5xx", pool=None, pacer=pacer, cls="f3",
                              max_tries=4, allow_direct=True)
    check("fetch: 5xx soft-retried to success",
          r is not None and r.status_code == 200 and info["tries"] == 2)

    # --- 6) pool: LRU rotation + strict/DIRECT semantics ---------------------
    pool2 = ProxyPool(state_file=f"{TMP}/p2.json", log=lambda *a: None)
    pool2.add("http://10.255.255.1:9")   # black hole (will fail fast on use)
    pool2.add("http://10.255.255.2:9")
    n1, n2, n3 = pool2.next(), pool2.next(), pool2.next()
    check("pool: LRU rotates between proxies",
          n1 != n2 and n3 == n1, f"{n1},{n2},{n3}")
    lst1, lst2 = pool2.as_list(), pool2.as_list()
    check("pool: as_list rotates order per call", lst1[0] != lst2[0])
    empty = ProxyPool(state_file=f"{TMP}/p3.json", log=lambda *a: None)
    check("pool: strict empty pool next() -> None (never your IP)",
          empty.next() is None)
    check("pool: strict empty pool as_list() -> []", empty.as_list() == [])
    os.environ["ERL_ALLOW_DIRECT"] = "1"
    loose = ProxyPool(state_file=f"{TMP}/p3b.json", log=lambda *a: None)
    check("pool: ERL_ALLOW_DIRECT=1 -> non-strict empty pool returns DIRECT",
          loose.next() == "DIRECT")
    os.environ.pop("ERL_ALLOW_DIRECT")

    # --- 7) pool: ban cooldown grows, retire after 4 --------------------------
    pool3 = ProxyPool(state_file=f"{TMP}/p4.json", log=lambda *a: None)
    pool3.add("http://1.2.3.4:8080")
    pool3.report("http://1.2.3.4:8080", status=429)
    c1 = pool3.entries["http://1.2.3.4:8080"].cool_until - time.time()
    pool3.report("http://1.2.3.4:8080", status=429)
    c2 = pool3.entries["http://1.2.3.4:8080"].cool_until - time.time()
    check("pool: exponential ban cooldown", c2 > c1, f"{c1:.0f}s -> {c2:.0f}s")
    for _ in range(4):
        pool3.report("http://1.2.3.4:8080", error="conn refused")
    check("pool: retired after 4 consecutive fails",
          pool3.entries["http://1.2.3.4:8080"].retired)
    check("pool: retired proxy skipped by next() (strict -> None)",
          pool3.next() is None)

    # --- 8) pool: persistence roundtrip ---------------------------------------
    # retired entries are dropped on reload (no dead history),
    # healthy/working entries survive with their stats.
    pool3.add("http://5.6.7.8:3128")
    pool3.report("http://5.6.7.8:3128", status=200, latency=0.5)
    pool3.save()
    pool3b = ProxyPool(state_file=f"{TMP}/p4.json", log=lambda *a: None)
    check("pool: retired entry dropped on reload (no dead history)",
          "http://1.2.3.4:8080" not in pool3b.entries)
    e2 = pool3b.entries.get("http://5.6.7.8:3128")
    check("pool: healthy entry persists with stats (ok count, latency)",
          e2 is not None and e2.ok >= 1 and not e2.retired)
    check("pool: snapshot reports strict_no_direct",
          pool3b.snapshot()["strict_no_direct"] is True)

    # --- 9) proxy plumbing: real request through local fake proxy -------------
    srv2, B2 = start_server({"/ok": [(200, b"target")]})
    psrv, PURL = start_server({})
    PPORT = psrv.server_address[1]    # real port number from the socket
    pool4 = ProxyPool(state_file=f"{TMP}/p5.json", log=lambda *a: None)
    pool4.add(f"http://127.0.0.1:{PPORT}")
    pool4.validate_all(workers=2)     # judges via proxy may fail offline; ignore
    pacer2 = AdaptivePacer(base=0.02, min_d=0.01, max_d=0.05)
    r, info = resilient_fetch(f"{B2}/ok", pool=pool4, pacer=pacer2,
                              cls="f4", max_tries=3)
    via_proxy = (r is not None and info["proxy"] == f"http://127.0.0.1:{PPORT}"
                 and r.status_code == 200)
    check("fetch: request routes through configured proxy", via_proxy,
          f"proxy={info['proxy']} status={info['status']} tries={info['tries']}")

    # --- 10) exhausted transport errors -> honest None -------------------------
    pool5 = ProxyPool(state_file=f"{TMP}/p6.json", log=lambda *a: None)
    pool5.add("http://10.255.255.9:9")   # unroutable
    pool5.add("http://10.255.255.8:9")   # second unroutable (rotation keeps
    no_harvest(pool5)                    # supplying proxies for every try)
    pacer3 = AdaptivePacer(base=0.01, min_d=0.01, max_d=0.02, cool_base=0.0,
                           cool_max=0.01)
    r, info = resilient_fetch("http://127.0.0.1:1/nope", pool=pool5, pacer=pacer3,
                              cls="f5", max_tries=2, timeout=2)
    check("fetch: honest failure after max_tries (no fake success)",
          r is None and info["tries"] == 2 and str(info["error"]).startswith("transport"),
          f"tries={info['tries']} err={info['error']}")

    # --- 11) STRICT: empty pool -> refused, ZERO direct hits --------------------
    hits_before = HITS["direct"]
    pool6 = ProxyPool(state_file=f"{TMP}/p7.json", log=lambda *a: None)
    no_harvest(pool6)
    r, info = resilient_fetch(f"{B2}/ok", pool=pool6, pacer=pacer3,
                              cls="f6", max_tries=4)
    check("strict: empty pool -> honest no_proxy_strict",
          r is None and info["error"] == "no_proxy_strict", f"err={info['error']}")
    check("strict: NO request left the machine (direct hit counter unchanged)",
          HITS["direct"] == hits_before, f"direct hits delta={HITS['direct']-hits_before}")

    # --- 12) STRICT: no pool at all -> refused, ZERO direct hits ----------------
    hits_before = HITS["direct"]
    r, info = resilient_fetch(f"{B2}/ok", pool=None, pacer=pacer3,
                              cls="f7", max_tries=4)
    check("strict: no pool -> honest no_pool_strict",
          r is None and info["error"] == "no_pool_strict", f"err={info['error']}")
    check("strict: NO request left the machine (no pool)",
          HITS["direct"] == hits_before)

    # --- 13) auto-refill: ensure() rescues a dry pool (self-adjusting) ---------
    pool7 = ProxyPool(state_file=f"{TMP}/p8.json", log=lambda *a: None)
    def fake_ensure(min_healthy=3, **kw):
        pool7.add(f"http://127.0.0.1:{PPORT}")
        pool7.report(f"http://127.0.0.1:{PPORT}", status=200, latency=0.01)
        return pool7.healthy_count()
    pool7.ensure = fake_ensure
    r, info = resilient_fetch(f"{B2}/ok", pool=pool7, pacer=pacer3,
                              cls="f8", max_tries=4)
    check("auto-refill: dry pool refilled by ensure() then fetch succeeds via proxy",
          r is not None and r.status_code == 200
          and info["proxy"] == f"http://127.0.0.1:{PPORT}",
          f"proxy={info['proxy']} tries={info['tries']}")

    # --- 14) explicit opt-out: allow_direct=True works (controlled tests only) --
    r, info = resilient_fetch(f"{B2}/ok", pool=None, pacer=pacer3,
                              cls="f9", max_tries=2, allow_direct=True)
    check("opt-out: allow_direct=True permits direct fetch",
          r is not None and r.status_code == 200 and info["proxy"] == "DIRECT",
          f"proxy={info['proxy']}")

    # --- 15) ensure() rate limiting ---------------------------------------------
    pool8 = ProxyPool(state_file=f"{TMP}/p9.json", log=lambda *a: None)
    calls = {"n": 0}
    pool8.harvest = lambda **kw: calls.__setitem__("n", calls["n"] + 1) or 0
    pool8.ensure(min_healthy=5)
    pool8.ensure(min_healthy=5)
    check("auto-refill: rate-limited to one harvest per cooldown window",
          calls["n"] == 1, f"harvest calls={calls['n']}")

    # --- summary -----------------------------------------------------------------
    print(f"\n== {len(PASS)} PASS / {len(FAIL)} FAIL ==")
    if FAIL:
        print("failed:", ", ".join(FAIL))
        sys.exit(1)
    print("ALL TESTS PASSED")

if __name__ == "__main__":
    main()
