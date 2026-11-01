"""Offline tests for config validation, net helpers and output writing."""
import json

import pytest

from proxyfetch.config import Config
from proxyfetch.errors import ConfigError
from proxyfetch.net import is_public_ipport, normalize_url, page_url
from proxyfetch.output import write_outputs
from proxyfetch.recipes import RECIPES


class TestConfig:
    def test_validated_rejects_missing_url(self):
        with pytest.raises(ConfigError):
            Config(url="").validated()

    def test_validated_rejects_tiny_budget(self):
        with pytest.raises(ConfigError):
            Config(url="https://example.com", budget_s=10).validated()

    def test_resolved_normalizes_scheme(self, tmp_path):
        cfg = Config(url="example.com/page", out_dir=tmp_path,
                     state_dir=tmp_path / "s").resolved()
        assert cfg.url == "https://example.com/page"

    def test_defaults_are_sane(self):
        cfg = Config(url="https://example.com")
        assert cfg.pages == 3 and cfg.budget_s >= 30
        assert cfg.use_browser is True and cfg.save is True


class TestNet:
    def test_normalize_adds_https(self):
        assert normalize_url("example.com") == "https://example.com"

    def test_normalize_rejects_empty(self):
        with pytest.raises(ValueError):
            normalize_url("   ")

    def test_public_ipport(self):
        assert is_public_ipport("217.114.43.142:8080")
        assert not is_public_ipport("127.0.0.1:8080")
        assert not is_public_ipport("10.0.0.1:80")
        assert not is_public_ipport("not-a-proxy")

    def test_page_url_appends(self):
        assert page_url("https://x.de/lst?a=1", 1) == "https://x.de/lst?a=1"
        assert page_url("https://x.de/lst?a=1", 2) == "https://x.de/lst?a=1&page=2"
        assert page_url("https://x.de/lst", 3) == "https://x.de/lst?page=3"


class TestOutput:
    def test_write_outputs_json_and_csv(self, tmp_path):
        recipe = RECIPES["autoscout24"]
        payload = {"schema": "proxyfetch.result/v1", "ok": True, "meta": {}}
        items = [{"title": "A", "price_eur": 100, "km": 5000, "year": "2020",
                  "version": "v", "ps": "110", "fuel": "B", "gear": "M",
                  "seller": "D", "city": "Berlin", "url": "https://x/1"},
                 {"title": "B", "price_eur": None, "km": None, "year": "",
                  "version": "", "ps": "", "fuel": "", "gear": "",
                  "seller": "", "city": "", "url": "https://x/2"}]
        files = write_outputs(items, payload, tmp_path, "demo", recipe)
        assert files["json"].endswith(".json") and files["csv"].endswith(".csv")

        doc = json.loads(open(files["json"], encoding="utf-8").read())
        assert doc["count"] == 2 and len(doc["items"]) == 2

        csv_text = open(files["csv"], encoding="utf-8-sig").read()
        lines = csv_text.strip().splitlines()
        assert lines[0].startswith("rank;title")
        assert ";100;" in lines[1]
        # None price sorts last, empty cell in CSV
        assert lines[2].endswith("https://x/2")

    def test_no_tmp_files_left_behind(self, tmp_path):
        recipe = RECIPES["generic"]
        write_outputs([{"id": "u", "title": "t", "url": "u"}],
                      {"meta": {}}, tmp_path, "demo", recipe)
        assert not list(tmp_path.glob("*.tmp"))
