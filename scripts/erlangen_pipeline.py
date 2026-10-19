#!/usr/bin/env python3
"""
erlangen_pipeline.py — ONE command, ONE output CSV.

Full chain (all stages support the new filtering options):
  1. merge_erlangen.py   union all raw sweeps -> dedupe -> PRE-FILTER
                         (Negativ-Liste: Ausbildung/Student, Senior/Mgmt mit
                          Junior-Ausnahme + FP-Guard, Fremdberufe; Frische-Check
                          date_posted <= --fresh-days)
  2. commute_filter.py   rail-corridor geo filter (S1 N-S trunk, <=50 km,
                         <=3 km station) — uses cached gazetteer, no network
  3. final CSV           download/erlangen_jobs_final_<stamp>.csv
                         sorted by commute distance, with age_days column

Intermediate files stay in --workdir (default data/work); download/ gets
EXACTLY ONE new CSV.

Usage:
  python3 scripts/erlangen_pipeline.py --sweep            # 0. sweep portals first (fresh setup)
  python3 scripts/erlangen_pipeline.py                    # full run (uses existing sweeps)
  python3 scripts/erlangen_pipeline.py --fresh-days 14    # tighter freshness
  python3 scripts/erlangen_pipeline.py --input <master.json> # skip merge step
  python3 scripts/erlangen_pipeline.py --no-prefilter     # geo filter only
  python3 scripts/erlangen_pipeline.py --station-km 2.0 --max-km 40

Scoring (optional, separate LLM pass):
  python3 scripts/de_job_score.py        # reads the newest erlangen_jobs_final_*.csv
"""
import argparse, csv, glob, json, os, subprocess, sys, time
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD = os.path.join(BASE, "download")
SCRIPTS = os.path.join(BASE, "scripts")

FINAL_COLS = ["title", "company", "location", "city", "direction", "station",
              "station_km", "erlangen_km", "line", "date_posted", "age_days",
              "is_remote", "source_portal", "job_url", "job_url_direct"]

