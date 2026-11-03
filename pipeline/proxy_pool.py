"""Minimal file-backed proxy pool — serves VALIDATED free proxies to WAF-blocked sources.

Data file: data/proxies/validated_proxies.json (written by scripts/proxy_tools/fetch_and_test.py,
which fetches 8 vetted GitHub proxy repos, dedupes, then two-phase tests: generic connectivity
+ real targets incl. kimeta/stellenanzeigen/BA API).

Usage inside a source:
    from pipeline.proxy_pool import pick, mark_dead
    entry = pick("kimeta")            # -> {"protocol","host","port","proxies",...} or None
    r = requests.get(url, proxies=entry["proxies"], ...)
    on connection failure: mark_dead(entry)

CLI:
    python -m pipeline.proxy_pool stats
    python -m pipeline.proxy_pool refresh [--threads 700]

Free proxies rot fast: refresh at most every few hours; expect 20-60% of yesterday's
validated proxies to be dead at any time — pick() rotates, mark_dead() prunes.
A corrupt/unreadable data file is LOGGED and treated as an empty pool (never a crash).
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from pipeline import logutil

log = logutil.get("proxy_pool")

PROJ = Path(__file__).resolve().parent.parent
DATA_FILE = PROJ / "data" / "proxies" / "validated_proxies.json"
TESTER = PROJ / "scripts" / "proxy_tools" / "fetch_and_test.py"

_lock = threading.Lock()
_rows: list[dict] = []
_rr: dict[str, int] = {}
_dead: list[str] = []
_load_failed = False

TARGETS = ("ba_api", "kimeta", "stellenanzeigen", "jobvector")


def _load() -> None:
    global _rows, _load_failed
    with _lock:
        if _rows or not DATA_FILE.exists():
            return
        try:
            rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                raise ValueError(f"expected a JSON list, got {type(rows).__name__}")
            _rows = rows
            log.info("proxy pool loaded: %d validated proxies from %s",
                     len(_rows), DATA_FILE.name)
        except (OSError, ValueError) as e:
            # corrupt data file must degrade to an empty pool, never a crash
            _rows = []
            _load_failed = True
            log.warning("proxy pool data file unreadable (%s: %s) -- "
                        "treating as empty; refresh with: "
                        "python -m pipeline.proxy_pool refresh",
                        type(e).__name__, e)


def _key(row: dict) -> str:
    return f"{row['protocol']}://{row['host']}:{row['port']}"


def pick(target: str) -> dict | None:
    """Best alive proxy validated for `target`, round-robin. None if pool empty/unavailable."""
    _load()
    with _lock:
        cand = [r for r in _rows if r.get(f"{target}_ok")]
        if not cand:                      # graceful fallback: any alive proxy
            cand = _rows
            if cand:
                log.debug("no %s-validated proxy alive -- falling back to any "
                          "alive proxy (%d)", target, len(cand))
        if not cand:
            return None
        i = _rr.get(target, 0) % len(cand)
        _rr[target] = i + 1
        row = cand[i]
        scheme = {"http": "http", "https": "http", "socks4": "socks4", "socks5": "socks5h"}[row["protocol"]]
        px = {"http": f"{scheme}://{row['host']}:{row['port']}",
              "https": f"{scheme}://{row['host']}:{row['port']}"}
        return {**row, "proxies": px}


def mark_dead(entry: dict) -> None:
    """Remove a dead proxy from the in-memory pool (persists to dead.jsonl for stats)."""
    global _rows
    with _lock:
        k = _key(entry)
        _rows = [r for r in _rows if _key(r) != k]
        _dead.append(k)
        log.debug("marked dead: %s (%d proxies left in pool)", k, len(_rows))
        dead_file = DATA_FILE.parent / "dead.jsonl"
        try:
            with open(dead_file, "a") as f:
                f.write(k + "\n")
        except OSError as e:
            log.warning("cannot persist dead-proxy log %s (%s)", dead_file, e)


def stats() -> dict:
    _load()
    with _lock:
        by_proto: dict[str, int] = {}
        per_target = {}
        for t in TARGETS:
            per_target[t] = sum(1 for r in _rows if r.get(f"{t}_ok"))
        for r in _rows:
            by_proto[r["protocol"]] = by_proto.get(r["protocol"], 0) + 1
        out = {"alive": len(_rows), "by_protocol": by_proto,
               "per_target": per_target, "dead_marked": len(_dead),
               "load_failed": _load_failed,
               "data_file": str(DATA_FILE)}
        # F12: staleness signal — kimeta degrades silently as the pool rots
        try:
            age_h = (time.time() - DATA_FILE.stat().st_mtime) / 3600.0
            out["age_hours"] = round(age_h, 1)
        except OSError:
            out["age_hours"] = None
        return out


def refresh(threads: int = 700) -> int:
    """Re-run fetch+validate, then reload the pool. Returns subprocess exit code."""
    cmd = [sys.executable, str(TESTER), "--threads", str(threads)]
    log.info("refreshing proxy pool: %s", " ".join(cmd))
    rc = subprocess.call(cmd)
    with _lock:
        _rows = []
        _load_failed = False
    _load()
    log.info("refresh finished rc=%d, pool now holds %d proxies", rc, len(_rows))
    return rc


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        threads = int(sys.argv[sys.argv.index("--threads") + 1]) if "--threads" in sys.argv else 700
        rc = refresh(threads)
        print(f"refresh finished rc={rc}")
    else:
        s = stats()
        print(json.dumps(s, indent=1))
