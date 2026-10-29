"""Pluggable extraction recipes.

A recipe bundles three concerns for one kind of target site:

1. ``verify``      -- is this HTML a *real* (non-blocked) page of the site?
2. ``parse``       -- extract normalized items from the page payload
3. presentation    -- CSV columns, console table, sort order, browser hints

LESSON LEARNED 1 (encoded here so it never regresses): do NOT treat "datadome"
as a block marker. Every legitimate AutoScout24 page embeds the DataDome JS
tag; only real content proof (items / markers) counts.

LESSON LEARNED 2: bot-challenge INTERSTITIALS (AWS WAF "Ich bin kein Roboter",
DataDome captcha, Cloudflare "Just a moment" ...) must never verify as real
content. Immobilienscout24's challenge page parses as a perfectly good
generic item (it has a title + meta description), which once made 14/19
proxies "verify" against a wall -- the pool then spun until timeout. Hence
every recipe rejects challenge fingerprints (see challenge_kind()).
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable

from . import errors
from .net import host_of


# --------------------------------------------------------------------- model
@dataclass(frozen=True)
class Recipe:
    name: str
    ok_markers: tuple[str, ...]        # empty tuple = no positive marker required
    block_markers: tuple[str, ...]
    parser: Callable[[str, str], list[dict]]
    min_items: int = 0                 # items a *page* must yield to count as OK
    article_selector: str | None = None  # CSS selector counted as content proof
    min_articles: int = 0
    locale: str | None = None
    timezone: str | None = None
    csv_columns: tuple[str, ...] = ("id", "title", "url")
    display: str = ""

    # ---------------------------------------------------------------- verify
    def verify(self, html: str) -> bool:
        """True when the page looks like the real site and not a block page."""
        if len(html) < 200:
            return False
        if challenge_kind(html):
            return False  # WAF/captcha interstitial -- never real content
        head = html[:40000].lower()
        m = re.search(r"<title[^>]*>(.*?)</title>", head, re.S)
        title = m.group(1) if m else ""
        if self.ok_markers and not any(k in head for k in self.ok_markers):
            return False
        return not any(b in head or b in title for b in self.block_markers)

    # ----------------------------------------------------------------- parse
    def parse(self, html: str, base_url: str) -> list[dict]:
        try:
            return self.parser(html, base_url)
        except Exception:
            return []

    # ----------------------------------------------------------- presentation
    def sort_key(self, item: dict):
        price = item.get("price_eur")
        return (price is None, price or 0)

    def table_row(self, item: dict) -> str:
        title = f"{item.get('title', '')} {item.get('version', '')}".strip()
        price = item.get("price_eur")
        price_s = f"EUR {price:,}" if isinstance(price, int) else "n/a"
        km = item.get("km")
        km_s = f"{km:,} km" if isinstance(km, int) else "n/a"
        extra = item.get("year") or ""
        city = (item.get("city") or item.get("description") or "")[:18]
        return f"{price_s:>12} | {extra:<6} | {km_s:>12} | {title[:40]} | {city}"


# --------------------------------------------------- bot-challenge detection
# Fingerprints of WAF / bot-wall INTERSTITIAL pages, keyed by vendor. Body
# markers are technical strings that only appear on challenge pages (never
# on legit pages: e.g. legit AS24 embeds js.datadome.co, but only the
# challenge interstitial references captcha-delivery.com). Title markers
# are human challenge phrases. Deliberately NOT included: bare "datadome"
# (lesson 1) and bare "captcha" in the body (login pages embed reCAPTCHA).
_CHALLENGE_BODY = (
    ("aws-waf", ("edge.sdk.awswaf.com", "awswafintegration", "aws-waf-token")),
    ("datadome", ("captcha-delivery.com",)),
    ("cloudflare", ("cf-chl-", "cf_chl_", "_incapsula_resource")),
    ("perimeterx", ("px-captcha", "press & hold to confirm")),
)
_CHALLENGE_TITLE = ("kein roboter", "just a moment", "attention required",
                    "checking your browser", "are you a robot", "captcha")


def challenge_kind(html: str) -> str | None:
    """Vendor name when ``html`` is a bot-challenge interstitial, else None.

    Used by every recipe's verify() so challenge pages can never pass
    proxy verification, and by the pipeline to explain WHY a site is
    unreachable (better than a silent timeout spin).
    """
    if not html:
        return None
    head = html[:40000].lower()
    for vendor, markers in _CHALLENGE_BODY:
        if any(m in head for m in markers):
            return vendor
    m = re.search(r"<title[^>]*>(.*?)</title>", head, re.S)
    if m and any(t in m.group(1).lower() for t in _CHALLENGE_TITLE):
        return "challenge"
    return None


# ------------------------------------------------------------------ autoscout24
def _dv(x):
    """Normalize vehicleDetails values (str, int or nested dict)."""
    if isinstance(x, dict):
        for k in ("value", "raw", "text", "label", "formatted"):
            if k in x:
                return _dv(x[k])
        return str(x)
    return x


def parse_autoscout24(html: str, base_url: str) -> list[dict]:
    """Extract listings from the Next.js ``__NEXT_DATA__`` payload."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    listings = data.get("props", {}).get("pageProps", {}).get("listings") or []
    out: list[dict] = []
    for l in listings:
        try:
            if not isinstance(l, dict) or not l.get("id"):
                continue  # junk/malformed entries are skipped, never fatal
            v = l.get("vehicle") or {}
            det = {d.get("iconName"): _dv(d.get("data"))
                   for d in (l.get("vehicleDetails") or []) if isinstance(d, dict)}
            pr = l.get("price") or l.get("pricing") or {}
            price = pr.get("priceRaw") or pr.get("consumerPriceRaw") or pr.get("numericPrice")
            km_raw = det.get("mileage_odometer")
            km = int(re.sub(r"[^\d]", "", str(km_raw))) \
                if km_raw and re.search(r"\d", str(km_raw)) else None
            seller = l.get("seller") or {}
            loc = l.get("location") if isinstance(l.get("location"), dict) else {}
            city = str(seller.get("cityName") or loc.get("city") or "").strip()
            zipc = str(loc.get("zip") or "").strip()
            out.append({
                "id": l.get("id"),
                "title": (v.get("title") or l.get("title") or
                          f"{v.get('make', '')} {v.get('model', '')}").strip(),
                "version": v.get("motorTypeName") or v.get("version") or "",
                "price_eur": int(price) if price else None,
                "year": str(det.get("calendar") or "").strip(),
                "km": km,
                "ps": str(det.get("speedometer") or "").strip("()"),
                "fuel": v.get("fuel") or "",
                "gear": v.get("transmission") or "",
                "seller": str(seller.get("type", "")),
                "city": f"{zipc} {city}".strip(),
                "url": urllib.parse.urljoin(base_url, l.get("url") or ""),
            })
        except Exception:
            continue  # one malformed listing must not poison the page
    return out


