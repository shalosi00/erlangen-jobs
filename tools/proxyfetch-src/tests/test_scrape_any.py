"""Offline tests: universal extraction (css/json/table/auto/custom),
pagination templates, dynamic CSV columns, direct-first probe, CLI flags."""
from __future__ import annotations

import json

import pytest

from proxyfetch import cli, errors, net, output, recipes, supply
from proxyfetch.config import Config
from proxyfetch.logutil import Logger

HTML_LIST = """
<html><head><title>Books</title></head><body>
<article class="product">
  <h3><a href="/catalogue/book-1.html" title="A Light in the Attic">Book One</a></h3>
  <p class="price_color">£51.77</p>
  <p class="rating">Three</p>
</article>
<article class="product">
  <h3><a href="/catalogue/book-2.html" title="Tipping the Velvet">Book Two</a></h3>
  <p class="price_color">£23.46</p>
  <p class="rating">One</p>
</article>
</body></html>
"""

HTML_TABLE = """
<html><head><title>Repo stats</title></head><body>
<table>
  <tr><th>Name</th><th>Stars</th><th>Language</th></tr>
  <tr><td>proxyfetch</td><td>42</td><td>Python</td></tr>
  <tr><td>other</td><td>7</td><td>Go</td></tr>
</table>
<table><tr><td>tiny</td></tr></table>
</body></html>
"""

JSON_BODY = json.dumps({
    "meta": {"total": 3},
    "data": {"items": [
        {"id": 1, "name": "first", "url": "/a/1", "extra": {"k": 1}},
        {"id": 2, "name": "second", "url": "https://x.com/a/2"},
    ]},
})


def _url(html_url="https://x.com/list"):
    return html_url


# ------------------------------------------------------------------ css
def test_parse_css_fields_text_attr():
    items = recipes.parse_css(HTML_LIST, "https://books.toscrape.com/",
                              "article.product",
                              {"title": "h3 a::attr(title)",
                               "price": ".price_color::text",
                               "url": "h3 a::attr(href)",
                               "rating": ".rating::text"})
    assert items[0] == {"title": "A Light in the Attic", "price": "£51.77",
                        "url": "https://books.toscrape.com/catalogue/book-1.html",
                        "rating": "Three"}
    assert items[1]["price"] == "£23.46"


def test_parse_css_default_field_is_element_text():
    items = recipes.parse_css(HTML_LIST, "https://x.com/", "h3 a")
    assert [i["text"] for i in items] == ["Book One", "Book Two"]


def test_parse_css_missing_field_is_empty_string():
    items = recipes.parse_css(HTML_LIST, "https://x.com/", "article.product",
                              {"title": "h3 a::attr(title)",
                               "nope": ".does-not-exist::text"})
    assert items[0]["nope"] == "" and items[0]["title"] == "A Light in the Attic"


def test_parse_css_all_empty_items_dropped():
    items = recipes.parse_css(HTML_LIST, "https://x.com/", "article.product",
                              {"nope": ".does-not-exist::text"})
    assert items == []


# ------------------------------------------------------------------ json
def test_parse_json_dot_path():
    items = recipes.parse_json_items(JSON_BODY, "https://api.x.com/", "data.items")
    assert len(items) == 2
    assert items[0]["name"] == "first"
    assert items[0]["url"] == "https://api.x.com/a/1"      # relative -> absolute
    assert json.loads(items[0]["extra"]) == {"k": 1}        # nested -> json string
    assert items[1]["url"] == "https://x.com/a/2"           # absolute untouched


def test_parse_json_auto_largest_array():
    items = recipes.parse_json_items(JSON_BODY, "https://api.x.com/")
    assert len(items) == 2 and items[1]["name"] == "second"


def test_parse_json_top_level_array_and_scalar_wrap():
    body = json.dumps([{"id": 9}, "just-a-string"])
    items = recipes.parse_json_items(body, "https://x.com/")
    assert items[0]["id"] == 9 and items[1] == {"value": "just-a-string"}


def test_parse_json_bad_body_returns_empty():
    assert recipes.parse_json_items("<html>not json</html>", "https://x.com/") == []


# ------------------------------------------------------------------ table
def test_parse_table_header_keys_and_largest_pick():
    items = recipes.parse_table(HTML_TABLE, "https://x.com/")
    assert items == [{"name": "proxyfetch", "stars": "42", "language": "Python"},
                     {"name": "other", "stars": "7", "language": "Go"}]


def test_parse_table_index_selection():
    # table 2 has a single row -> not enough structure
    assert recipes.parse_table(HTML_TABLE, "https://x.com/", table_index=2) == []
    assert len(recipes.parse_table(HTML_TABLE, "https://x.com/", table_index=1)) == 2


# ------------------------------------------------------------------ auto
def test_auto_prefers_table_over_meta():
    r = recipes.resolve("auto", "https://unknown-site.example/stats")
    items = r.parse(HTML_TABLE, "https://unknown-site.example/stats")
    assert len(items) == 2 and items[0]["name"] == "proxyfetch"


