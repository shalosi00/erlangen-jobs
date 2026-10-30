#!/usr/bin/env python3
"""Seed proxyfetch's winner cache (~/.proxyfetch/winners.json) from our
validated proxy pool (data/proxies/validated_proxies.csv).

proxyfetch only speaks http:// proxies (aiohttp engine, no SOCKS), so we
seed the http-protocol rows. Entries are written with verified_at=now and
site=host-of-URL for every target site the proxy passed in our own checks;
proxyfetch re-verifies the cache at run start (check_batch 'cache-reverify')
and drops dead entries automatically, so stale rows are harmless.

Usage:
  python3 scripts/seed_proxyfetch.py                # seed all http proxies
  python3 scripts/seed_proxyfetch.py --clear        # wipe cache first
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "proxies" / "validated_proxies.csv"
STATE_DIR = Path.home() / ".proxyfetch"
WINNERS = STATE_DIR / "winners.json"

# site-key candidates per validated_proxies.csv column
SITE_COLS = {
    "ba_api_ok": "rest.arbeitsagentur.de",
    "kimeta_ok": "www.kimeta.de",
    "stellenanzeigen_ok": "www.stellenanzeigen.de",
    "jobvector_ok": "www.jobvector.de",
}


def host_of(url: str) -> str:
    return urlsplit(url).netloc or url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true", help="wipe existing cache")
    args = ap.parse_args()

    now = int(time.time())
    data: dict = {"schema": "proxyfetch.winners/v1", "proxies": {}}

    if WINNERS.exists() and not args.clear:
        try:
            loaded = json.loads(WINNERS.read_text(encoding="utf-8"))
            if isinstance(loaded.get("proxies"), dict):
                data = loaded
        except Exception:
            pass  # start clean; corrupt file handled by proxyfetch too

    store = data.setdefault("proxies", {})
    seeded = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("protocol") != "http":
                continue  # proxyfetch/aiohttp engine: http proxies only
            host, port = row.get("host", "").strip(), row.get("port", "").strip()
            if not host or not port:
                continue
            key = f"http://{host}:{port}"
            entry = store.get(key) or {}
            for col, site in SITE_COLS.items():
                if str(row.get(col, "")).lower() == "true":
                    e = dict(entry.get(site) or {})
                    e.update({
                        "site": site,
                        "target": site,
                        "verified_at": now,
                        "latency": float(row["latency_ms"]) / 1000.0
                        if row.get("latency_ms") else 1.0,
                        "browser_verified": e.get("browser_verified", False),
                        "successes": e.get("successes", 0),
                        "failures": e.get("failures", 0),
                    })
                    store.setdefault(key, {})[site] = e
                    seeded += 1

    data["updated_at"] = now
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = WINNERS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(WINNERS)
    print(f"seeded {seeded} site-entries across {len(store)} http proxies -> {WINNERS}")


if __name__ == "__main__":
    main()
