"""Bot-challenge detection, honest probe rejection and the IS24 recipe.

Regression ground for the Immobilienscout24 incident: its AWS-WAF
challenge page ("Ich bin kein Roboter") parsed as a perfectly good
generic item, which let 14/19 proxies "verify" against a wall and made
the pipeline spin until timeout. These tests pin the fix at every layer.
"""
from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from proxyfetch import asynchttp, recipes

FIXTURES = Path(__file__).parent / "fixtures"
IS24_CHALLENGE = (FIXTURES / "is24_challenge.html").read_text(encoding="utf-8")


def _fake_listing(i: int) -> dict:
    return {"id": str(100000 + i), "exposeId": f"EX{i}", "title": f"Wohnung {i}",
            "price": {"value": 900 + i * 10, "currency": "EUR"},
            "numberOfRooms": 2 + i * 0.5, "livingArea": 55 + i,
            "address": {"city": "Berlin", "zipCode": "10" + f"{i:03d}"}}


def _is24_page(listings: list[dict]) -> str:
    """Minimal IS24-style page: __NEXT_DATA__ with nested listing array + noise."""
    payload = {
        "props": {"pageProps": {
            "ga": {"page": "Suche", "nav": [{"label": n, "id": n} for n in range(20)]},
            "searchResult": {"resultItems": listings},
        }},
    }
    return ("<html><head><title>Wohnung mieten in Berlin - ImmobilienScout24"
            "</title></head><body>"
            f'<script id="__NEXT_DATA__" type="application/json">'
            f"{json.dumps(payload)}</script></body></html>")


# ---------------------------------------------------------- challenge_kind
def test_real_is24_challenge_is_aws_waf():
    assert recipes.challenge_kind(IS24_CHALLENGE) == "aws-waf"


def test_challenge_vendor_body_markers():
    dd = ('<html><script src="https://geo.captcha-delivery.com/captcha.js">'
          "</script><body>x</body></html>")
    cf = "<html>cfg = {cf_chl_opt: 1}; please wait</html>"
    px = '<html><div class="px-captcha">Press &amp; Hold to confirm</div></html>'
    assert recipes.challenge_kind(dd) == "datadome"
    assert recipes.challenge_kind(cf) == "cloudflare"
    assert recipes.challenge_kind(px) == "perimeterx"


def test_challenge_title_markers():
    page = "<html><head><title>Just a moment...</title></head><body>loading</body></html>"
    assert recipes.challenge_kind(page) == "challenge"
    robot = "<html><head><title>Are you a robot? - X</title></head><body>y</body></html>"
    assert recipes.challenge_kind(robot) == "challenge"


def test_legit_pages_are_not_challenges():
    # the AS24 lesson: legit pages EMBED datadome -- that is not a challenge
    as24 = ("<html><head><title>Gebrauchtwagen - AutoScout24</title></head>"
            "<body><script src='https://js.datadome.co/tag.js'></script>"
            "<article>listing</article></body></html>")
    plain = "<html><head><title>Cool gadgets</title></head><body><table><tr><td>a</td></tr></table></body></html>"
    assert recipes.challenge_kind(as24) is None
    assert recipes.challenge_kind(plain) is None
    assert recipes.challenge_kind("") is None


def test_verify_rejects_challenge_on_every_recipe():
    auto = recipes.resolve("auto", "https://anywhere.example/x")
    css = recipes.resolve("auto", "https://x.example/", css="article",
                          fields={"t": "h2::text"})
    for recipe in (recipes.RECIPES["generic"], recipes.RECIPES["autoscout24"],
                   recipes.RECIPES["immobilienscout24"], auto, css):
        assert recipe.verify(IS24_CHALLENGE) is False, recipe.name


def test_verify_still_accepts_legit_content():
    page = _is24_page([_fake_listing(i) for i in range(5)])
    assert recipes.RECIPES["immobilienscout24"].verify(page) is True
    assert recipes.RECIPES["generic"].verify(
        "<html><title>ok</title><body>" + "word " * 50 + "</body></html>") is True


