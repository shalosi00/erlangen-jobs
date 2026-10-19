#!/usr/bin/env python3
"""geocode_companies.py — give EVERY employer its own point on the map.

The row-level enrich_addresses.py only reaches street precision when the job
description contains a literal street+HN (rare, ~2%); everybody else lands on
the city centroid, so hundreds of companies stack on one dot. This pass asks
the geocoder where the COMPANY is instead:

  query    "{company}, {city}"  then "{company}"   (biased to the city centre)
  sanity   result must sit within 25 km of the city centroid (12 km when the
           result's own town name differs from the target city); highways and
           administrative places are rejected unless they carry a house number
  accept   precision = street (house number found) | poi (company POI w/o HN)
  miss     keep city centroid — build_map.py spreads coincident pins instead

Network: strict proxy pool only (net_resilience), never your IP.
Cache:   data/work/address_geo_cache.json, keys "co:<company>:<city>" —
         resumable; definitive Photon "no result" answers are cached,
         network flakes are not (they retry on the next run).

Usage:
  python3 scripts/geocode_companies.py                    # 8-min budget
  python3 scripts/geocode_companies.py --budget-sec 420   # short round
  python3 scripts/geocode_companies.py --all              # re-resolve even street rows
"""
import argparse, csv, itertools, json, math, os, re, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "data", "work")

import enrich_addresses as ea          # reuse pool, pacing, cache, photon
from enrich_addresses import (norm_key, _fold, _fetch_json,
                              load_cache, save_cache)
import threading

_TL = threading.local()

def _pace_fast(gap=0.15):
    """Per-thread pacing — the shared global pacer serialises all workers."""
    last = getattr(_TL, "last", 0.0)
    wait = gap - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    _TL.last = time.time()

POI_KEYS = {"amenity", "office", "shop", "building", "craft", "industrial",
            "leisure", "tourism", "man_made", "landuse", "public"}
REJECT_KEYS = {"highway", "place", "boundary", "waterway", "natural", "railway"}
LEGAL = re.compile(r"\b(gmbh|mbh|&|co\.?|kg|ag|se|ug|ohg|e\.?\s?k\.?|e\.?\s?v\.?|"
                   r"inc\.?|ltd\.?|llc|sa|nv|bv)\b\.?", re.I)
PAREN = re.compile(r"\([^)]*\)")

