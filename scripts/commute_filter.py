#!/usr/bin/env python3
"""
commute_filter.py — Erlangen rail-commute filter (FAST, stdlib-only).

Constraint researched & encoded in data/rail_corridor.json:
  Job passes ONLY if the company location is
    1) on a rail line running NORTH or SOUTH from Erlangen
       (S1 trunk Bamberg–Erlangen–Nürnberg + same-axis continuations:
        north ext. Hallstadt/Breitengüßbach via Bamberg,
        south leg Schwabach/Roth/Allersberg etc. via Nürnberg), and
    2) within 50 km of Erlangen center, and
    3) close to a train station (has own station, or <= 3.0 km from one).

Speed design ("very quickly filter out"):
  - Pass 1 (fast path): normalized city lookup in the corridor town map
    -> instant PASS/FAIL for ~95% of rows, ZERO network.
  - Pass 2 (fallback): Nominatim geocode for unknown cities, 1 rps, disk-cached
    in data/geocode_cache.json (first run only; later runs are instant).
  - --no-network: mark unknown cities unresolved instead of fetching.

Usage:
  python3 scripts/commute_filter.py                       # filter master dataset
  python3 scripts/commute_filter.py --input <file.json>   # any jobspy-style list
  python3 scripts/commute_filter.py --station-km 2.0 --no-network
  python3 scripts/commute_filter.py --prefilter --fresh-days 30   # text pre-filter inline

Outputs (in download/):
  erlangen_commute_filtered_<ts>.json/.csv   passing jobs + commute annotations
  erlangen_commute_report_<ts>.md            stats, per-station breakdown, audit
"""
import json, csv, math, os, re, sys, time, argparse, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORR_FILE = os.path.join(BASE, "data", "rail_corridor.json")
CACHE_FILE = os.path.join(BASE, "data", "geocode_cache.json")
DOWNLOAD = os.path.join(BASE, "download")
UA = "erlangen-commute-filter/1.0 (job-search tooling; contact: operator)"

# optional text pre-filter (same module the merge pipeline uses)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import job_prefilter
except ImportError:
    job_prefilter = None

# strict proxy layer for the rare online geocode calls (never the user's IP)
try:
    import net_resilience as _nr
except ImportError:
    _nr = None
_GEO_POOL = None          # lazy: only built when a cache miss needs network

def _geo_opener():
    """Proxy-rotating urllib opener (strict).

    Returns (opener, proxy_url) or (None, None) when offline/no proxy is
    allowed — the user's IP is NEVER used for geocoding.
    """
    global _GEO_POOL
    if _nr is None:
        return None, None
    if _GEO_POOL is None:
        try:
            _GEO_POOL = _nr.ProxyPool(state_file=_nr.POOL_STATE,
                                      log=lambda *a: None)
        except Exception:
            return None, None
    px_url = _GEO_POOL.next()
    if px_url is None:                 # strict: never the user's IP
        _GEO_POOL.ensure(min_healthy=1)
        px_url = _GEO_POOL.next()
    if px_url is None:
        return None, None
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": px_url, "https": px_url}))
    return opener, px_url

# ---------------------------------------------------------------- location parsing
REGION_TAILS = re.compile(
    r",\s*(BY|Bavaria|Bayern|Germany|Deutschland|Oberfranken|Oberbayern|"
    r"Middle Franconia|Mittelfranken|Upper Franconia|Lower Bavaria|"
    r"Greater Nuremberg Metropolitan Area|Nürnberger Land)\s*$", re.I)

