#!/usr/bin/env python3
"""mine_desc_addresses.py — last-resort geo source: addresses hidden in the
job description text. Postings often contain a literal German street line:

    "Deichslerstraße 25, 90489 Nürnberg"
    "Günter-Scharowsky-Str. 1, 91058 Erlangen"

We mine street+house-number (+optional PLZ/town) candidates from the
descriptions of rows still at town-centroid precision, geocode them via
geocode.maps.co (strict proxy pool), and accept only results that carry a
house number AND sit within 12 km of the row's city centroid.

Cache: data/work/desc_mine.json (resumable; definitive answers cached).

Usage:
  python3 scripts/mine_desc_addresses.py --dry          # count candidates only
  python3 scripts/mine_desc_addresses.py --budget-sec 240
"""
import argparse, csv, json, os, re, sys, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "data", "work")
MINE_JSON = os.path.join(WORK, "desc_mine.json")

from enrich_addresses import norm_key, load_cache, save_cache  # noqa: E402
import geocode_companies as gc                                  # maps.co fetch

# street token: capitalised name incl. hyphens/dots/umlauts, ending in a
# street-type word, then house number (with optional letter / range)
STREET = re.compile(
    r"([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9./\-]{1,48}?"
    r"(?:straße|strasse|str\.|str\b|weg|allee|platz|gasse|ring|damm|ufer|markt)"
    r"\.?\s*\d{1,4}\s*[a-zA-Z]?(?:\s*[-/]\s*\d{1,4})?)"
    r"\s*[,;·]?\s*(?:(\d{5})\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{2,}))?",
    re.I)

# looser fallback: unsuffixed street names like "Südwestpark 10-12 – 90449 Nürnberg"
LOOSE = re.compile(
    r"([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9./\-]*(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9./\-]*){0,2}"
    r"\s+\d{1,4}\s*[a-zA-Z]?(?:\s*[-/]\s*\d{1,4})?)"
    r"\s*[,;·–\-]?\s*(\d{5})\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{2,})")

def haversine(lat1, lon1, lat2, lon2):
    p = math_pi = 3.141592653589793 / 180
    a = (0.5 - math.cos((lat2 - lat1) * p) / 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2)
    return 12742 * math.asin(math.sqrt(a))

def clean_mined(s):
    s = re.sub(r"\s+", " ", s or "").strip(" ,;")
    return s

def mine(desc):
    """Return list of candidate address strings from a description."""
    if not desc:
        return []
    out, seen = [], set()
    for rx in (STREET, LOOSE):                              # strict first, loose fill
        for m in rx.finditer(desc):
            street, plz, town = m.group(1), m.group(2), m.group(3)
            cand = clean_mined(f"{street}, {plz} {town}" if plz else street)
            if len(cand) < 8 or cand.lower() in seen:
                continue
            seen.add(cand.lower())
            out.append(cand)
            if len(out) >= 3:                               # first 3 plausible
                return out
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--budget-sec", type=int, default=240)
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

    # employers still at city precision + their descriptions
    emps = {}
    for r in rows:
        if (r.get("geo_precision") or "city") != "city" or not r.get("lat"):
            continue
        k = (r["company"], r["city"])
        emps.setdefault(k, {"clat": float(r["lat"]), "clon": float(r["lon"]),
                            "descs": [], "rowidx": []})
        if r.get("description"):
            emps[k]["descs"].append(r["description"])
        emps[k]["rowidx"].append(r)

    cache = load_cache()  # shared cache file; we use "dm:" prefix keys
    todo, mined = {}, 0
    for k, e in emps.items():
        key = "dm:" + norm_key(k[0]) + ":" + norm_key(k[1])
        cands = []
        for d in e["descs"]:
            cands.extend(mine(d))
            if cands:
                break
        if cands:
            mined += 1
        if key not in cache and cands:
            todo[k] = (key, cands)
    print(f"city employers: {len(emps)} | with mined candidates: {mined} | "
          f"to geocode: {len(todo)} | budget {a.budget_sec}s")
    if a.dry:
        for k, (key, cands) in list(todo.items())[:15]:
            print(f"  {k[0][:36]:36} {k[1][:14]:14} -> {cands[0][:60]}")
        return

    os.makedirs(WORK, exist_ok=True)
    deadline, t0, placed = time.time() + a.budget_sec, time.time(), 0
    for i, (k, (key, cands)) in enumerate(sorted(todo.items()), 1):
        if time.time() > deadline:
            print(f"  ... budget stop at {i-1}/{len(todo)} (resume by rerunning)")
            break
        e = emps[k]
        hit = None
        for cand in cands[:2]:                              # try first 2 candidates
            q = cand if re.search(r"\d{5}", cand) else f"{cand}, {k[1]}, Germany"
            f, ok = gc.mapsco_forward(q)
            if not ok or not f:
                continue
            s, h = gc.score_mapsco(f, k[0], k[1], e["clat"], e["clon"])
            # strict: must carry a house number and stay near the city
            if h and h.get("precision") == "street" and h.get("km", 99) <= 12:
                hit = h
                break
        if hit:
            cache[key] = {"lat": hit["lat"], "lon": hit["lon"], "display": hit["display"],
                          "source": "desc-mine", "precision": "street",
                          "mined": hit.get("display", "")}
            placed += 1
            print(f"  [{i}/{len(todo)}] + {k[0][:30]:30} {hit['display'][:56]}", flush=True)
        else:
            cache[key] = None                               # definitive: candidates rejected
        if i % 10 == 0:
            save_cache(cache)
    save_cache(cache)

    # write back to every city row of employers we resolved
    changed = 0
    for r in rows:
        if (r.get("geo_precision") or "city") != "city" or not r.get("lat"):
            continue
        key = "dm:" + norm_key(r["company"]) + ":" + norm_key(r["city"])
        hit = cache.get(key)
        if hit and hit.get("lat"):
            r["company_address"] = hit.get("mined") or hit.get("display") or r["company_address"]
            r["lat"], r["lon"] = hit["lat"], hit["lon"]
            r["geo_precision"] = "street"
            r["geo_source"] = "desc-mine"
            changed += 1
    out = a.input or src
    tmp = out + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, out)

    from collections import Counter
    prec = Counter((r.get("geo_precision") or "city") for r in rows)
    print(f"\n=== DESC MINING === placed {placed} employers, {changed} rows updated")
    print(f"row precision now: " + " ".join(f"{k}={v}" for k, v in sorted(prec.items())))

if __name__ == "__main__":
    import math
    main()
