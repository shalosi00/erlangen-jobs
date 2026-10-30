#!/usr/bin/env python3
"""enrich_addresses.py — add company addresses + geo coordinates to the final CSV.

Adds 5 map-ready columns:
  company_address   best-known street address (extracted from the job description,
                    resolved via geocoder display name) or the town name
  lat, lon          WGS84 coordinates of the workplace (street-level if possible,
                    else town centroid)
  geo_precision     street | city | ''
  geo_source        google | nominatim | photon | cache | gazetteer | ''

Geocoding provider chain (first available wins per query):
  1. google      — Geocoding API, activates automatically when GOOGLE_MAPS_API_KEY
                   is set ($5/1k, 10k free/mo — best quality)
  2. nominatim   — OpenStreetMap, through the strict proxy pool (1 req/s policy)
  3. photon      — komoot Photon, through the strict proxy pool (backup)
  4. gazetteer   — offline town centroids from data/rail_corridor.json (62 towns)

Everything network goes through net_resilience (NEVER your IP). Results are cached
in data/work/address_geo_cache.json (resumable: rerun fills gaps only).

Usage:
  python3 scripts/enrich_addresses.py                       # newest final CSV
  python3 scripts/enrich_addresses.py --limit 20            # smoke
  python3 scripts/enrich_addresses.py --budget-sec 1800     # long run
  python3 scripts/enrich_addresses.py --provider offline    # no network at all
"""
import argparse, csv, json, os, re, sys, time, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
WORK = os.path.join(BASE, "data", "work")
CACHE_FILE = os.path.join(WORK, "address_geo_cache.json")

# ---------------------------------------------------------------- extraction
# German street-name endings; require a house number right after to avoid FPs
_STREET = re.compile(
    r"\b((?:[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.\-'’]+[ \t]){0,2}"
    r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.\-'’]*"
    r"(?:stra(?:ß|ss)e|str\.|weg|allee|platz|ring|gasse|damm|ufer|markt|steige|gürtel|zeile|anger)"
    r"[\s.]*\d{1,4}\s*[a-zA-Z]?)")
_PLZ_CITY = re.compile(r"\b(9\d{4})\b[\s,]+([A-ZÄÖÜ][a-zäöüß]+(?:[ -][A-ZÄÖÜ][a-zäöüß]+){0,2})\b")
_LABEL = re.compile(r"(?:Arbeitsort|Standort|Einsatzort|Jobort|Adresse)\s*[:\-]\s*([^\n]{5,90})", re.I)
_BAD = re.compile(r"[@\ufffd]|https?://|www\.|Postfach|\bIL\b|\bUS\b")

def clean(s):
    s = re.sub(r"\s+", " ", str(s or "").strip())
    return s.strip(" .,;:|•-–")

_COUNTRY_WORDS = re.compile(r"\b(Deutschland|Germany|Bayern|Bavaria|BY|DE)\b", re.I)

def _clean_city_token(t):
    t = _COUNTRY_WORDS.sub(" ", t or "")
    t = clean(re.sub(r"^(?:ca\.?|etwa)\s+", "", t))
    return t

def extract_address(desc, location):
    """Return (street_query|None, city|None). street_query is a geocoder-ready string."""
    d = clean(desc)[:4000]
    street, city = None, None
    m = _STREET.search(d)
    if m:
        cand = clean(m.group(1))
        cand = re.sub(r"^(?:Arbeitsort|Standort|Einsatzort|Jobort|Adresse)\s*[:\-]?\s*", "", cand, flags=re.I)
        if 6 <= len(cand) <= 60 and not _BAD.search(cand):
            street = cand
            # PLZ+City in the vicinity of the street match
            win = d[max(0, m.start() - 90): m.end() + 90]
            pm = _PLZ_CITY.search(win)
            if pm:
                city = f"{pm.group(1)} {_clean_city_token(pm.group(2))}".strip()
            street = f"{street}, {city}" if city else street
    if not city:
        lm = _LABEL.search(clean(desc)[:2500])
        if lm:
            t = clean(lm.group(1))
            pm = _PLZ_CITY.search(t)
            if pm:
                city = f"{pm.group(1)} {_clean_city_token(pm.group(2))}".strip()
    if not city:
        # fall back to the CSV location column: "City, Bavaria, Germany"
        loc = clean(location)
        if loc:
            first = re.split(r",", loc)[0].strip()
            gm = re.match(r"^Greater\s+(.+?)\s+Metropolitan", first, re.I)
            if gm:
                first = gm.group(1).strip()
            if re.match(r"^[A-ZÄÖÜ][a-zäöüß.\- ]{2,40}$", first) and not _BAD.search(first):
                city = first
    if city:
        city = _clean_city_token(city).strip()
        if not city or not re.search(r"[A-Za-zÄÖÜäöüß]", city):
            city = None
    return street, city