# ----------------------------------------------------- immobilienscout24
# IS24 sits behind AWS WAF; its search pages are Next.js and embed the
# result payload in __NEXT_DATA__. Exact nesting changes between releases,
# so the parser deep-searches the JSON for the largest array of
# listing-shaped dicts instead of hardcoding a path.
_IS24_LISTING_VOCAB = ("realestate", "price", "address", "exposeid", "title",
                       "listingid", "numberofrooms", "livingarea", "objectid")


def _is24_listing_score(arr: list) -> int:
    """How much an array looks like IS24 listings (0 = not at all)."""
    if not arr or not all(isinstance(x, dict) for x in arr):
        return 0
    hits = sum(
        1 for d in arr
        if sum(1 for k in d if k.lower() in _IS24_LISTING_VOCAB) >= 2)
    return hits if hits >= max(1, len(arr) * 0.7) else 0


_NESTED_VALUE_KEYS = ("value", "amount", "raw", "formatted", "number", "text", "label")


def _scalarize(v):
    """Reduce a matched value to a scalar (unwrap {value:..}/[first]/etc.)."""
    if not isinstance(v, (dict, list)):
        return v
    if isinstance(v, dict):
        for nk in _NESTED_VALUE_KEYS:
            for k, x in v.items():
                if nk in k.lower() and not isinstance(x, (dict, list)):
                    return x
        for x in v.values():
            if not isinstance(x, (dict, list)):
                return x
    if isinstance(v, list):
        for x in v[:10]:
            got = _scalarize(x)
            if got is not None:
                return got
    return None


def _dig_first(d: dict, *needles: str, depth: int = 4):
    """Depth-first search for the first value whose key contains a needle.

    Matches inside nested dicts/lists; dict values are unwrapped via
    ``_scalarize`` so ``{"price": {"value": 900}}`` yields ``900``.
    """
    if depth <= 0 or not isinstance(d, dict):
        return None
    for k, v in d.items():
        if any(n in k.lower() for n in needles):
            got = _scalarize(v)
            if got is not None:
                return got
    for v in d.values():
        if isinstance(v, dict):
            got = _dig_first(v, *needles, depth=depth - 1)
            if got is not None:
                return got
        elif isinstance(v, list):
            for x in v[:10]:
                if isinstance(x, dict):
                    got = _dig_first(x, *needles, depth=depth - 1)
                    if got is not None:
                        return got
    return None