CITY_ALIASES = {
    "nuremberg": "Nürnberg", "nuernberg": "Nürnberg", "nurnberg": "Nürnberg",
    "nürnberg nord": "Nürnberg",
    "fuerth": "Fürth", "furth": "Fürth",
    "breitenguessbach": "Breitengüßbach",
    "greater nuremberg metropolitan area": "Nürnberg",  # metro label -> city center
    "grosser raum nürnberg": "Nürnberg",
    "stein": "Stein bei Nürnberg",
    "neumarkt": "Neumarkt in der Oberpfalz",
    "neumarkt in der oberpfalz": "Neumarkt in der Oberpfalz",
    "lauf": "Lauf an der Pegnitz",
    "rothenbach an der pegnitz": "Röthenbach an der Pegnitz",
    "altdorf": "Altdorf bei Nürnberg",
    "hoechstadt an der aisch": "Höchstadt an der Aisch",
    "hochstadt an der aisch": "Höchstadt an der Aisch",
    "schwaig": "Schwaig bei Nürnberg",  # near Nürnberg airport, no corridor station
}

def parse_city(location):
    """Return (city_key, metro_approx, raw). Normalizes jobspy-style strings."""
    if not location:
        return None, False, ""
    raw = str(location).strip()
    s = raw
    # strip stacked region tails: "City, BY, Germany" -> "City"
    for _ in range(4):
        s2 = REGION_TAILS.sub("", s).strip(", ")
        if s2 == s:
            break
        s = s2
    low = s.lower()
    if low in CITY_ALIASES:
        return CITY_ALIASES[low], low.startswith("greater"), raw
    # district prefixes: "Erlangen-Tennenlohe" -> "Erlangen"
    m = re.match(r"^(Erlangen|Nürnberg|Nuremberg|Fürth|Fürth|Bamberg|Schwabach|Baiersdorf|Forchheim)-", s, re.I)
    if m:
        head = m.group(1)
        head = "Nürnberg" if head.lower() in ("nürnberg", "nuremberg") else head
        return head, False, raw
    # "Lauf a.d.Pegnitz" style
    s2 = re.sub(r"\ba\.\s*d\.\s*", "an der ", s, flags=re.I)
    if s2.lower() in CITY_ALIASES:
        return CITY_ALIASES[s2.lower()], False, raw
    return (s if s else None), False, raw

# ---------------------------------------------------------------- geo helpers
def haversine(a, b):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE))
        except Exception:
            return {}
    return {}

def save_cache(c):
    tmp = CACHE_FILE + ".tmp"
    json.dump(c, open(tmp, "w"), ensure_ascii=False, indent=0)
    os.replace(tmp, CACHE_FILE)

def geocode(city, cache, network=True):
    """Nominatim geocode a Bavarian town; cached. Returns (lat, lon) or None."""
    key = f"town={city}|cc=de"
    if key in cache:
        res = cache[key]
    elif not network:
        return None
    else:
        params = {"q": f"{city}, Bayern", "format": "jsonv2", "limit": 8, "countrycodes": "de"}
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
        res = []
        for attempt in range(3):
            opener, px_used = _geo_opener()
            if opener is None:
                # strict no-IP mode: no healthy proxy -> do NOT geocode directly
                print(f"  ! geocode({city}) skipped: no healthy proxy available "
                      f"(strict mode — your IP is never used)", flush=True)
                break
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de"})
                with opener.open(req, timeout=25) as r:
                    res = json.load(r)
                try:
                    _GEO_POOL.report(px_used, status=200)
                except Exception:
                    pass
                break
            except urllib.error.HTTPError as e:
                wait = 8 if e.code == 429 else 2 + 3 * attempt   # throttle -> longer backoff
                print(f"  ! geocode({city}) HTTP {e.code}, retry in {wait}s", flush=True)
                try:
                    _GEO_POOL.report(px_used, error=f"http_{e.code}")
                except Exception:
                    pass
                if attempt == 2:
                    break
                time.sleep(wait)
            except Exception as e:
                print(f"  ! geocode({city}) error {e}, retrying", flush=True)
                try:
                    _GEO_POOL.report(px_used, error=str(e)[:80])
                except Exception:
                    pass
                if attempt == 2:
                    break
                time.sleep(2 + 3 * attempt)
        cache[key] = res
        time.sleep(1.15)
    if not res:
        return None
    tn = city.lower()
    rank = {"city": 0, "town": 1, "municipality": 2, "village": 3,
            "borough": 4, "suburb": 4, "administrative": 5, "hamlet": 8}
    cand = []
    for r_ in res:
        disp = r_.get("display_name", "")
        first = disp.split(",")[0].strip().lower()
        if first != tn and not first.startswith(tn + " "):
            continue
        cand.append((rank.get(r_.get("type"), 6), -float(r_.get("importance") or 0), r_))
    if not cand:
        return None
    best = sorted(cand, key=lambda x: (x[0], x[1]))[0][2]
    return float(best["lat"]), float(best["lon"])