# ---------------------------------------------------------------- gazetteer
def load_gazetteer():
    rc = json.load(open(os.path.join(BASE, "data", "rail_corridor.json"), encoding="utf-8"))
    gaz = {}
    for name, v in (rc.get("towns") or {}).items():
        if isinstance(v, dict) and v.get("lat"):
            gaz[name.lower()] = (float(v["lat"]), float(v["lon"]))
    for s in (rc.get("stations") or []):
        if isinstance(s, dict) and s.get("lat"):
            gaz.setdefault(str(s.get("name") or "").lower(), (float(s["lat"]), float(s["lon"])))
    # merge commute_filter's Nominatim cache (457 town/place lookups) as offline fallback
    gc_path = os.path.join(BASE, "data", "geocode_cache.json")
    if os.path.exists(gc_path):
        try:
            gc = json.load(open(gc_path, encoding="utf-8"))
            for key, results in gc.items():
                if not (isinstance(results, list) and results and isinstance(results[0], dict)):
                    continue
                r0 = results[0]
                if not (r0.get("lat") and r0.get("lon")):
                    continue
                q = key.split("|")[0]
                for pfx in ("q=", "town=", "plz="):
                    if q.startswith(pfx):
                        q = q[len(pfx):]
                        break
                q = clean(q).lower()
                if q and q not in gaz:
                    gaz[q] = (float(r0["lat"]), float(r0["lon"]))
        except Exception:
            pass
    return gaz

_GAZ = None
_GAZ_FOLD = None       # fold -> coords
_GAZ_FOLD_NAME = None  # fold -> original gazetteer name
_CITY_ALIAS = {
    "nuremberg": "Nürnberg", "nurnberg": "Nürnberg", "nuernberg": "Nürnberg",
    "fuerth": "Fürth", "furth": "Fürth",
    "munich": "München", "muenchen": "München", "cologne": "Köln", "koeln": "Köln",
    "wuerzburg": "Würzburg", "regensburg": "Regensburg", "bamberg": "Bamberg",
}

def _fold(s):
    s = (s or "").lower().strip()
    for a, b in (("ß", "ss"), ("ü", "u"), ("ö", "o"), ("ä", "a"), ("é", "e")):
        s = s.replace(a, b)
    return s

def gazetteer_city(city):
    global _GAZ, _GAZ_FOLD, _GAZ_FOLD_NAME
    if _GAZ is None:
        _GAZ = load_gazetteer()
        _GAZ_FOLD = {_fold(k): v for k, v in _GAZ.items()}
        _GAZ_FOLD_NAME = {_fold(k): k for k in _GAZ}
    if not city:
        return None
    tokens = [clean(re.sub(r"^\d{5}\s*", "", t)) for t in re.split(r"[,/]", city)]
    tokens = [_CITY_ALIAS.get(t.lower(), t) for t in tokens]          # EN->DE spelling
    for t in tokens:
        key = t.lower()
        if key in _GAZ:
            lat, lon = _GAZ[key]
            disp = _CITY_ALIAS.get(key, key).title()
            return {"lat": lat, "lon": lon, "display": disp + " (Korridor-Gemeinde)",
                    "source": "gazetteer", "precision": "city"}
        if _fold(t) in _GAZ_FOLD:
            lat, lon = _GAZ_FOLD[_fold(t)]
            return {"lat": lat, "lon": lon, "display": _unfold_name(t) + " (Korridor-Gemeinde)",
                    "source": "gazetteer", "precision": "city"}
    t = clean(re.sub(r"^\d{5}\s*", "", city))
    t = _CITY_ALIAS.get(t.lower(), t)
    f = _fold(t)
    for name_f, (lat, lon) in _GAZ_FOLD.items():
        if f.startswith(name_f) or name_f.startswith(f):
            disp = (_GAZ_FOLD_NAME.get(name_f) or name_f).title()
            return {"lat": lat, "lon": lon, "display": disp + " (Korridor-Gemeinde)",
                    "source": "gazetteer", "precision": "city"}
    return None