def _as_int(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return int(x)
    if isinstance(x, str) and re.search(r"\d", x):
        try:
            return int(re.sub(r"[^\d]", "", x))
        except ValueError:
            return None
    return None


def parse_immobilienscout24(html: str, base_url: str) -> list[dict]:
    """Extract IS24 search listings from the embedded __NEXT_DATA__ JSON."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    arrays = _find_object_arrays(data)
    scored = [( _is24_listing_score(a), len(a), a) for _, a in arrays]
    scored = [s for s in scored if s[0] > 0]
    if not scored:
        return []
    arr = max(scored, key=lambda s: (s[1], s[0]))[2]
    out: list[dict] = []
    for d in arr:
        try:
            iid = _dig_first(d, "exposeid", "listingid", "objectid") or d.get("id")
            if not iid:
                continue
            price = _as_int(_dig_first(d, "price"))
            area = _as_int(_dig_first(d, "livingarea", "area"))
            rooms = _dig_first(d, "numberofrooms", "rooms")
            try:
                rooms_f = round(float(str(rooms).replace(",", ".")), 1) if rooms else None
            except ValueError:
                rooms_f = None
            out.append({
                "id": str(iid),
                "title": str(_dig_first(d, "title") or "").strip()[:200],
                "price_eur": price,
                "rooms": rooms_f,
                "area_m2": area,
                "city": str(_dig_first(d, "city") or "").strip()[:80],
                "zip": str(_dig_first(d, "zipcode", "postcode", "zip") or "").strip(),
                "url": f"{base_url.rsplit('/Suche', 1)[0]}/expose/{iid}",
            })
        except Exception:
            continue  # one malformed listing must not poison the page
    return out


# --------------------------------------------------------------------- generic
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _first_text(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.I | re.S)
    return _WS_RE.sub(" ", _TAG_RE.sub("", m.group(1))).strip() if m else ""


def parse_generic(html: str, base_url: str) -> list[dict]:
    """Best-effort structured view of an arbitrary page.

    Returns a single item with title, meta description and embedded JSON-LD
    (truncated) so agents still get useful, machine-readable content from
    any URL. Returns [] when nothing meaningful is present.
    """
    title = _first_text(html, r"<h1[^>]*>(.*?)</h1>") or _first_text(html, r"<title[^>]*>(.*?)</title>")
    desc = _first_text(html, r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']') \
        or _first_text(html, r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']')
    jsonld: list = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         html, re.S):
        try:
            jsonld.append(json.loads(m.group(1)))
        except Exception:
            continue
        if len(jsonld) >= 5:
            break
    if not (title or desc or jsonld):
        return []
    return [{
        "id": base_url,
        "title": title[:300],
        "description": desc[:500],
        "price_eur": None,
        "url": base_url,
        "jsonld": jsonld,
    }]


# ------------------------------------------------------- universal extraction
# Scrape ANY site: CSS selectors, JSON endpoints, HTML tables. CSS/table
# use BeautifulSoup (soupsieve CSS engine, supports ::text and ::attr()).
_BLOCK_GENERIC = ("access denied", "request blocked",
                  "temporarily unavailable", "proxy error")


def _soup(html: str):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise errors.ConfigError(
            "CSS/table extraction needs beautifulsoup4",
            hint="pip install beautifulsoup4")
    return BeautifulSoup(html, "html.parser")


def _norm_key(s: str, i: int) -> str:
    k = re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")
    return k or f"col_{i}"


def parse_css(html: str, base_url: str, selector: str = "",
              fields: dict[str, str | None] | None = None) -> list[dict]:
    """Extract items with a CSS selector; fields map name -> sub-selector.

    Field selectors are relative to each item element and support
    Scrapy-style suffixes: ``h3 a::text`` (element text) and
    ``a::attr(href)`` (attribute value). A bare selector (``h3 a``) or
    ``None`` yields the element's own text. href/src attribute values are
    resolved against the page URL automatically.
    """
    if not selector:
        return []
    soup = _soup(html)
    fields = fields if fields else {"text": None}
    out: list[dict] = []
    for el in soup.select(selector):
        item: dict = {}
        for fname, sel in fields.items():
            item[fname] = _select_field(el, sel, base_url)
        if any(item.values()):
            out.append(item)
    return out


_ATTR_SUFFIX = re.compile(r"::attr\(([^)]*)\)$")


def _select_field(el, sel: str | None, base_url: str) -> str:
    """Evaluate one field selector against an item element."""
    attr: str | None = None
    if sel:
        m = _ATTR_SUFFIX.search(sel)
        if m:
            attr = m.group(1).strip()
            sel = sel[:m.start()].strip()
        elif sel.endswith("::text"):
            sel = sel[:-6].strip()
        elif sel.endswith(":text"):  # tolerate single-colon spelling
            sel = sel[:-5].strip()
    if sel:
        found = el.select(sel)
        if not found:
            return ""
        first = found[0]
    else:
        first = el
    if attr is not None:
        val = first.get(attr, "") if hasattr(first, "get") else ""
    elif isinstance(first, str):
        val = first
    else:
        val = first.get_text(" ", strip=True)
    val = _WS_RE.sub(" ", str(val)).strip()
    if attr and val and attr in ("href", "src", "data-src", "action"):
        val = urllib.parse.urljoin(base_url, val)
    return val


def _norm_json_item(d: dict, base_url: str) -> dict:
    out = {}
    for k, v in d.items():
        out[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
    for k in ("url", "link", "href", "image", "img", "thumbnail", "avatar"):
        v = out.get(k)
        if isinstance(v, str) and v.startswith("/"):
            out[k] = urllib.parse.urljoin(base_url, v)
    return out


def _find_object_arrays(obj, path: str = "", out: list | None = None,
                        depth: int = 0) -> list[tuple[str, list]]:
    if out is None:
        out = []
    if depth > 6:
        return out
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj):
            out.append((path, obj))
        for x in obj[:3]:
            _find_object_arrays(x, path, out, depth + 1)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _find_object_arrays(v, f"{path}.{k}" if path else k, out, depth + 1)
    return out


def _walk_json_path(data, key: str):
    cur = data
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.lstrip("-").isdigit():
            cur = cur[int(part)]
        else:
            return None
    return cur


def parse_json_items(html: str, base_url: str,
                     json_key: str | None = None) -> list[dict]:
    """Extract items from a JSON response (REST APIs, JSON endpoints).

    ``json_key`` is a dot-path to the array of objects (list indices
    allowed: ``data.items``). Without it the largest array of objects
    anywhere in the document wins.
    """
    try:
        data = json.loads(html.strip())
    except Exception:
        return []
    arr = None
    if json_key:
        cand = _walk_json_path(data, json_key)
        if isinstance(cand, list):
            arr = cand
        elif isinstance(cand, dict):
            arr = [cand]
    if arr is None and isinstance(data, list):
        arr = data
    if arr is None:
        arrays = _find_object_arrays(data)
        arr = max(arrays, key=lambda kv: len(kv[1]))[1] if arrays else None
    if not arr:
        return []
    return [_norm_json_item(x, base_url) if isinstance(x, dict) else {"value": x}
            for x in arr]


def parse_table(html: str, base_url: str,
                table_index: int | None = None) -> list[dict]:
    """Extract rows from an HTML table (header row -> keys).

    ``table_index`` is 1-based; 0/None picks the table with the most rows.
    """
    soup = _soup(html)
    tables = soup.find_all("table")
    if not tables:
        return []
    if table_index and table_index > 0:
        pick = tables[table_index - 1] if table_index - 1 < len(tables) else None
    else:
        pick = max(tables, key=lambda t: len(t.find_all("tr")))
    if pick is None:
        return []
    rows = pick.find_all("tr")
    if len(rows) < 2:
        return []
    th = rows[0].find_all("th")
    if th:
        header = [c.get_text(" ", strip=True) for c in th]
        data_rows = rows[1:]
    else:
        header = [c.get_text(" ", strip=True) for c in rows[0].find_all("td")]
        data_rows = rows[1:]
    keys = [_norm_key(h, i) for i, h in enumerate(header)]
    out: list[dict] = []
    for r in data_rows:
        cells = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
        cells += [""] * (len(keys) - len(cells))
        item = {k: v for k, v in zip(keys, cells) if v}
        if item:
            out.append(item)
    return out


def _universal_recipe(name: str, display: str, parser: Callable,
                      **recipe_kwargs) -> Recipe:
    return Recipe(
        name=name,
        display=display,
        ok_markers=(),
        block_markers=_BLOCK_GENERIC,
        parser=parser,
        min_items=1,
        csv_columns=(),  # dynamic: derived from the extracted items
        **recipe_kwargs,
    )


def _make_auto() -> Recipe:
    """Structured-first chain for unknown sites:
    HTML table (>=2 rows) -> page meta/JSON-LD -> embedded JSON array."""
    def _parse(html: str, base_url: str) -> list[dict]:
        for finder in (lambda: parse_table(html, base_url),
                       lambda: parse_generic(html, base_url),
                       lambda: parse_json_items(html, base_url)):
            items = finder()
            if items:
                return items
        return []
    return _universal_recipe("auto-any", "auto: table -> page meta -> JSON", _parse)


_UNIVERSAL = {
    "custom": lambda parser: _universal_recipe(
        "custom", "custom parser (library mode)", parser),
    "css": lambda selector, fields: _universal_recipe(
        "css", f"css selector: {selector}",
        lambda html, base_url: parse_css(html, base_url, selector, fields)),
    "json": lambda json_key="": _universal_recipe(
        "json", f"json endpoint (path: {json_key or 'auto'})",
        lambda html, base_url: parse_json_items(html, base_url, json_key or None)),
    "table": lambda table_index=None: _universal_recipe(
        "table", f"html table #{table_index or 'largest'}",
        lambda html, base_url: parse_table(html, base_url, table_index)),
    "auto": _make_auto,
}


# ------------------------------------------------------------------- registry
RECIPES: dict[str, Recipe] = {
    "autoscout24": Recipe(
        name="autoscout24",
        display="AutoScout24 listings",
        ok_markers=("autoscout24",),
        # NOTE: "datadome" is deliberately NOT here (see module docstring).
        block_markers=("nicht verf", "ist für dich nicht", "access denied"),
        parser=parse_autoscout24,
        min_items=3,
        article_selector="article",
        min_articles=5,
        locale="de-DE",
        timezone="Europe/Berlin",
        csv_columns=("rank", "title", "version", "year", "km", "ps", "fuel",
                     "gear", "price_eur", "seller", "city", "url"),
    ),
    "immobilienscout24": Recipe(
        name="immobilienscout24",
        display="Immobilienscout24 listings",
        ok_markers=("immobilien",),
        block_markers=("nicht verf", "ist für dich nicht", "access denied"),
        parser=parse_immobilienscout24,
        min_items=3,
        article_selector="article",
        min_articles=3,
        locale="de-DE",
        timezone="Europe/Berlin",
        csv_columns=("rank", "title", "rooms", "area_m2", "price_eur",
                     "zip", "city", "url"),
    ),
    "generic": Recipe(
        name="generic",
        display="generic page (title/meta/JSON-LD)",
        ok_markers=(),
        block_markers=("access denied", "request blocked",
                       "temporarily unavailable", "proxy error"),
        parser=parse_generic,
        min_items=0,
        csv_columns=("id", "title", "description", "url"),
    ),
}

_HOST_HINTS = {
    "autoscout24": ("autoscout24.",),
    "immobilienscout24": ("immobilienscout24.",),
}


def resolve(name: str, url: str, *, css: str | None = None,
            fields: dict[str, str | None] | None = None,
            json_key: str | None = None, table_index: int | None = None,
            parser: Callable[[str, str], list[dict]] | None = None) -> Recipe:
    """Resolve the recipe for a run.

    Explicit extraction options (CSS / JSON path / table / custom parser)
    always win over ``name``; ``auto`` falls back to host detection and then
    to a structured-first chain (table -> page meta -> embedded JSON).
    """
    if parser is not None:
        return _UNIVERSAL["custom"](parser=parser)
    if css:
        return _UNIVERSAL["css"](selector=css, fields=dict(fields or {}))
    if json_key:
        return _UNIVERSAL["json"](json_key=json_key)
    if table_index is not None:
        return _UNIVERSAL["table"](table_index=table_index)
    if name == "auto":
        try:
            host = host_of(url)
        except ValueError:
            host = ""
        name = next((r for r, hints in _HOST_HINTS.items() if any(h in host for h in hints)),
                    "auto-any")
    if name == "auto-any":
        return _UNIVERSAL["auto"]()
    recipe = RECIPES.get(name)
    if recipe is None:
        raise errors.ConfigError(
            f"unknown recipe {name!r}",
            hint=f"available recipes: {', '.join(sorted(RECIPES))} (or 'auto')")
    return recipe