def haversine(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (0.5 - math.cos((lat2 - lat1) * p) / 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2)
    return 12742 * math.asin(math.sqrt(a))          # km

def clean_company(name):
    c = PAREN.sub(" ", name or "")
    c = LEGAL.sub(" ", c)
    c = re.sub(r"[.,;:]+", " ", c)
    return re.sub(r"\s+", " ", c).strip(" -")

def _lean_fetch(url, H, timeout=9):
    """One strict-pool attempt, private pacer (the global one backs off for
    minutes once a target throttles — that stalled round 2 to a crawl)."""
    import net_resilience as nr
    pool = ea._pool()
    if not pool.as_list():
        return None
    try:
        resp, info = nr.resilient_fetch(url, pool=pool, pacer=nr.AdaptivePacer(),
                                        timeout=timeout, max_tries=1,
                                        extra_headers=H, log=None)
        if resp is None or getattr(resp, "status_code", 0) >= 400:
            return None
        return resp
    except Exception:
        return None

def photon_biased(q, lat, lon):
    """Photon with location bias. Returns (features, ok) — ok=False = network flake."""
    _pace_fast()
    u = ("https://photon.komoot.io/api?limit=1&lang=de"
         f"&lat={lat:.6f}&lon={lon:.6f}&q=" + urllib.parse.quote(q))
    H = {"User-Agent": "erlangen-jobs/1.0", "Accept": "application/json"}
    for _ in range(3):                                # rotate past proxy flakes
        r = _lean_fetch(u, H)
        if r is not None:
            try:
                return (r.json().get("features") or []), True
            except Exception:
                return None, False                    # 2xx but broken body -> flake
    return None, False

def score_feature(f, company, city, clat, clon):
    """Return (score, dict|None). dict=None means 'definitively not this company'."""
    p = f.get("properties", {}) or {}
    c = f.get("geometry", {}).get("coordinates") or [None, None]
    if not c or c[0] is None:
        return -99, None
    lon, lat = float(c[0]), float(c[1])
    dist = haversine(clat, clon, lat, lon)
    if dist > 25:
        return -99, None
    rcity = _fold(str(p.get("city") or p.get("district") or p.get("county") or ""))
    if rcity and _fold(city) not in rcity and rcity not in _fold(city) and dist > 12:
        return -99, None
    key = str(p.get("osm_key") or "")
    hn, street, name = p.get("housenumber"), p.get("street"), str(p.get("name") or "")
    s = 0.0
    if hn:
        s += 3
    if street:
        s += 2
    if key in POI_KEYS:
        s += 1.5
    ctok = _fold(clean_company(company)).split()[0] if clean_company(company) else ""
    if ctok and ctok in _fold(name):
        s += 1.5
    if key in REJECT_KEYS and not hn:
        s -= 4                                        # road named "Siemensstraße" etc.
    if dist < 3:
        s += 1                                        # near the city it claims
    prec = "street" if (hn or (street and key in POI_KEYS)) else \
           ("poi" if (key in POI_KEYS or (ctok and ctok in _fold(name))) else "city")
    disp = ", ".join(str(p.get(k)) for k in ("name", "street", "housenumber",
                                             "postcode", "city", "district", "state")
                     if p.get(k) not in (None, "None", "")) or name or q_disp(city)
    return s, {"lat": round(lat, 6), "lon": round(lon, 6), "display": disp[:120],
               "source": "photon", "precision": prec, "km": round(dist, 1)}

def q_disp(city):
    return city or ""

def resolve_employer(company, city, clat, clon, cache):
    """Best Photon answer for one employer; returns hit dict or None (keeps city)."""
    key = f"co:{norm_key(company)}:{norm_key(city)}"
    if key in cache:
        hit = cache[key]
        return dict(hit, source="cache:" + str(hit.get("source", "?"))) if hit else None
    cc = clean_company(company)
    best = None
    definitive_empty = True
    for q in (f"{cc}, {city}", cc):
        feats, ok = photon_biased(q, clat, clon)
        if not ok:
            definitive_empty = False                  # network flake — retry later
            continue
        if feats:
            s, hit = score_feature(feats[0], cc, city, clat, clon)
            if hit and (best is None or s > best[0]):
                best = (s, hit)
    if best and best[0] > 0:
        hit = best[1]
        cache[key] = {"lat": hit["lat"], "lon": hit["lon"], "display": hit["display"],
                      "source": hit["source"], "precision": hit["precision"]}
        return hit
    if definitive_empty:
        # photon answered (no features, or only things that are clearly NOT the
        # company — roads/admin places/other towns). Retrying is pointless.
        cache[key] = None
    return None

def main():
    ap = argparse.ArgumentParser(description="per-company geocoding pass (own map point per employer)")
    ap.add_argument("--input", default=None)
    ap.add_argument("--budget-sec", type=int, default=480)
    ap.add_argument("--all", action="store_true", help="also re-resolve street-level rows")
    a = ap.parse_args()

    src = a.input
    if not src:
        import glob as _g
        cands = sorted(f for f in _g.glob(os.path.join(BASE, "download", "erlangen_jobs_final_*.csv"))
                       if "_part" not in os.path.basename(f))
        src = cands[-1] if cands else None
    if not src or not os.path.exists(src):
        sys.exit(f"input CSV not found: {src}")

    rows = list(csv.DictReader(open(src, newline="", encoding="utf-8")))
    fieldnames = list(rows[0].keys())
    for c in ("company_address", "lat", "lon", "geo_precision", "geo_source"):
        if c not in fieldnames:
            fieldnames.append(c)

    # distinct employers still sitting on the city centroid
    emp = {}
    for r in rows:
        if not r.get("lat"):
            continue
        if not a.all and r.get("geo_precision") == "street":
            continue
        emp.setdefault((r["company"], r["city"]), (r["lat"], r["lon"]))

    cache = load_cache()
    todo = sorted(k for k in emp if f"co:{norm_key(k[0])}:{norm_key(k[1])}" not in cache)
    print(f"input: {os.path.basename(src)} ({len(rows)} rows) | employers to place: "
          f"{len(emp)} | already answered: {len(emp) - len(todo)} | budget: {a.budget_sec}s")

    deadline, t0, placed = time.time() + a.budget_sec, time.time(), 0
    prec = {"street": 0, "poi": 0, "city": 0}

    def work(key):
        company, city = key
        clat, clon = emp[key]
        return key, resolve_employer(company, city, float(clat), float(clon), cache)

    done = 0
    chunk_it = iter(todo)
    while True:
        if time.time() > deadline:
            print(f"  ... budget exhausted at {done}/{len(todo)} (resume by rerunning)")
            break
        chunk = list(itertools.islice(chunk_it, 32))
        if not chunk:
            break
        with ThreadPoolExecutor(max_workers=8) as ex:
            for key, hit in ex.map(work, chunk):
                done += 1
                if hit:
                    placed += 1
                    prec[hit.get("precision", "city")] = prec.get(hit.get("precision", "city"), 0) + 1
        save_cache(cache)
        print(f"  ... {done}/{len(todo)} tried, {placed} newly placed "
              f"({time.time()-t0:.0f}s elapsed)", flush=True)
    save_cache(cache)

    # write back
    stats = {"street": 0, "poi": 0, "city": 0}
    for r in rows:
        if not r.get("lat") or (not a.all and r.get("geo_precision") == "street"):
            stats[r.get("geo_precision") or "city"] = stats.get(r.get("geo_precision") or "city", 0) + 1
            continue
        hit = resolve_employer(r["company"], r["city"], float(r["lat"]), float(r["lon"]), cache)
        if hit:
            r["company_address"] = hit["display"]
            r["lat"], r["lon"] = hit["lat"], hit["lon"]
            r["geo_precision"] = hit["precision"]
            r["geo_source"] = hit["source"]
            stats[hit["precision"]] += 1
        else:
            stats["city"] += 1

    out = a.input or src
    tmp = out + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, out)

    print(f"\n=== COMPANY GEOCODING ===")
    print(f"newly placed this run: {placed} (street={prec.get('street',0)} "
          f"poi={prec.get('poi',0)} city={prec.get('city',0)})")
    print(f"row precision now: street={stats.get('street',0)} poi={stats.get('poi',0)} "
          f"city={stats.get('city',0)}  (rows {len(rows)})")
    print(f"cache: {len(cache)} entries ({time.time()-t0:.0f}s)")

if __name__ == "__main__":
    main()