def test_auto_falls_back_to_json_on_api_body():
    r = recipes.resolve("auto", "https://api.unknown.example/v1/things")
    items = r.parse(JSON_BODY, "https://api.unknown.example/v1/things")
    assert len(items) == 2


def test_auto_falls_back_to_page_meta():
    r = recipes.resolve("auto", "https://unknown.example/")
    items = r.parse(HTML_LIST, "https://unknown.example/")
    assert len(items) == 1 and "Books" in items[0]["title"]


# ------------------------------------------------------------------ resolve
def test_resolve_custom_parser_wins():
    def my_parser(html, url):
        return [{"x": 1}]
    r = recipes.resolve("generic", "https://x.com/", parser=my_parser)
    assert r.name == "custom" and r.parse("<b>anything</b>", "u") == [{"x": 1}]


def test_resolve_css_overrides_recipe_name():
    r = recipes.resolve("autoscout24", "https://x.com/", css="article")
    assert r.name == "css"


def test_resolve_universal_names_via_flags():
    assert recipes.resolve("generic", "https://x.com/", json_key="a.b").name == "json"
    assert recipes.resolve("generic", "https://x.com/", table_index=1).name == "table"


# ------------------------------------------------------------------ net
def test_page_url_template_all_pages():
    base = "https://books.toscrape.com/catalogue/page-1.html"
    tpl = "https://books.toscrape.com/catalogue/page-{n}.html"
    assert net.page_url(base, 1, tpl) == tpl.format(n=1)
    assert net.page_url(base, 3, tpl) == tpl.format(n=3)


def test_page_url_template_with_url_placeholder():
    tpl = "{url}?p={n}"
    assert net.page_url("https://x.com/l", 2, tpl) == "https://x.com/l?p=2"


def test_page_url_default_unchanged():
    assert net.page_url("https://x.com/l", 1) == "https://x.com/l"
    assert net.page_url("https://x.com/l", 2) == "https://x.com/l?page=2"
    with pytest.raises(ValueError):
        net.page_url("https://x.com/l", 2, "no-placeholder")


# ------------------------------------------------------------------ output
def test_dynamic_csv_columns_from_items(tmp_path):
    r = recipes.resolve("generic", "https://x.com/", css="x")
    items = [{"title": "a", "price": "1"}, {"title": "b", "price": "2", "extra": "e"}]
    files = output.write_outputs(items, {"count": 2}, tmp_path, "t", r)
    header = open(files["csv"], encoding="utf-8-sig").readline().strip()
    assert header.split(";") == ["title", "price", "extra"]


def test_generic_console_row_for_non_car_items():
    row = output.recipe_row({"title": "Book", "price": "5", "rating": "One"})
    assert "title=Book" in row and "price=5" in row


# ------------------------------------------------------------------ direct
def test_direct_probe_success(monkeypatch):
    from proxyfetch import pipeline

    def fake_get(url, *, timeout, proxy, read_limit, headers=None):
        assert proxy is None
        return HTML_LIST
    monkeypatch.setattr(net, "http_get", fake_get)
    cfg = Config(url="https://x.com/", css_selector="article.product")
    r = recipes.resolve("auto", cfg.url, css="article.product")
    out = pipeline._direct_probe(cfg, r, Logger(quiet=True))
    assert out and out[0][0] == "direct" and out[0][1] >= 0


def test_direct_probe_blocked(monkeypatch):
    from proxyfetch import pipeline

    def fake_get(url, **kw):
        raise OSError("blocked")
    monkeypatch.setattr(net, "http_get", fake_get)
    cfg = Config(url="https://x.com/")
    r = recipes.resolve("generic", cfg.url)
    assert pipeline._direct_probe(cfg, r, Logger(quiet=True)) == []


def test_direct_probe_unparseable(monkeypatch):
    from proxyfetch import pipeline

    monkeypatch.setattr(net, "http_get", lambda *a, **kw: "junk page")
    cfg = Config(url="https://x.com/", css_selector="article.product")
    r = recipes.resolve("auto", cfg.url, css="article.product")
    assert pipeline._direct_probe(cfg, r, Logger(quiet=True)) == []


# ------------------------------------------------------------------ config/cli
def test_config_mutually_exclusive_extraction():
    cfg = Config(url="https://x.com", css_selector="a", json_key="a.b")
    with pytest.raises(errors.ConfigError):
        cfg.validated()


def test_config_page_template_must_contain_n():
    with pytest.raises(errors.ConfigError):
        Config(url="https://x.com", page_template="nope").validated()


def test_cli_parse_fields():
    assert cli._parse_fields(None) is None
    assert cli._parse_fields(["title=h3 a::text", "url=a::attr(href)"]) == \
        {"title": "h3 a::text", "url": "a::attr(href)"}
    with pytest.raises(errors.ConfigError):
        cli._parse_fields(["noseparator"])


def test_cli_scrape_flags_parse():
    args = cli.build_parser().parse_args(
        ["--css", "article.p", "--field", "title=h3::text",
         "--page-template", "https://x/p-{n}.html", "--no-direct",
         "https://x.com"])
    assert args.css == "article.p"
    assert args.field == ["title=h3::text"]
    assert args.page_template == "https://x/p-{n}.html"
    assert args.no_direct is True