# ---------------------------------------------------------------- main filter
def main():
    ap = argparse.ArgumentParser(description="Erlangen N-S rail corridor job filter")
    ap.add_argument("--input", default=os.path.join(DOWNLOAD, "erlangen_master_20261017_1813.json"))
    ap.add_argument("--prefix", default="erlangen_commute")
    ap.add_argument("--station-km", type=float, default=3.0,
                    help="max straight-line km from a corridor station (default 3.0)")
    ap.add_argument("--max-km", type=float, default=50.0, help="max km from Erlangen (default 50)")
    ap.add_argument("--include-remote", action="store_true", help="keep remote jobs (default: reject)")
    ap.add_argument("--no-network", action="store_true", help="never geocode online; unknown -> unresolved")
    ap.add_argument("--save-rejected", action="store_true", help="also write rejected jobs file for audit")
    ap.add_argument("--outdir", default=DOWNLOAD, help=f"output directory (default {DOWNLOAD})")
    ap.add_argument("--prefilter", action="store_true",
                    help="apply text pre-filter (job_prefilter) before the geo pass")
    ap.add_argument("--fresh-days", type=int, default=30,
                    help="prefilter: max age of date_posted in days (default 30)")
    ap.add_argument("--no-fp-guard", action="store_true",
                    help="prefilter: disable senior/mgmt false-positive guard")
    args = ap.parse_args()

    corr = json.load(open(CORR_FILE))
    stations = [s for s in corr["stations"] if s.get("enabled")]
    towns = corr["towns"]
    E = (corr["meta"]["erlangen_center"]["lat"], corr["meta"]["erlangen_center"]["lon"])

    jobs = json.load(open(args.input))
    print(f"loaded {len(jobs)} jobs from {os.path.basename(args.input)}")

    # -------- optional text pre-filter (before ANY geo work) --------
    pf_stats = None
    if args.prefilter:
        if job_prefilter is None:
            print("! job_prefilter not importable - skipping pre-filter")
        else:
            n_in = len(jobs)
            jobs, pf_rej, pf_stats = job_prefilter.prefilter_jobs(
                jobs, fresh_days=args.fresh_days, fp_guard=not args.no_fp_guard)
            print(f"pre-filter: {n_in} -> {len(jobs)} jobs "
                  f"({len(pf_rej)} removed: " + ", ".join(
                      f"{k}={v}" for k, v in sorted(pf_stats['by_rule'].items(),
                                                    key=lambda x: -x[1])) + ")")

    print(f"corridor: {len(stations)} stations ("
          f"{sum(1 for s in stations if s['tier']=='trunk_direct')} direct trunk, "
          f"{sum(1 for s in stations if s['tier']=='transfer1')} 1-transfer), "
          f"{len(towns)} known towns | thresholds: <= {args.max_km} km Erlangen, "
          f"<= {args.station_km} km station")

    cache = load_cache()
    t0 = time.time()
    passing, rejected, unresolved = [], [], []
    net_calls = 0

    def nearest_station(lat, lon):
        best, bd = None, 1e18
        for s in stations:
            d = haversine((lat, lon), (s["lat"], s["lon"]))
            if d < bd:
                best, bd = s, d
        return best, bd

    for i, job in enumerate(jobs):
        loc = job.get("location") or ""
        city, metro, raw = parse_city(loc)
        is_remote = str(job.get("is_remote", "False")).lower() == "true" or \
                    "remote" in loc.lower() and "area" not in loc.lower()
        rec_reason = None
        anno = None

        if is_remote and not args.include_remote:
            rec_reason = "remote"
        elif not city:
            rec_reason = "no_location"
        elif city in towns:
            t = towns[city]
            if t["status"] == "corridor_town" and t["dist_km"] <= args.max_km:
                st, sd = nearest_station(t["lat"], t["lon"])
                anno = dict(city=city, lat=t["lat"], lon=t["lon"],
                            erlangen_km=t["dist_km"], nearest_station=st["name"],
                            station_km=round(sd, 2), direction=st["branch"],
                            tier=st["tier"], line=st["line"],
                            match="town", metro_approx=metro)
            elif t["status"] == "outside_50km" or t["dist_km"] > args.max_km:
                rec_reason = f"outside_{int(args.max_km)}km"
            else:
                rec_reason = "off_corridor_town"
        else:
            coords = geocode(city, cache, network=not args.no_network)
            if coords is None:
                rec_reason = "unresolved_location"
                if args.no_network:
                    rec_reason = "unresolved_no_network"
            else:
                lat, lon = coords
                dist_e = haversine(E, coords)
                if dist_e > args.max_km:
                    rec_reason = f"outside_{int(args.max_km)}km"
                else:
                    st, sd = nearest_station(lat, lon)
                    if sd <= args.station_km:
                        anno = dict(city=city, lat=lat, lon=lon,
                                    erlangen_km=round(dist_e, 2), nearest_station=st["name"],
                                    station_km=round(sd, 2), direction=st["branch"],
                                    tier=st["tier"], line=st["line"],
                                    match="geocode", metro_approx=metro)
                    else:
                        rec_reason = f"no_station_within_{int(args.station_km)}km"
            net_calls += 1

        if anno:
            out = dict(job)
            out["commute"] = anno
            passing.append(out)
        elif rec_reason:
            rej = dict(job)
            rej["reject_reason"] = rec_reason
            rejected.append(rej)
        if rec_reason == "unresolved_location":
            unresolved.append(city)

    dt = time.time() - t0
    save_cache(cache)

    # ---------------- outputs
    os.makedirs(args.outdir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M")
    out_base = os.path.join(args.outdir, f"{args.prefix}_filtered_{ts}")
    json.dump(passing, open(out_base + ".json", "w"), ensure_ascii=False, indent=1)
    with open(out_base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cols = ["title", "company", "location", "commute_city", "commute_direction",
                "commute_station", "commute_station_km", "commute_erlangen_km",
                "commute_line", "date_posted", "is_remote", "job_url", "job_url_direct"]
        w.writerow(cols)
        for j in passing:
            c = j.get("commute", {})
            w.writerow([j.get("title"), j.get("company"), j.get("location"),
                        c.get("city"), c.get("direction"), c.get("nearest_station"),
                        c.get("station_km"), c.get("erlangen_km"), c.get("line"),
                        j.get("date_posted"), j.get("is_remote"),
                        j.get("job_url"), j.get("job_url_direct")])
    if args.save_rejected:
        json.dump(rejected, open(out_base + "_rejected.json", "w"), ensure_ascii=False, indent=1)

    # ---------------- report
    from collections import Counter
    by_city = Counter(p["commute"]["city"] for p in passing)
    by_station = Counter(p["commute"]["nearest_station"] for p in passing)
    by_dir = Counter(p["commute"]["direction"] for p in passing)
    by_reason = Counter(r["reject_reason"] for r in rejected)
    by_comp = Counter(p.get("company") or "?" for p in passing)
    tier_direct = sum(1 for p in passing if p["commute"]["tier"] == "trunk_direct")

    n_geo_input = len(jobs)
    rep = []
    rep.append(f"# Erlangen N-S Rail Corridor Filter — Report {ts}\n")
    rep.append(f"**Input**: {os.path.basename(args.input)} ({n_geo_input} jobs)  ")
    rep.append(f"**Constraint**: company on a rail line running north/south from Erlangen, "
               f"≤{int(args.max_km)} km from Erlangen center, ≤{args.station_km} km from a station\n")
    if pf_stats:
        rep.append(f"**Pre-filter**: {pf_stats['input']} -> {pf_stats['kept']} jobs "
                   f"({pf_stats['rejected']} removed by text/date rules)\n")
    rep.append("## Result\n")
    rep.append(f"| | jobs |")
    rep.append(f"|---|---|")
    rep.append(f"| **PASS (on corridor)** | **{len(passing)}** |")
    rep.append(f"| rejected | {len(rejected)} |")
    rep.append(f"| of which direct trains (no transfer) | {tier_direct} |")
    rep.append(f"| runtime | {dt:.1f}s ({net_calls} network lookups) |\n")
    rep.append("## Rejection reasons\n")
    rep.append("| reason | jobs |")
    rep.append("|---|---|")
    for reason, n in by_reason.most_common():
        rep.append(f"| {reason} | {n} |")
    rep.append("\n## Passing jobs by direction\n")
    for d_, n in by_dir.most_common():
        rep.append(f"- **{d_}**: {n}")
    rep.append("\n## Passing jobs by station\n")
    rep.append("| station | branch | jobs |")
    rep.append("|---|---|---|")
    stmap = {s["name"]: s for s in stations}
    for sname, n in by_station.most_common():
        s = stmap.get(sname, {})
        rep.append(f"| {sname} | {s.get('branch','')} | {n} |")
    rep.append("\n## Passing jobs by city\n")
    rep.append("| city | jobs |")
    rep.append("|---|---|")
    for city, n in by_city.most_common():
        rep.append(f"| {city} | {n} |")
    rep.append("\n## Top companies passing\n")
    rep.append("| company | jobs |")
    rep.append("|---|---|")
    for comp, n in by_comp.most_common(15):
        rep.append(f"| {comp} | {n} |")
    if unresolved:
        rep.append(f"\n## Unresolved locations ({len(unresolved)} jobs)\n")
        for u in sorted(set(unresolved)):
            rep.append(f"- {u}")
    rep.append("\n## Corridor definition (data/rail_corridor.json)\n")
    rep.append("**Trunk (direct S1/RE from Erlangen):** " +
               ", ".join(f"{s['name']} ({s['dist_km']} km)" for s in
                         sorted([s for s in stations if s['tier'] == 'trunk_direct'],
                                key=lambda x: (x['branch'], x['dist_km']))) + "\n")
    rep.append("**Same axis, 1 transfer (S2/RB/S5/RB-Bamberg):** " +
               ", ".join(f"{s['name']} ({s['dist_km']} km)" for s in
                         sorted([s for s in stations if s['tier'] == 'transfer1'],
                                key=lambda x: (x['branch'], x['dist_km']))) + "\n")
    rep.append("**Excluded branches (audit):** Feucht/Altdorf/Neumarkt (S2/S3 east legs), "
               "Lauf/Röthenbach/Hersbruck (S1 east leg), Ansbach/Wicklesgreuth/Heilsbronn (S4 west), "
               "Neustadt/Aisch+Emskirchen (S6 NW), **Herzogenaurach (adidas/Schaeffler HQ — "
               "Aurachtalbahn has NO passenger service; StUB tram planned)**\n")
    open(out_base + "_report.md", "w").write("\n".join(rep))
    json.dump(rep, open("/dev/null", "w"))  # no-op guard

    print(f"\n=== RESULT ===")
    if pf_stats:
        print(f"pre-filter: {pf_stats['input']} -> {pf_stats['kept']}")
    print(f"PASS:  {len(passing)}  ({tier_direct} direct-train)")
    print(f"FAIL:  {len(rejected)}")
    for reason, n in by_reason.most_common():
        print(f"   - {reason}: {n}")
    print(f"runtime: {dt:.1f}s | output: {out_base}.json/.csv/_report.md")

if __name__ == "__main__":
    main()