def _unfold_name(t):
    """Pick the canonical (original-cased) gazetteer name matching folded t."""
    if _GAZ_FOLD_NAME is not None:
        if _fold(t) in _GAZ_FOLD_NAME:
            return _GAZ_FOLD_NAME[_fold(t)].title()
        for name_f, orig in _GAZ_FOLD_NAME.items():
            if _fold(t).startswith(name_f) or name_f.startswith(_fold(t)):
                return orig.title()
    if _GAZ is None:
        return t.title()
    for k in _GAZ:
        if _fold(k) == _fold(t):
            return k.title()
    return t.title()

# ---------------------------------------------------------------- geocoders
_LAST_HIT = {"google": 0.0, "nominatim": 0.0, "photon": 0.0, "mapsco": 0.0}
_MIN_GAP = {"google": 0.12, "nominatim": 1.1, "photon": 0.35, "mapsco": 0.22}

def _pace(prov):
    wait = _MIN_GAP[prov] - (time.time() - _LAST_HIT[prov])
    if wait > 0:
        time.sleep(wait + 0.05)
    _LAST_HIT[prov] = time.time()

_POOL = None

def _pool():
    """Build/reuse the global strict proxy pool; auto-harvest once if dry."""
    global _POOL
    import net_resilience as nr
    if _POOL is None:
        _POOL, _ = nr.build(log=lambda *a, **k: None)
    if not _POOL.as_list():
        _POOL.ensure()
    return _POOL

def _fetch_json(url, headers, timeout=15, allow_direct=False):
    try:
        import net_resilience as nr
        pool = _pool()
        if not pool.as_list() and not allow_direct:
            return None                      # strict: never your IP
        resp, info = nr.resilient_fetch(url, timeout=timeout, max_tries=2,
                                        extra_headers=headers, log=None,
                                        pool=pool, allow_direct=allow_direct)
        if resp is None or getattr(resp, "status_code", 0) >= 400:
            return None
        return resp.json()
    except Exception:
        return None

def geo_google(q, key, allow_direct):
    _pace("google")
    u = ("https://maps.googleapis.com/maps/api/geocode/json?address="
         + urllib.parse.quote(q) + "&region=de&key=" + key)
    j = _fetch_json(u, {"Accept": "application/json"}, allow_direct=allow_direct)
    r = (j or {}).get("results") or []
    if j and j.get("status") == "OK" and r:
        g = r[0]["geometry"]["location"]
        prec = "street" if any(x for x in r[0].get("address_components", [])
                               if "route" in x.get("types", [])) else "city"
        return {"lat": g["lat"], "lon": g["lng"], "display": r[0].get("formatted_address", q),
                "source": "google", "precision": prec}
    return None

def geo_nominatim(q, allow_direct):
    _pace("nominatim")
    u = ("https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&addressdetails=1"
         "&countrycodes=de&q=" + urllib.parse.quote(q))
    j = _fetch_json(u, {"User-Agent": "erlangen-jobs/1.0 (personal job-search; OSM geocoding)",
                        "Accept": "application/json", "Accept-Language": "de"}, allow_direct=allow_direct)
    r = j if isinstance(j, list) else []
    if r:
        a = r[0].get("address") or {}
        prec = "street" if (a.get("house_number") or a.get("road")) else "city"
        return {"lat": float(r[0]["lat"]), "lon": float(r[0]["lon"]),
                "display": r[0].get("display_name", q), "source": "nominatim", "precision": prec}
    return None

def geo_photon(q, allow_direct):
    _pace("photon")
    u = ("https://photon.komoot.io/api?limit=1&lang=de&q=" + urllib.parse.quote(q))
    H = {"User-Agent": "erlangen-jobs/1.0", "Accept": "application/json"}
    j = None
    for _ in range(5):                       # photon flakes via proxies; rotate a few
        j = _fetch_json(u, H, allow_direct=allow_direct)
        if j:
            break
    f = ((j or {}).get("features") or [])
    if f:
        c = f[0]["geometry"]["coordinates"]          # [lon, lat]
        p = f[0].get("properties", {})
        prec = "street" if (p.get("housenumber") or p.get("street")) else "city"
        disp = ", ".join(str(p.get(k)) for k in ("name", "street", "housenumber", "postcode",
                                                 "city", "state")
                         if p.get(k) not in (None, "None", "")) or q
        return {"lat": c[1], "lon": c[0], "display": disp, "source": "photon", "precision": prec}
    return None