def run(cmd):
    print(f"\n$ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(f"stage failed: {' '.join(cmd)}")

def newest(pattern, d):
    files = sorted(glob.glob(os.path.join(d, pattern)))
    return files[-1] if files else None

def _split_parts(src, parts):
    """Stage 5: record-aware split (multiline description fields safe)."""
    import csv as _csv
    with open(src, newline="", encoding="utf-8") as f:
        reader = _csv.DictReader(f)
        fieldnames, rows = reader.fieldnames, list(reader)
    n = len(rows)
    size = (n + parts - 1) // parts
    base = os.path.splitext(src)[0]
    made = []
    for i in range(parts):
        chunk = rows[i * size: min((i + 1) * size, n)]
        if not chunk and i:
            break
        p_csv = f"{base}_part{i + 1}_of_{parts}.csv"
        p_json = f"{base}_part{i + 1}_of_{parts}.json"
        with open(p_csv, "w", newline="", encoding="utf-8") as f:
            w = _csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(chunk)
        with open(p_json, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False, default=str)
        made.append((p_csv, len(chunk)))
    total = sum(c for _, c in made)
    if total != n:
        sys.exit(f"parts integrity FAIL: {total} != {n}")
    print(f"stage 5: split into {len(made)} parts "
          f"({', '.join(f'{os.path.basename(p)}={c}' for p, c in made)}) "
          f"— integrity OK ({total} == {n})")

def _enrich_file(csv_path, args):
    """Stage 6: add company_address + lat/lon (map-ready) to the final CSV."""
    cmd = [sys.executable, os.path.join(SCRIPTS, "enrich_addresses.py"),
           "--input", csv_path, "--out", csv_path, "--budget-sec", "1500"]
    if args.allow_direct:
        cmd.append("--allow-direct")
    run(cmd)
    print(f"stage 6: geo-enriched {csv_path}")

def _map_file(csv_path):
    """Stage 7: render the geocoded final CSV into a self-contained Leaflet map."""
    run([sys.executable, os.path.join(SCRIPTS, "build_map.py"), "--input", csv_path])
    print(f"stage 7: map written to {os.path.join(BASE, 'map')}")


def main():
    ap = argparse.ArgumentParser(description="Erlangen job pipeline -> one final CSV")
    ap.add_argument("--input", default=None,
                    help="skip merge, use this master JSON as start")
    ap.add_argument("--sweep", nargs="?", const=0, type=int, default=None, metavar="N",
                    help="stage 0: scrape Indeed/LinkedIn/Google first (fresh setup). "
                         "Optional N = only first N queries per site (smoke)")
    ap.add_argument("--workdir", default=os.path.join(BASE, "data", "work"))
    ap.add_argument("--out", default=None, help="final CSV path (default download/erlangen_jobs_final_<stamp>.csv)")
    ap.add_argument("--fresh-days", type=int, default=30,
                    help="pre-filter: max age of date_posted (default 30)")
    ap.add_argument("--no-fp-guard", action="store_true",
                    help="pre-filter: disable senior/mgmt FP guard")
    ap.add_argument("--no-prefilter", action="store_true",
                    help="skip the text/date pre-filter entirely (geo only)")
    ap.add_argument("--station-km", type=float, default=3.0)
    ap.add_argument("--max-km", type=float, default=50.0)
    ap.add_argument("--include-remote", action="store_true")
    ap.add_argument("--no-network", action="store_true")
    ap.add_argument("--fetch-desc", action="store_true",
                    help="stage 4: visit every job page, collect FULL descriptions "
                         "(linkedin public pages + indeed re-search + direct URLs; "
                         "checkpointed, resumable, self-adaptive networking) "
                         "-> final CSV sorted by date")
    ap.add_argument("--limit-desc", type=int, default=0,
                    help="fetch-desc: only first N missing jobs (smoke/e2e)")
    ap.add_argument("--desc-checkpoint", default=None,
                    help="fetch-desc: alternative checkpoint path (isolatable for tests)")
    ap.add_argument("--desc-phase", default="all", choices=["all", "li", "direct", "indeed", "csv"],
                    help="fetch-desc: restrict to one phase (li = fast e2e test)")
    ap.add_argument("--no-proxy", action="store_true",
                    help="fetch-desc: disable proxy pool — REQUIRES --allow-direct "
                         "(otherwise your IP would touch job portals)")
    ap.add_argument("--allow-direct", action="store_true",
                    help="opt-out of strict no-IP mode: allow DIRECT connections "
                         "as last resort (uses YOUR IP — not recommended)")
    ap.add_argument("--proxy-refresh", action="store_true",
                    help="fetch-desc: harvest+validate free proxies first "
                         "(otherwise done automatically when the pool is low)")
    ap.add_argument("--parts", type=int, default=0,
                    help="stage 5: split the final CSV into N parts "
                         "(record-aware, order preserved; writes "
                         "<out>_part{i}_of_N.csv/.json). 0 = off")
    ap.add_argument("--enrich-geo", action="store_true",
                    help="stage 6: add company_address + lat/lon columns "
                         "(map-ready; Google if GOOGLE_MAPS_API_KEY set, else "
                         "Photon/zippopotam via proxy pool + offline gazetteer; "
                         "cached, resumable)")
    ap.add_argument("--build-map", action="store_true",
                    help="stage 7: render the final CSV into map/index.html "
                         "(self-contained Leaflet map; needs lat/lon, so run "
                         "together with --enrich-geo or on a geocoded CSV)")
    args = ap.parse_args()

    if args.no_proxy and not args.allow_direct:
        sys.exit("--no-proxy would expose your IP to job portals -> refused.\n"
                 "Add --allow-direct if you really want that (not recommended).")

    os.makedirs(args.workdir, exist_ok=True)
    os.makedirs(DOWNLOAD, exist_ok=True)
    os.makedirs(os.path.join(BASE, "data", "raw"), exist_ok=True)
    if args.allow_direct:
        os.environ["ERL_ALLOW_DIRECT"] = "1"   # inherited by every stage
    t0 = time.time()
    today = date.today()

    # ---- stage 0 (optional): portal sweep --------------------------------
    raw_glob = glob.glob(os.path.join(BASE, "data", "raw", "erlangen_ALL_portals_*.json"))
    if args.sweep is None and not raw_glob and not args.input and not args.no_network:
        sys.exit("no portal sweeps found in data/raw/.\n"
                 "Run once with --sweep to scrape Indeed/LinkedIn/Google first:\n"
                 "  python3 scripts/erlangen_pipeline.py --sweep\n"
                 "(or pass --input <master.json> / --no-network for offline runs)")
    if args.sweep is not None:
        cmd = [sys.executable, os.path.join(SCRIPTS, "erlangen_all_portals.py")]
        if args.sweep:
            cmd += ["--queries", str(args.sweep)]
        if args.allow_direct:
            cmd.append("--allow-direct")
        if args.proxy_refresh:
            cmd.append("--proxy-refresh")
        run(cmd)

    # ---- stage 1: merge + pre-filter ------------------------------------
    if args.input:
        master = args.input
        print(f"stage 1 skipped (--input): {master}")
    else:
        cmd = [sys.executable, os.path.join(SCRIPTS, "merge_erlangen.py"),
               "--outdir", args.workdir, "--fresh-days", str(args.fresh_days)]
        if args.no_prefilter:
            cmd.append("--no-prefilter")
        run(cmd)
        cands = [f for f in sorted(glob.glob(os.path.join(args.workdir, "erlangen_master_*.json")))
                 if "_prefilter_rejected" not in os.path.basename(f)]
        if not cands:
            sys.exit("no master JSON produced by merge stage")
        master = cands[-1]
        print(f"stage 1 master: {master}")

    # ---- stage 2: rail-corridor geo filter ------------------------------
    # Text pre-filter happened in stage 1 (merge). The geo stage only re-applies
    # it if we STARTED from a raw --input file (then it runs there).
    run_geo_prefilter = bool(args.input) and not args.no_prefilter
    cmd = [sys.executable, os.path.join(SCRIPTS, "commute_filter.py"),
           "--input", master, "--outdir", args.workdir,
           "--station-km", str(args.station_km), "--max-km", str(args.max_km)]
    if run_geo_prefilter:
        cmd += ["--prefilter", "--fresh-days", str(args.fresh_days)]
        if args.no_fp_guard:
            cmd.append("--no-fp-guard")
    if args.include_remote:
        cmd.append("--include-remote")
    if args.no_network:
        cmd.append("--no-network")
    run(cmd)
    filtered = newest("erlangen_commute_filtered_*.json", args.workdir)
    if not filtered:
        sys.exit("no commute-filtered JSON produced")
    print(f"stage 2 output: {filtered}")

    # ---- stage 4 (optional): full job descriptions + date-sorted CSV -------
    if args.fetch_desc:
        cmd = [sys.executable, os.path.join(SCRIPTS, "fetch_descriptions.py"),
               "--input", filtered, "--phase", args.desc_phase, "--write-csv",
               "--workers", "3", "--li-min", "1.2", "--li-max", "2.8"]
        if args.limit_desc:
            cmd += ["--limit", str(args.limit_desc)]
        if args.desc_checkpoint:
            cmd += ["--checkpoint", args.desc_checkpoint]
        if args.no_proxy:
            cmd.append("--no-proxy")
        if args.allow_direct:
            cmd.append("--allow-direct")
        if args.proxy_refresh:
            cmd.append("--proxy-refresh")
        if args.out:
            cmd += ["--out", args.out]
        run(cmd)
        fin = newest(os.path.join(DOWNLOAD, "erlangen_jobs_final_*.csv"), DOWNLOAD) \
            if not args.out else args.out
        print(f"\n=== FINAL (with descriptions, sorted by date) ===")
        print(f"output: {fin}")
        if args.enrich_geo:
            _enrich_file(fin, args)
        if args.build_map:
            _map_file(fin)
        if args.parts:
            _split_parts(fin, args.parts)
        return

    # ---- stage 3: ONE final CSV ------------------------------------------
    jobs = json.load(open(filtered))
    for j in jobs:
        d = str(j.get("date_posted") or "")[:10]
        try:
            j["age_days"] = (today - date.fromisoformat(d)).days if d else ""
        except ValueError:
            j["age_days"] = ""
    def sort_key(j):
        try:
            km = float(j.get("commute", {}).get("erlangen_km", 999))
        except (TypeError, ValueError):
            km = 999
        return (km, str(j.get("date_posted") or ""), str(j.get("company") or ""))
    jobs.sort(key=sort_key)

    out = args.out or os.path.join(DOWNLOAD, f"erlangen_jobs_final_{today.strftime('%Y%m%d')}.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FINAL_COLS)
        for j in jobs:
            c = j.get("commute", {})
            w.writerow([j.get("title"), j.get("company"), j.get("location"),
                        c.get("city"), c.get("direction"), c.get("nearest_station"),
                        c.get("station_km"), c.get("erlangen_km"), c.get("line"),
                        j.get("date_posted"), j.get("age_days"), j.get("is_remote"),
                        j.get("source_portal"), j.get("job_url"), j.get("job_url_direct")])

    if args.parts:
        _split_parts(out, args.parts)
    if args.enrich_geo:
        _enrich_file(out, args)
    if args.build_map:
        _map_file(out)

    dt = time.time() - t0
    from collections import Counter
    by_dir = Counter(j["commute"]["direction"] for j in jobs)
    print(f"\n=== FINAL ===")
    print(f"{len(jobs)} jobs -> {out}  ({dt:.1f}s total)")
    print("by direction:", dict(by_dir.most_common()))
    print(f"columns: {', '.join(FINAL_COLS)}")

if __name__ == "__main__":
    main()
