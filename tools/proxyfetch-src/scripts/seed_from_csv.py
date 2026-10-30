#!/usr/bin/env python3
"""Seed proxyfetch's winner cache from an EXTERNAL pre-validated proxy CSV.

Useful when you maintain your own validated pool elsewhere (e.g. a daily
pipeline that benchmarks proxies against specific target sites) and want
proxyfetch to reuse it instead of harvesting public lists from scratch.

proxyfetch re-verifies every cached entry at run start (cache-reverify) and
drops dead ones, so stale rows are harmless -- seed freely.

Expected CSV columns: protocol, host, port  (protocol must be http/https --
the aiohttp engine cannot speak SOCKS).  Per-site columns like ``kimeta_ok``
are optional; every truthy value maps that proxy to the site given via
--map COL=HOST (repeatable).  With no --map, proxies are seeded for --site.

Usage:
  # seed for one site
  python3 scripts/seed_from_csv.py proxies.csv --site www.kimeta.de

  # map boolean columns to site hosts (repeatable)
  python3 scripts/seed_from_csv.py proxies.csv \
      --map kimeta_ok=www.kimeta.de --map stellenanzeigen_ok=www.stellenanzeigen.de
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

SCHEMA = "proxyfetch.winners/v1"


def default_state_dir() -> Path:
    import os
    return Path(os.environ.get("PROXYFETCH_STATE_DIR", "~/.proxyfetch")).expanduser()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", help="CSV with protocol,host,port columns")
    ap.add_argument("--site", help="seed all proxies for this one site host")
    ap.add_argument("--map", action="append", default=[],
                    metavar="COL=HOST", help="map truthy CSV column COL to site HOST")
    ap.add_argument("--state-dir", type=Path, default=None,
                    help="proxyfetch state dir (default ~/.proxyfetch)")
    ap.add_argument("--clear", action="store_true", help="replace the whole cache")
    args = ap.parse_args()

    if not args.site and not args.map:
        ap.error("pass --site HOST and/or at least one --map COL=HOST")

    now = int(time.time())
    state_dir = args.state_dir or default_state_dir()
    path = state_dir / "winners.json"
    data: dict = {"schema": SCHEMA, "proxies": {}}
    if path.exists() and not args.clear:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded.get("proxies"), dict):
                data = loaded
        except Exception:
            pass

    store = data.setdefault("proxies", {})
    seeded = 0
    with open(args.csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            proto = (row.get("protocol") or "").strip().lower()
            if proto not in ("http", "https"):
                continue  # aiohttp engine: http(s) proxies only
            host, port = (row.get("host") or "").strip(), (row.get("port") or "").strip()
            if not host or not port:
                continue
            key = f"http://{host}:{port}"
            targets: dict[str, float] = {}
            if args.site:
                targets[args.site] = 1.0
            for m in args.map:
                col, _, site = m.partition("=")
                if str(row.get(col, "")).strip().lower() in ("true", "1", "yes"):
                    try:
                        targets[site] = float(row.get("latency_ms") or 1000) / 1000.0
                    except ValueError:
                        targets[site] = 1.0
            for site, lat in targets.items():
                e = dict(store.get(key, {}).get(site) or {})
                e.update({"site": site, "target": site, "verified_at": now,
                          "latency": lat, "browser_verified": e.get("browser_verified", False),
                          "successes": e.get("successes", 0), "failures": e.get("failures", 0)})
                store.setdefault(key, {})[site] = e
                seeded += 1

    data["updated_at"] = now
    state_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    print(f"seeded {seeded} site-entries across {len(store)} proxies -> {path}")


if __name__ == "__main__":
    main()
