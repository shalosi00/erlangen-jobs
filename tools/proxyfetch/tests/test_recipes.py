"""Offline tests for recipes: AS24 parsing, generic parsing, verify/resolve."""
import json

from proxyfetch.recipes import RECIPES, parse_autoscout24, parse_generic, resolve


def _as24_html(listings: list[dict]) -> str:
    payload = {"props": {"pageProps": {"listings": listings}}}
    return ("<html><head><title>AutoScout24 Europe</title></head><body>"
            f'<script id="__NEXT_DATA__" type="application/json">'
            f"{json.dumps(payload)}</script></body></html>")


def _listing(idx: int, **over):
    base = {
        "id": f"idx-{idx}",
        "url": f"/details/idx-{idx}.html",
        "vehicle": {"title": f"Test Car {idx}", "make": "Dacia",
                    "model": "Jogger", "fuel": "Benzin",
                    "transmission": "Manuell"},
        "vehicleDetails": [
            {"iconName": "mileage_odometer", "data": {"value": "12.000 km"}},
            {"iconName": "calendar", "data": {"value": "03/2023"}},
            {"iconName": "speedometer", "data": {"value": "(110 PS)"}},
        ],
        "price": {"priceRaw": 15000 + idx * 100},
        "seller": {"type": "D", "cityName": "Berlin"},
        "location": {"zip": "10115", "city": "Berlin"},
    }
    base.update(over)
    return base


AS24 = RECIPES["autoscout24"]


class TestAutoscout24:
    def test_parse_full_listing(self):
        items = parse_autoscout24(_as24_html([_listing(0)]), "https://www.autoscout24.de/lst/x")
        assert len(items) == 1
        it = items[0]
        assert it["id"] == "idx-0"
        assert it["title"] == "Test Car 0"
        assert it["price_eur"] == 15000
        assert it["km"] == 12000
        assert it["year"] == "03/2023"
        assert it["ps"] == "110 PS"
        assert it["city"] == "10115 Berlin"
        assert it["url"] == "https://www.autoscout24.de/details/idx-0.html"

    def test_parse_location_dict_fallback(self):
        html = _as24_html([_listing(1, seller={"type": "P"})])  # no seller.cityName
        it = parse_autoscout24(html, "https://www.autoscout24.de/lst/x")[0]
        assert it["city"] == "10115 Berlin"

    def test_malformed_listing_skipped_not_fatal(self):
        html = _as24_html([{"garbage": True}, _listing(2)])
        items = parse_autoscout24(html, "https://www.autoscout24.de/lst/x")
        assert [i["id"] for i in items] == ["idx-2"]

    def test_no_payload_returns_empty(self):
        assert parse_autoscout24("<html><body>hi</body></html>", "https://x") == []

    def test_verify_accepts_real_and_rejects_block(self):
        real = _as24_html([_listing(0)]) + '<script src="https://js.datadome.co/tag.js">'
        assert AS24.verify(real) is True  # datadome tag must NOT cause rejection
        blocked = "<html><title>Diese Seite ist für dich nicht verfügbar</title></html>"
        assert AS24.verify(blocked) is False

    def test_sort_key_price_last_for_none(self):
        items = [{"price_eur": None}, {"price_eur": 100}, {"price_eur": 50}]
        items.sort(key=AS24.sort_key)
        assert [i["price_eur"] for i in items] == [50, 100, None]


GENERIC = RECIPES["generic"]


class TestGeneric:
    def test_parse_title_meta_jsonld(self):
        html = ("<html><head><title>Page</title>"
                '<meta name="description" content="A demo page">'
                '<script type="application/ld+json">{"@type":"Product"}</script>'
                "</head><body><h1>Hello</h1></body></html>")
        items = parse_generic(html, "https://example.com/x")
        assert len(items) == 1
        assert items[0]["title"] == "Hello"
        assert items[0]["description"] == "A demo page"
        assert items[0]["jsonld"] == [{"@type": "Product"}]

    def test_parse_empty_page_returns_empty(self):
        assert parse_generic("<html></html>", "https://example.com") == []

    def test_verify_block_markers(self):
        assert GENERIC.verify("<html>access denied for you</html>" + "x" * 300) is False
        assert GENERIC.verify("<html><title>t</title>" + "y" * 300) is True


class TestResolve:
    def test_auto_detects_autoscout24(self):
        assert resolve("auto", "https://www.autoscout24.de/lst/x").name == "autoscout24"
        assert resolve("auto", "https://www.autoscout24.it/lst/x").name == "autoscout24"

    def test_auto_falls_back_to_generic(self):
        # 0.3.0: auto for unknown hosts resolves to the structured-first
        # chain (table -> page meta -> JSON) instead of plain generic.
        assert resolve("auto", "https://example.com/page").name == "auto-any"

    def test_unknown_recipe_raises_config_error(self):
        import pytest
        from proxyfetch.errors import ConfigError
        with pytest.raises(ConfigError):
            resolve("nope", "https://example.com")