def geo_mapsco(q, key, allow_direct):
    """geocode.maps.co — Nominatim-grade forward geocoder, API-keyed (5 req/s
    free demo tier). Key comes from GEOCODE_MAPS_API_KEY, never logged/committed."""
    _pace("mapsco")
    u = ("https://geocode.maps.co/search?format=jsonv2&countrycodes=de&q="
         + urllib.parse.quote(q) + "&api_key=" + key)
    j = _fetch_json(u, {"Accept": "application/json"}, allow_direct=allow_direct)
    r = j if isinstance(j, list) else []
    if r:
        a = r[0].get("address") or {}
        prec = "street" if (a.get("house_number") or a.get("road")) else "city"
        return {"lat": float(r[0]["lat"]), "lon": float(r[0]["lon"]),
                "display": r[0].get("display_name", q), "source": "mapsco",
                "precision": prec, "category": r[0].get("category", ""),
                "name": r[0].get("name", "")}
    return None

def geo_zippopotam(q, allow_direct):
    """PLZ -> city centroid fallback (query like '91052 Erlangen')."""
    m = re.match(r"^(\d{5})\b", q.strip())
    if not m:
        return None
    _pace("photon")
    u = f"https://api.zippopotam.us/de/{m.group(1)}"
    j = _fetch_json(u, {"User-Agent": "erlangen-jobs/1.0", "Accept": "application/json"},
                    allow_direct=allow_direct)
    places = (j or {}).get("places") or []
    if places:
        p = places[0]
        disp = f"{p.get('post code')} {p.get('place name')}".replace("None", "").strip()
        return {"lat": float(p["latitude"]), "lon": float(p["longitude"]),
                "display": disp, "source": "zippopotam", "precision": "city"}
    return None