# ------------------------------------------------------------ IS24 recipe
def test_is24_recipe_auto_detection_by_host():
    r = recipes.resolve("auto", "https://www.immobilienscout24.de/Suche/de/berlin/wohnung-mieten")
    assert r.name == "immobilienscout24"


def test_is24_parser_extracts_listings():
    listings = [_fake_listing(i) for i in range(4)]
    items = recipes.parse_immobilienscout24(
        _is24_page(listings), "https://www.immobilienscout24.de/Suche/de/berlin/wohnung-mieten")
    assert len(items) == 4
    first = items[0]
    assert first["id"] == "EX0"  # exposeId preferred (IS24's real identifier)
    assert first["title"] == "Wohnung 0"
    assert first["price_eur"] == 900
    assert first["rooms"] == 2.0
    assert first["area_m2"] == 55
    assert first["city"] == "Berlin"
    assert first["url"].endswith("/expose/EX0")
    assert first["url"].startswith("https://www.immobilienscout24.de")


def test_is24_parser_prefers_listing_array_over_noise():
    """A smaller listing array must beat a big non-listing array."""
    payload = {
        "props": {"pageProps": {
            "seo": [{"text": f"t{i}", "link": "/l{i}"} for i in range(30)],
            "results": [_fake_listing(i) for i in range(3)],
        }},
    }
    html = ("<html><script id=\"__NEXT_DATA__\" type=\"application/json\">"
            + json.dumps(payload) + "</script></html>")
    items = recipes.parse_immobilienscout24(
        html, "https://www.immobilienscout24.de/Suche/x")
    assert len(items) == 3
    assert items[0]["price_eur"] == 900


def test_is24_parser_no_next_data_no_crash():
    assert recipes.parse_immobilienscout24("<html>nothing</html>", "https://x.de/") == []
    bad = ('<script id="__NEXT_DATA__">not json</script>')
    assert recipes.parse_immobilienscout24(bad, "https://x.de/") == []
    empty = _is24_page([])
    assert recipes.parse_immobilienscout24(empty, "https://x.de/") == []


def test_is24_challenge_page_parses_nothing():
    """Even if something routed a challenge body to the parser: no items."""
    assert recipes.parse_immobilienscout24(IS24_CHALLENGE, "https://x.de/") == []


# ------------------------------------------------- async engine: 4xx probes
@pytest.fixture()
def wl_server():
    """Server that serves OK content but answers /401 with HTTP 401."""

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/401":
                body = b"<html><body>Example Domain</body></html>"
                self.send_response(401)  # body passes verifier -- status must not
            else:
                body = b"<html><body>Example Domain</body></html>"
                self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


def test_asynchttp_rejects_4xx_even_with_passing_body(wl_server):
    """Pin the IS24 bug: a 401 challenge body must never verify a proxy."""
    out = asynchttp.check(["direct"], wl_server + "401", timeout=5,
                          read_limit=100, verifier=lambda b: "Example Domain" in b)
    assert out == []
    ok = asynchttp.check(["direct"], wl_server, timeout=5,
                         read_limit=100, verifier=lambda b: "Example Domain" in b)
    assert ok == [("direct", ok[0][1])]


def test_threads_probe_rejects_4xx(wl_server):
    """Thread engine semantics: urllib raises HTTPError on 401 -> no pass."""
    from proxyfetch import supply
    from proxyfetch.config import Config
    spec = supply.ProbeSpec(url=wl_server + "401", verifier=lambda b: True,
                            timeout=5, read_limit=100)
    out = supply.run_check(["direct"], supply._probe_threads(spec), 2, _Quiet(), "t")
    assert out == []


class _Quiet:  # minimal logger stand-in for run_check
    def info(self, *a, **k):
        pass
