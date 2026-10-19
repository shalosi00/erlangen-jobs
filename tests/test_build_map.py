#!/usr/bin/env python3
"""test_build_map.py — offline unit tests for the map builder (no network, no browser).

Covers:
  * aggregation: rows merge per (company, lat, lon); bad/missing coords skipped
  * popup HTML escaping (no XSS through company/title/portal fields)
  * portal color mapping + fallback palette
  * GeoJSON structure: FeatureCollection, [lon, lat] coordinate order
  * render(): payload embedded, no '</script>' breakout, tokens replaced

Run:  python3 tests/test_build_map.py      (exit 0 = all PASS)
"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import build_map as bm

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  ({extra})" if extra else ""))

def row(title="Engineer", company="ACME GmbH", lat="49.58", lon="11.01",
        portal="Indeed", addr="Erlangen (Korridor-Gemeinde)", prec="city", **kw):
    r = dict(title=title, company=company, lat=lat, lon=lon,
             source_portal=portal, company_address=addr, geo_precision=prec,
             job_url="https://example.test/x", job_url_direct="",
             date_posted="2026-10-10", erlangen_km="3.2", line="S1",
             station="Erlangen", location="Erlangen, Bavaria", is_remote="")
    r.update(kw)
    return r

# ------------------------------------------------------------- aggregation
print("aggregate():")
markers, skipped = bm.aggregate([
    row(), row(title="DevOps", date_posted="2026-10-12"),          # same company+point -> 1 marker
    row(company="Other AG", lat="49.4", lon="10.5"),               # different company -> own marker
    row(lat="", lon=""), row(lat="99.9", lon="999"),               # bad coords -> skipped
])
check("same company+point merges", len(markers) == 2, f"got {len(markers)}")
check("bad coords skipped", skipped == 2, f"got {skipped}")
check("marker n counts jobs", markers[0]["n"] == 2, f"got {markers[0]['n']}")
check("jobs sorted newest first", markers[0]["jobs"][0]["d"] == "2026-10-12")
check("main portal picked", markers[0]["portal"].lower() == "indeed")
check("popup has company", "ACME GmbH" in markers[0]["popup"])

m2, s2 = bm.aggregate([row(company="<script>alert(1)</script> AG",
                           title="T</script>X", portal="WeirdPortal")])
check("company HTML-escaped in popup", "<script>" not in m2[0]["popup"]
      and "&lt;script&gt;" in m2[0]["popup"])
check("portal fallback color assigned", m2[0]["color"].startswith("#"))

# ------------------------------------------------------------- colors
print("portal_color():")
check("indeed brand color", bm.portal_color("indeed") == "#2f6fd6")
check("stepstone brand color", bm.portal_color("Stepstone") == "#12b886")
check("substring match", bm.portal_color("linkedin_de") == "#0a84c1")
check("unknown -> palette fallback", bm.portal_color("mystery") in bm._FALLBACK)

# ------------------------------------------------------------- geojson
print("build_geojson():")
gj = bm.build_geojson([row(lat="49.5", lon="11.0"), row(lat="", lon="")])
check("FeatureCollection", gj["type"] == "FeatureCollection")
check("only valid rows become features", len(gj["features"]) == 1)
f = gj["features"][0]
check("coords are [lon, lat]", f["geometry"]["coordinates"] == [11.0, 49.5])
check("properties carried", f["properties"]["company"] == "ACME GmbH"
      and f["properties"]["job_url"].startswith("https://"))

# ------------------------------------------------------------- render
print("render():")
payload = {"markers": m2, "portals": [], "topEmployers": [],
           "townCount": 1, "nSkipped": 0, "generated": "2026-10-20T00:00Z"}
page = bm.render(payload, "Test</title><script>evil()</script>", "2026-10-20", "x.csv")
check("payload embedded", "alert(1)</script> AG" not in page
      and "alert(1)<\\/script> AG" in page)
check("no payload </script> breakout", "</scr" not in page.split('<script id="payload"')[1].split("</script>")[0])
check("title tag escaped", "<title>Test&lt;/title&gt;" in page)
check("tokens replaced", "__PAYLOAD__" not in page and "__TITLE__" not in page)
js = json.loads(page.split('<script id="payload" type="application/json">')[1].split("</script>")[0])
check("embedded JSON parses", js["markers"][0]["company"].endswith("AG"))

# ------------------------------------------------------------- summary
print(f"\n{len(PASS)} PASS, {len(FAIL)} FAIL")
if FAIL:
    print("FAILED:", ", ".join(FAIL)); sys.exit(1)
print("ALL PASS")
