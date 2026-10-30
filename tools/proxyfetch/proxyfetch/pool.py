"""Proxy pool: persistent winner cache + per-run health tracking.

Persistence layer (``<state_dir>/winners.json``) survives across runs so a
warm start re-verifies only a handful of proxies instead of harvesting from
scratch. The format is versioned and transparently migrates the legacy
one-off script format.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

SCHEMA = "proxyfetch.pool/v1"


class ProxyPool:
    """Tracks which proxies work for a given site, in memory and on disk.

    * persistent layer: ``proxies`` dict -> verified winners with metadata
    * runtime layer:    failure strikes / success bookkeeping for this run
    """

    def __init__(self, state_dir: Path | str, *, ttl_s: int = 3 * 3600,
                 max_fails: int = 2) -> None:
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / "winners.json"
        self.ttl_s = ttl_s
        self.max_fails = max_fails
        self._data: dict[str, Any] = {"schema": SCHEMA, "proxies": {}}
        self._fails: dict[str, int] = {}
        self._used: set[str] = set()
        self._wins: set[str] = set()
        self._load()

    # ------------------------------------------------------------ persistence
    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data.get("proxies"), dict):
                return
            self._data = data
            self._data.setdefault("schema", "legacy")
        except FileNotFoundError:
            pass
        except Exception:
            # Corrupt cache must never kill a run: start clean, keep the file
            # around for forensics.
            try:
                os.replace(self.path, self.path.with_suffix(".json.corrupt"))
            except OSError:
                pass

    def save(self) -> None:
        """Atomic write -- a killed process can never corrupt the cache."""
        self._data["updated_at"] = int(time.time())
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    @staticmethod
    def _migrate_entry(entry: dict) -> dict:
        """Legacy format used ``target`` as the cache key for the site."""
        if "site" not in entry and "target" in entry:
            entry["site"] = entry["target"]
        entry.setdefault("browser_verified", False)
        entry.setdefault("latency", 99.0)
        entry.setdefault("successes", 0)
        entry.setdefault("failures", 0)
        return entry

    # ------------------------------------------------------------ cache API
    def cached_for_site(self, site: str, *, fresh: bool = False) -> list[str]:
        """Cached winners for ``site``, best-first; empty when --fresh or TTL expired."""
        if fresh:
            return []
        now = time.time()
        entries: list[tuple[str, dict]] = []
        for proxy, raw in self._data.get("proxies", {}).items():
            entry = self._migrate_entry(dict(raw))
            if entry.get("site") != site:
                continue
            if now - entry.get("verified_at", 0) > self.ttl_s:
                continue
            entries.append((proxy, entry))
        entries.sort(key=lambda kv: (not kv[1].get("browser_verified", False),
                                     kv[1].get("latency", 99.0)))
        return [p for p, _ in entries]

    def record(self, proxies, *, site: str, target: str | None = None,
               browser_verified: bool = False, latency: float | dict | None = None) -> None:
        """Persist winners (idempotent; refreshes verified_at)."""
        if not proxies:
            return
        store: dict = self._data.setdefault("proxies", {})
        now = int(time.time())
        for p in proxies:
            if p.startswith("127."):        # local rotator endpoint, not a real proxy
                continue
            prev = self._migrate_entry(dict(store.get(p, {})))
            lat = latency.get(p, prev.get("latency", 0)) if isinstance(latency, dict) \
                else (latency if isinstance(latency, (int, float)) else prev.get("latency", 0))
            entry = {
                "site": site,
                "target": target or prev.get("target", site),
                "verified_at": now,
                "latency": lat,
                "browser_verified": browser_verified or prev.get("browser_verified", False),
                "successes": prev.get("successes", 0) + (1 if p in self._wins else 0),
                "failures": self._fails.get(p, 0),
            }
            store[p] = entry
        self.save()

    # ------------------------------------------------------------ runtime API
    def mark(self, proxy: str, ok: bool) -> None:
        """Record an attempt result; bench the proxy after ``max_fails`` strikes."""
        if ok:
            self._fails[proxy] = 0
            self._used.add(proxy)
            self._wins.add(proxy)
        else:
            self._fails[proxy] = self._fails.get(proxy, 0) + 1

    def is_dead(self, proxy: str) -> bool:
        return self._fails.get(proxy, 0) >= self.max_fails

    @property
    def used(self) -> set[str]:
        return set(self._used)

    def stats(self) -> dict:
        return {
            "cached_total": len(self._data.get("proxies", {})),
            "used_this_run": len(self._used),
            "succeeded_this_run": len(self._wins),
        }
