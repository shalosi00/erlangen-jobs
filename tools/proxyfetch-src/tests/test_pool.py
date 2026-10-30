"""Offline tests for the proxy pool: cache, TTL, migration, strike tracking."""
import json
import time

import pytest

from proxyfetch.pool import ProxyPool


@pytest.fixture
def state(tmp_path):
    return tmp_path / "state"


class TestCache:
    def test_roundtrip(self, state):
        pool = ProxyPool(state)
        pool.record(["1.1.1.1:80"], site="example.com", latency={"1.1.1.1:80": 0.5})
        again = ProxyPool(state)  # new instance reads from disk
        assert again.cached_for_site("example.com") == ["1.1.1.1:80"]

    def test_site_scoping(self, state):
        pool = ProxyPool(state)
        pool.record(["1.1.1.1:80"], site="a.com")
        assert pool.cached_for_site("b.com") == []

    def test_fresh_flag_ignores_cache(self, state):
        pool = ProxyPool(state)
        pool.record(["1.1.1.1:80"], site="a.com")
        assert pool.cached_for_site("a.com", fresh=True) == []

    def test_ttl_expiry(self, state):
        pool = ProxyPool(state, ttl_s=10)
        pool.record(["1.1.1.1:80"], site="a.com")
        # backdate the entry
        data = json.loads((state / "winners.json").read_text())
        data["proxies"]["1.1.1.1:80"]["verified_at"] = int(time.time()) - 3600
        (state / "winners.json").write_text(json.dumps(data))
        pool2 = ProxyPool(state, ttl_s=10)
        assert pool2.cached_for_site("a.com") == []

    def test_legacy_format_migration(self, state):
        # legacy one-off script format: {"proxies": {p: {"target": site, ...}}}
        state.mkdir(parents=True)
        legacy = {"proxies": {"2.2.2.2:8080": {
            "target": "www.autoscout24.de", "verified_at": int(time.time()),
            "latency": 1.2, "browser_verified": True}}}
        (state / "winners.json").write_text(json.dumps(legacy))
        pool = ProxyPool(state)
        assert pool.cached_for_site("www.autoscout24.de") == ["2.2.2.2:8080"]

    def test_corrupt_cache_does_not_crash(self, state):
        state.mkdir(parents=True)
        (state / "winners.json").write_text("{not json!!")
        pool = ProxyPool(state)
        assert pool.cached_for_site("a.com") == []

    def test_localhost_never_recorded(self, state):
        pool = ProxyPool(state)
        pool.record(["127.0.0.1:18080"], site="a.com")
        assert (state / "winners.json").read_text().count("127.0.0.1") == 0


class TestStrikes:
    def test_two_strikes_bench_proxy(self, state):
        pool = ProxyPool(state, max_fails=2)
        pool.mark("p", False)
        assert pool.is_dead("p") is False
        pool.mark("p", False)
        assert pool.is_dead("p") is True

    def test_success_resets_strikes(self, state):
        pool = ProxyPool(state, max_fails=2)
        pool.mark("p", False)
        pool.mark("p", True)
        pool.mark("p", False)
        assert pool.is_dead("p") is False

    def test_used_tracking(self, state):
        pool = ProxyPool(state)
        pool.mark("p", True)
        assert pool.used == {"p"}
