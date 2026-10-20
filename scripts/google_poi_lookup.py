#!/usr/bin/env python3
"""google_poi_lookup.py — street addresses for employers OSM doesn't know.

Drives the agent-browser headless CLI against Google Maps search:
  open  https://www.google.com/maps/search/{company}+{city}?hl=en
  wait for the canonical /maps/place/ URL  -> coords from !3dLAT!4dLON
  name from <h1>, address from button[data-item-id="address"]

Sanity gates before accepting a hit:
  * <= 30 km from the town centroid
  * first company token appears in the place name, OR the address mentions
    the target town
Results are appended to data/work/google_poi.json after EVERY company
(sandbox resets killed longer runs twice already — this is resumable;
rerun and it skips what it has). Rejected searches are stored with a
reason so they don't re-burn quota.

Write-back: rows still at 'city' precision get
  company_address = google address, lat/lon, geo_precision=street,
  geo_source=google-maps. Rows OSM already placed well are left alone.

Usage:
  python3 scripts/google_poi_lookup.py --budget-sec 420   # chunk, resumable
  python3 scripts/google_poi_lookup.py --writeback-only   # just apply JSON
"""
import argparse, csv, json, math, os, re, subprocess, sys, time, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "data", "work")
POI_JSON = os.path.join(WORK, "google_poi.json")

from enrich_addresses import norm_key, _fold          # noqa: E402

