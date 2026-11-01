#!/usr/bin/env python3
"""
Free-proxy fetch + validate engine for the Asha job toolkit.

Pipeline:
  1. Fetch candidate proxy lists from vetted GitHub repos (raw CDN).
  2. Dedupe on (protocol, host, port), merge metadata (country/asn/latency).
  3. Phase 1: concurrent connectivity check (https generate_204).
  4. Phase 2: survivors checked against REAL job targets (BA API, kimeta,
     stellenanzeigen.de, jobvector.de) -> per-target OK flags + latency.

Outputs (data/proxies/):
  validated_proxies.json  - winners with full metadata
  validated_proxies.csv   - same, flat
  fetch_stats.json        - per-source counts, error taxonomy

Usage:
  python fetch_and_test.py [--threads 600] [--timeout 4] [--skip-phase2]
                           [--phase2-limit 3000] [--max-per-source 12000]
"""
import argparse
import concurrent.futures as cf
import csv
import json
import random
import re
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
OUT_DIR = Path("/home/z/my-project/data/proxies")
PRINT_LOCK = threading.Lock()

# (repo, proto, raw_url, format, cap)
# format: plain="ip:port" | scheme="proto://ip:port" | country="ip:port:Country"
SOURCES = [
    ("monosans/proxy-list",     "json", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json", "mono", 0),
    ("TheSpeedX/PROXY-List",    "http",   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",   "plain", 0),
    ("TheSpeedX/PROXY-List",    "socks4", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt", "plain", 0),
    ("TheSpeedX/PROXY-List",    "socks5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt", "plain", 0),
    ("proxifly/free-proxy-list","http",   "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",  "scheme", 0),
    ("proxifly/free-proxy-list","https",  "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt", "scheme", 0),
    ("proxifly/free-proxy-list","socks4", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt","scheme", 0),
    ("proxifly/free-proxy-list","socks5", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt","scheme", 12000),
    ("zloi-user/hideip.me",     "http",   "https://raw.githubusercontent.com/zloi-user/hideip.me/master/http.txt",   "country", 0),
    ("zloi-user/hideip.me",     "https",  "https://raw.githubusercontent.com/zloi-user/hideip.me/master/https.txt",  "country", 0),
    ("zloi-user/hideip.me",     "socks4", "https://raw.githubusercontent.com/zloi-user/hideip.me/master/socks4.txt", "country", 0),
    ("zloi-user/hideip.me",     "socks5", "https://raw.githubusercontent.com/zloi-user/hideip.me/master/socks5.txt", "country", 0),
    ("roosterkid/openproxylist","http",   "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",  "plain", 0),
    ("roosterkid/openproxylist","socks4", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt", "plain", 0),
    ("roosterkid/openproxylist","socks5", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt", "plain", 0),
    ("Zaeem20/FREE_PROXIES_LIST","http",  "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt", "plain", 0),
    ("clarketm/proxy-list",     "http",   "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt", "plain", 0),
    ("MuRongPIG/Proxy-Master",  "http",   "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",   "plain", 2500),
    ("MuRongPIG/Proxy-Master",  "socks4", "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt", "plain", 2500),
    ("MuRongPIG/Proxy-Master",  "socks5", "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt", "plain", 2500),
]

# proto -> requests proxy scheme
SCHEME = {"http": "http", "https": "http", "socks4": "socks4", "socks5": "socks5h"}

# Phase-2 targets: (name, url, kwargs, success check)
BA_URL = ("https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
          "?was=Fachinformatiker&wo=Erlangen&umkreis=50&angebotsart=4&size=1&page=1")
TARGETS = [
    ("ba_api", BA_URL, {"headers": {**UA, "X-API-Key": "jobboerse-jobsuche"}}, "ba"),
    ("kimeta", "https://www.kimeta.de/", {"headers": UA}, "site"),
    ("stellenanzeigen", "https://www.stellenanzeigen.de/", {"headers": UA}, "site"),
    ("jobvector", "https://www.jobvector.de/", {"headers": UA}, "site"),
]


def log(msg):
    with PRINT_LOCK:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def parse_candidates(repo, proto, fmt, text):
    """Return list of (proto, host, port, country_or_None)."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "error code" in line.lower():
            continue
        host = port = country = None
        if fmt == "mono":
            continue  # handled separately
        if fmt == "scheme":
            m = re.match(r"^(https?|socks[45])://(\[?[0-9a-fA-F:.]+\]?):(\d{2,5})$", line)
            if m:
                host, port = m.group(2).strip("[]"), int(m.group(3))
        elif fmt == "country":
            parts = line.split(":")
            if len(parts) >= 2 and parts[1].isdigit():
                host, port = parts[0], int(parts[1])
                country = parts[2] if len(parts) >= 3 else None
        else:  # plain
            m = re.match(r"^(\[?[0-9a-fA-F:.]+\]?):(\d{2,5})$", line)
            if m:
                host, port = m.group(1).strip("[]"), int(m.group(2))
        if host and port and 0 < port < 65536:
            out.append((proto, host, port, country))
    return out


def fetch_pool(args):
    """Fetch all source lists -> {(proto,host,port): record}."""
    pool = {}
    src_counts = {}
    sess = requests.Session()
    sess.headers.update(UA)
    for repo, proto, url, fmt, cap in SOURCES:
        try:
            t0 = time.perf_counter()
            r = sess.get(url, timeout=25)
            dt = time.perf_counter() - t0
            if r.status_code != 200:
                src_counts[repo] = {"proto": proto, "status": r.status_code, "n": 0}
                log(f"  FETCH-FAIL {repo} [{proto}] HTTP {r.status_code}")
                continue
            if fmt == "mono":
                entries = json.loads(r.text)
                cands = []
                for e in entries:
                    p = e.get("protocol")
                    if p not in ("http", "socks4", "socks5"):
                        continue
                    geo = (e.get("geolocation") or {}).get("country") or {}
                    rec = {"proto": p, "host": e["host"], "port": e["port"],
                           "country": geo.get("iso_code"),
                           "lat_ms_upstream": int((e.get("timeout") or 0) * 1000),
                           "exit_ip": e.get("exit_ip"),
                           "asn": ((e.get("asn") or {}).get("autonomous_system_number"))}
                    cands.append(rec)
            else:
                cands = [{"proto": proto, "host": h, "port": p, "country": c,
                          "lat_ms_upstream": None, "exit_ip": None, "asn": None}
                         for (pr, h, p, c) in parse_candidates(repo, proto, fmt, r.text)]
            if cap and len(cands) > cap:
                cands = random.sample(cands, cap)
            added = 0
            for c in cands:
                key = (c["proto"], c["host"], c["port"])
                if key in pool:
                    pool[key]["sources"].add(repo)
                    if c.get("country") and not pool[key]["country"]:
                        pool[key]["country"] = c["country"]
                else:
                    pool[key] = {**c, "sources": {repo}}
                    added += 1
            src_counts[repo] = {"proto": proto, "status": 200, "n_raw": len(cands),
                                "n_new": added, "fetch_s": round(dt, 1)}
            log(f"  fetched {repo} [{proto or 'multi'}] raw={len(cands)} new={added} ({dt:.1f}s)")
        except Exception as e:
            src_counts[repo] = {"proto": proto, "error": f"{type(e).__name__}: {e}"[:120], "n": 0}
            log(f"  FETCH-FAIL {repo} [{proto}] {type(e).__name__}: {str(e)[:80]}")
    return pool, src_counts


def proxy_dict(proto, host, port):
    s = SCHEME[proto]
    return {"http": f"{s}://{host}:{port}", "https": f"{s}://{host}:{port}"}


def check_one(key, rec, url, headers, timeout, want_json_key=None):
    """Return (ok, latency_ms, http_status_or_err)."""
    t0 = time.perf_counter()
    try:
        r = requests.get(url, headers=headers, proxies=proxy_dict(*key),
                         timeout=timeout, allow_redirects=True)
        lat = int((time.perf_counter() - t0) * 1000)
        ok = 200 <= r.status_code < 300
        if ok and want_json_key:
            ok = want_json_key in r.text[:200000]
        return ok, lat, r.status_code
    except Exception as e:
        return False, None, type(e).__name__


def phase1(pool, args):
    """Connectivity check. Returns {key: rec} survivors."""
    survivors = {}
    err_types = Counter()
    keys = list(pool.keys())
    log(f"PHASE1: testing {len(keys)} unique candidates, threads={args.threads}, timeout={args.timeout}s")
    t0 = time.perf_counter()

    def work(key):
        return key, check_one(key, pool[key], "https://www.gstatic.com/generate_204",
                              UA, args.timeout)

    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.threads) as ex:
        for key, (ok, lat, status) in ex.map(work, keys):
            done += 1
            if done % 5000 == 0:
                log(f"  phase1 progress {done}/{len(keys)}, alive so far {len(survivors)}")
            if ok:
                rec = pool[key]
                rec["latency_ms"] = lat
                survivors[key] = rec
            else:
                err_types[str(status)] += 1
    log(f"PHASE1 done in {time.perf_counter()-t0:.0f}s: {len(survivors)}/{len(keys)} alive "
        f"({100*len(survivors)/max(1,len(keys)):.1f}%)")
    log(f"  error taxonomy: {dict(err_types.most_common(8))}")
    return survivors


def phase2(survivors, args):
    """Check survivors against real job targets."""
    keys = sorted(survivors.keys(), key=lambda k: survivors[k]["latency_ms"])[:args.phase2_limit]
    log(f"PHASE2: checking {len(keys)} fastest survivors against {len(TARGETS)} real targets")
    t0 = time.perf_counter()
    results = {k: {} for k in keys}

    for tname, url, kw, kind in TARGETS:
        want = "ergebnisliste" if kind == "ba" else None
        ok_n = 0

        def work(key):
            return key, check_one(key, survivors[key], url, kw.get("headers"),
                                  max(args.timeout, 8), want)

        with cf.ThreadPoolExecutor(max_workers=args.threads) as ex:
            for key, (ok, lat, status) in ex.map(work, keys):
                results[key][tname] = {"ok": ok, "latency_ms": lat, "status": str(status)}
                if ok:
                    ok_n += 1
        log(f"  {tname}: {ok_n}/{len(keys)} usable ({100*ok_n/max(1,len(keys)):.1f}%)")

    for k in keys:
        survivors[k]["targets"] = results[k]
    log(f"PHASE2 done in {time.perf_counter()-t0:.0f}s")
    return survivors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=600)
    ap.add_argument("--timeout", type=float, default=4.0)
    ap.add_argument("--max-per-source", type=int, default=12000)
    ap.add_argument("--phase2-limit", type=int, default=3000)
    ap.add_argument("--skip-phase2", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log("FETCH: downloading proxy lists")
    pool, src_counts = fetch_pool(args)
    log(f"POOL: {len(pool)} unique (proto,host,port) candidates after dedupe")

    survivors = phase1(pool, args)
    if not args.skip_phase2 and survivors:
        survivors = phase2(survivors, args)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for (proto, host, port), rec in sorted(survivors.items(), key=lambda kv: kv[1]["latency_ms"]):
        tg = rec.get("targets", {})
        rows.append({
            "protocol": proto, "host": host, "port": port,
            "latency_ms": rec["latency_ms"],
            "country": rec.get("country"), "asn": rec.get("asn"),
            "exit_ip": rec.get("exit_ip"),
            "ba_api_ok": tg.get("ba_api", {}).get("ok", False),
            "kimeta_ok": tg.get("kimeta", {}).get("ok", False),
            "stellenanzeigen_ok": tg.get("stellenanzeigen", {}).get("ok", False),
            "jobvector_ok": tg.get("jobvector", {}).get("ok", False),
            "sources": ",".join(sorted(rec["sources"])),
            "checked_at": now,
        })

    (OUT_DIR / "validated_proxies.json").write_text(json.dumps(rows, indent=1))
    with open(OUT_DIR / "validated_proxies.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["protocol"])
        w.writeheader()
        w.writerows(rows)
    stats = {"checked_at": now, "candidates": len(pool), "alive_phase1": len(survivors),
             "rows_written": len(rows), "sources": src_counts}
    (OUT_DIR / "fetch_stats.json").write_text(json.dumps(stats, indent=1, default=str))

    ba_ok = sum(1 for r in rows if r["ba_api_ok"])
    kim_ok = sum(1 for r in rows if r["kimeta_ok"])
    st_ok = sum(1 for r in rows if r["stellenanzeigen_ok"])
    jv_ok = sum(1 for r in rows if r["jobvector_ok"])
    print(f"\n===== RESULT =====")
    print(f"candidates: {len(pool)}  alive: {len(survivors)}  written: {len(rows)}")
    print(f"usable for: BA-API {ba_ok} | kimeta {kim_ok} | stellenanzeigen {st_ok} | jobvector {jv_ok}")
    by_proto = Counter(r["protocol"] for r in rows)
    print(f"by protocol: {dict(by_proto)}")
    print(f"saved -> {OUT_DIR}/validated_proxies.{{json,csv}}")


if __name__ == "__main__":
    main()