# ---------------------------------------------------------------- cache
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_cache(cache):
    os.makedirs(WORK, exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    json.dump(cache, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, CACHE_FILE)

# ---------------------------------------------------------------- main
def norm_key(s):
    return re.sub(r"[^a-zäöüß0-9]+", " ", (s or "").lower()).strip()

def resolve(query, cache, provider, google_key, allow_direct, deadline, mapsco_key=""):
    k = norm_key(query)
    if not k:
        return None
    if k in cache:
        hit = cache[k]
        if hit and hit.get("lat"):
            hit = dict(hit)
            hit["source"] = "cache:" + str(hit.get("source", "?"))
            return hit
        return None                      # known-bad query (negative cache)
    if provider == "offline" or time.time() > deadline:
        return None
    hit = None
    if provider == "auto" and google_key and time.time() <= deadline:
        hit = geo_google(query, google_key, allow_direct)
    if not hit and (provider == "mapsco" or (provider == "auto" and mapsco_key)) \
            and mapsco_key and time.time() <= deadline:
        hit = geo_mapsco(query, mapsco_key, allow_direct)
    if not hit and provider in ("auto", "photon") and time.time() <= deadline:
        hit = geo_photon(query, allow_direct)
    if not hit and provider in ("auto", "zippopotam") and time.time() <= deadline:
        hit = geo_zippopotam(query, allow_direct)
    if hit is None and time.time() > deadline:
        return None                      # out of budget: DON'T negative-cache
    # nominatim deliberately NOT in the auto chain: it blocks most proxy IPs
    # and burns the whole retry budget. Use --provider nominatim explicitly.
    cache[k] = hit or None               # negative caching too
    if hit is None:
        cache[k] = {"lat": None, "lon": None, "display": "", "source": "miss", "precision": ""}
    return hit

def main():
    ap = argparse.ArgumentParser(description="add company_address + lat/lon columns to the final CSV")
    ap.add_argument("--input", default=None, help="final CSV (default: newest download/erlangen_jobs_final_*.csv)")
    ap.add_argument("--out", default=None, help="output CSV (default: overwrite input atomically)")
    ap.add_argument("--limit", type=int, default=0, help="only first N rows (smoke)")
    ap.add_argument("--provider", default="auto",
                    choices=["auto", "google", "mapsco", "nominatim", "photon", "zippopotam", "offline"])
    ap.add_argument("--budget-sec", type=int, default=1200, help="max network time (cache makes reruns resume)")
    ap.add_argument("--allow-direct", action="store_true", help="opt-out of strict no-IP mode (not recommended)")
    a = ap.parse_args()

    import glob as _g
    src = a.input
    if not src:
        cands = sorted(f for f in _g.glob(os.path.join(BASE, "download", "erlangen_jobs_final_*.csv"))
                       if "_part" not in os.path.basename(f))
        src = cands[-1] if cands else None
    if not src or not os.path.exists(src):
        sys.exit(f"input CSV not found: {src or '(none in download/)'}")

    rows = list(csv.DictReader(open(src, newline="", encoding="utf-8")))
    fieldnames = list(rows[0].keys()) if rows else []
    if a.limit:
        rows = rows[: a.limit]
    for c in ("company_address", "lat", "lon", "geo_precision", "geo_source"):
        if c not in fieldnames:
            fieldnames.append(c)

    cache = load_cache()
    google_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    mapsco_key = os.environ.get("GEOCODE_MAPS_API_KEY", "")
    provider = a.provider
    deadline = time.time() + a.budget_sec
    t0 = time.time()

    # ---- pass 1: extract candidates for every row
    plan = []                             # (row_idx, street_q, city)
    for i, r in enumerate(rows):
        street, city = extract_address(r.get("description"), r.get("location") or r.get("city"))
        plan.append((i, street, city))
    n_street = sum(1 for _, s, _ in plan if s)
    uniq = {norm_key(s) for _, s, _ in plan if s} | {norm_key(c) for _, _, c in plan if c}
    uniq.discard("")
    print(f"input: {os.path.basename(src)} ({len(rows)} rows)")
    print(f"extracted: {n_street} street candidates | {len(uniq)} unique geocode queries "
          f"({len(load_cache())} cached)")

    # ---- pass 2: resolve unique queries (cache first, network second)
    resolved, tried = 0, 0
    for q in sorted(uniq):
        if norm_key(q) in cache:
            continue
        # city-only queries resolvable by the offline gazetteer skip the network
        if gazetteer_city(q):
            continue
        tried += 1
        hit = resolve(q, cache, provider, google_key, a.allow_direct, deadline, mapsco_key)
        resolved += 1 if hit else 0
        if tried % 25 == 0:
            save_cache(cache)
            print(f"  ... {tried} new queries resolved ({time.time()-t0:.0f}s, "
                  f"{max(0.0, deadline-time.time()):.0f}s budget left)")
    save_cache(cache)

    # ---- pass 3: write result columns
    stats = {"street": 0, "city": 0, "none": 0}
    srcs = {}
    for i, street_q, city in plan:
        hit = resolve(street_q, cache, "offline", "", False, deadline) if street_q else None
        if hit and hit.get("lat") and hit.get("precision") == "street":
            res = hit
        else:
            chit = resolve(city, cache, "offline", "", False, deadline) if city else None
            res = (chit if chit and chit.get("lat") else None) or gazetteer_city(city) or \
                  (hit if hit and hit.get("lat") else None)
            if not (res and res.get("lat")):
                # last resort: the CSV's own city/location columns
                for fb in (rows[i].get("city"), (rows[i].get("location") or "").split(",")[0]):
                    res = gazetteer_city(fb)
                    if res and res.get("lat"):
                        break
        r = rows[i]
        if res and res.get("lat"):
            r["company_address"] = res.get("display") or street_q or city or ""
            r["lat"] = round(float(res["lat"]), 6)
            r["lon"] = round(float(res["lon"]), 6)
            r["geo_precision"] = res.get("precision") or "city"
            r["geo_source"] = res.get("source") or ""
            stats[res.get("precision") or "city"] += 1
            base_src = str(res.get("source") or "").split(":")[-1]
            srcs[base_src] = srcs.get(base_src, 0) + 1
        else:
            r["company_address"] = street_q or ""
            r["lat"], r["lon"], r["geo_precision"], r["geo_source"] = "", "", "", ""
            stats["none"] += 1

    out = a.out or src
    tmp = out + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, out)

    dt = time.time() - t0
    print(f"\n=== GEO ENRICHMENT ===")
    print(f"output: {out}")
    print(f"precision: street={stats['street']}  city={stats['city']}  none={stats['none']}  "
          f"(rows {len(rows)})")
    print(f"sources: {dict(sorted(srcs.items(), key=lambda x: -x[1]))}")
    print(f"cache: {len(cache)} entries at {os.path.relpath(CACHE_FILE, BASE)}  ({dt:.0f}s)")

if __name__ == "__main__":
    main()