def haversine(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (0.5 - math.cos((lat2 - lat1) * p) / 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2)
    return 12742 * math.asin(math.sqrt(a))

def ab(cmd, timeout=40):
    """Run an agent-browser CLI command; return stdout string or ''."""
    try:
        r = subprocess.run(["agent-browser"] + cmd, capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except Exception:
        return ""

def clean_company(name):
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", name or "")).strip()

def load_json():
    if os.path.exists(POI_JSON):
        try:
            return json.load(open(POI_JSON, encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_json(d):
    os.makedirs(WORK, exist_ok=True)
    tmp = POI_JSON + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, POI_JSON)

def lookup_one(company, city, clat, clon):
    """One Google Maps search. Returns hit dict (or {'reject': reason})."""
    q = f"{clean_company(company)} {city}"
    url = "https://www.google.com/maps/search/" + urllib.parse.quote_plus(q) + "?hl=en"
    ab(["open", url], timeout=45)
    deadline = time.time() + 14
    place_url = ""
    while time.time() < deadline:
        time.sleep(2.0)
        u = ab(["get", "url"], timeout=20)
        if "/maps/place/" in u:
            place_url = u
            break
        if "google.com/sorry" in u or "consent." in u:
            return {"reject": "blocked", "q": q}
    if not place_url:
        # try clicking the first result card, then wait for a real place page
        ab(["eval", "var e=document.querySelector('a.hfpxzc'); if(e){e.click();} 0"], timeout=25)
        deadline2 = time.time() + 10
        while time.time() < deadline2:
            time.sleep(2.0)
            place_url = ab(["get", "url"], timeout=20)
            if "/maps/place/" in place_url:
                break
        if "/maps/place/" not in place_url:
            return {"reject": "no-place-url", "q": q}
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", place_url) or \
        re.search(r"/@(-?\d+\.\d+),(-?\d+\.\d+)", place_url)
    if not m:
        return {"reject": "no-coords", "q": q}
    lat, lon = float(m.group(1)), float(m.group(2))
    # poll until the place panel has actually replaced the results list
    info, name, addr = "", "", ""
    deadline3 = time.time() + 8
    while time.time() < deadline3:
        time.sleep(1.5)
        info = ab(["eval", "(document.querySelector('h1')||{textContent:''}).textContent"
                           " + ' ||| ' + ((document.querySelector('button[data-item-id=\"address\"]')"
                           "||{ariaLabel:''}).ariaLabel || '')"], timeout=25)
        info = info.strip().strip('"')
        name, _, addr = info.partition(" ||| ")
        if name and name.strip().lower() not in ("results", ""):
            break
    addr = re.sub(r"^Address:\s*", "", (addr or "")).strip().strip('"').strip().rstrip(",")
    name = (name or "").strip().strip('"')
    # ---- sanity gates
    dist = haversine(clat, clon, lat, lon)
    if dist > 30:
        return {"reject": f"far-{dist:.0f}km", "q": q, "name": name}
    ctok = _fold(clean_company(company)).split()[0] if clean_company(company) else ""
    if ctok and ctok not in _fold(name):
        if not (city and city.split()[0].lower() in _fold(addr).lower()):
            return {"reject": "name-mismatch", "q": q, "name": name}
    return {"lat": lat, "lon": lon, "name": name, "address": addr,
            "km": round(dist, 1), "source": "google-maps", "q": q}

def writeback(rows, poi):
    """Apply google hits to rows still at city precision."""
    changed = 0
    for r in rows:
        if not r.get("lat") or (r.get("geo_precision") or "city") != "city":
            continue
        hit = poi.get(f"{norm_key(r['company'])}|{norm_key(r['city'])}")
        if not hit or "lat" not in hit:
            continue
        r["company_address"] = hit.get("address") or hit.get("name") or r["company_address"]
        r["lat"] = round(float(hit["lat"]), 6)
        r["lon"] = round(float(hit["lon"]), 6)
        r["geo_precision"] = "street"
        r["geo_source"] = "google-maps"
        changed += 1
    return changed

def main():
    ap = argparse.ArgumentParser(description="Google Maps POI lookup via headless browser")
    ap.add_argument("--input", default=None)
    ap.add_argument("--budget-sec", type=int, default=420)
    ap.add_argument("--writeback-only", action="store_true")
    a = ap.parse_args()

    src = a.input
    if not src:
        import glob as _g
        cands = sorted(f for f in _g.glob(os.path.join(BASE, "download", "erlangen_jobs_final_*.csv"))
                       if "_part" not in os.path.basename(f))
        src = cands[-1] if cands else None
    rows = list(csv.DictReader(open(src, newline="", encoding="utf-8")))
    fieldnames = list(rows[0].keys())
    poi = load_json()

    if a.writeback_only:
        changed = writeback(rows, poi)
        out = a.input or src
        tmp = out + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, out)
        print(f"writeback: {changed} rows updated from {POI_JSON}")
        return

    todo = []
    seen = set()
    for r in rows:
        if not r.get("lat") or (r.get("geo_precision") or "city") != "city":
            continue
        key = f"{norm_key(r['company'])}|{norm_key(r['city'])}"
        if key in poi or key in seen:
            continue
        seen.add(key)
        todo.append((key, r["company"], r["city"], float(r["lat"]), float(r["lon"])))
    known = sum(1 for v in poi.values() if "lat" in v)
    print(f"google lookup: {len(todo)} employers to try "
          f"({known} already good, {len(poi) - known} already rejected), budget {a.budget_sec}s")

    deadline, t0, ok0 = time.time() + a.budget_sec, time.time(), known
    for i, (key, company, city, clat, clon) in enumerate(todo, 1):
        if time.time() > deadline:
            print(f"  ... budget stop at {i-1}/{len(todo)} (resume by rerunning)")
            break
        hit = lookup_one(company, city, clat, clon)
        poi[key] = hit
        save_json(poi)                                  # resumable: save every step
        if "lat" in hit:
            print(f"  [{i}/{len(todo)}] + {company[:34]:34} {hit['address'][:52]}",
                  flush=True)
        elif i % 10 == 0:
            print(f"  [{i}/{len(todo)}] ... ({time.time()-t0:.0f}s)", flush=True)
        time.sleep(1.2)

    good = sum(1 for v in poi.values() if "lat" in v)
    print(f"\n=== GOOGLE POI === total good: {good} (was {ok0}), "
          f"rejected: {len(poi) - good} | {time.time()-t0:.0f}s")
    changed = writeback(rows, poi)
    out = a.input or src
    tmp = out + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, out)
    print(f"writeback: {changed} rows updated -> {out}")

if __name__ == "__main__":
    main()
