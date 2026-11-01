#!/usr/bin/env python3
"""erlangen_all_portals.py - EVERY-portal sweep for Erlangen, Germany +50km.

Phases:
  A) indeed + linkedin, 18 broad bilingual queries, 60d window, 250/query
  B) google (aggregates StepStone/Xing/Monster/Glassdoor...) with location fallbacks
Crash-safe: incremental JSON save after every scrape; dedupe on (title,company,location,url).

Self-adaptive networking: STRICT proxy mode — every scrape call runs through
rotating proxies (net_resilience pool; env PROXY_LIST / data/proxies.txt /
auto-harvest).  The user's real IP is NEVER used: if no healthy proxy exists
the pool auto-refills, and if that still yields nothing the site is SKIPPED
honestly (never scraped directly).  Per-site pause adapts AIMD-style.
Opt-out only via --allow-direct (uses your IP — not recommended).

Output: data/raw/erlangen_ALL_portals_<stamp>.json + download/erlangen_ALL_portals_<stamp>.csv
"""
import argparse, json, os, sys, time, csv, traceback, random
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import net_resilience as nr

# Pre-Filter: Negativ-Liste + Frische-Check VOR der CSV-Schreibung
# (JSON bleibt ungefiltert als Audit-/Merge-Quelle; deaktivierbar: --no-prefilter)
from job_prefilter import prefilter_jobs

import pandas as pd
from jobspy import scrape_jobs

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)
OUT_DIR = os.path.join(BASE, "download")
RAW_DIR = os.path.join(BASE, "data", "raw")
LOG = os.path.join(BASE, "erlangen_all.log")
STAMP = time.strftime("%Y%m%d_%H%M")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG), exist_ok=True)

LOCATION = "Erlangen, Germany"
DISTANCE_MI = 31  # ~50 km
HOURS_OLD = 1440  # 60 days
RESULTS_WANTED = 250

QUERIES = [
    "", "engineer", "Ingenieur", "software", "developer", "IT", "Entwickler",
    "data", "Vertrieb", "Kaufmännisch", "Praktikum", "Werkstudent",
    "Techniker", "Medizin", "Logistik", "research", "marketing", "finance",
]
GOOGLE_LOCATION_FALLBACKS = ["Erlangen", "Nuremberg, Germany", "Bavaria, Germany", "Germany"]
GOOGLE_QUERIES = ["engineer", "software", "Entwickler", "IT", "jobs"]

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def key_of(row):
    return (
        str(row.get("title", "")).strip().lower(),
        str(row.get("company", "")).strip().lower(),
        str(row.get("location", "")).strip().lower(),
        str(row.get("job_url", "")).strip(),
    )

def trim(row):
    d = row.get("description")
    if isinstance(d, str) and len(d) > 900:
        row["description"] = d[:900]
    return row

def main():
    ap = argparse.ArgumentParser(description="ALL-portals sweep for Erlangen +50km")
    ap.add_argument("--no-prefilter", action="store_true", help="write CSV unfiltered")
    ap.add_argument("--allow-direct", action="store_true",
                    help="opt-out of strict no-IP mode: permit direct scrapes "
                         "when no proxy is available (uses YOUR IP — not recommended)")
    ap.add_argument("--proxy-refresh", action="store_true", help="harvest+validate free proxies first")
    ap.add_argument("--proxy-min", type=int, default=5)
    ap.add_argument("--queries", type=int, default=0, help="only first N queries per site (smoke)")
    args = ap.parse_args()

    # ---- self-adaptive network setup (strict: never the user's IP) -----
    if args.allow_direct:
        os.environ["ERL_ALLOW_DIRECT"] = "1"
    pool = nr.ProxyPool(state_file=nr.POOL_STATE)       # ONE shared pool state
    if args.proxy_refresh:
        pool.harvest(min_healthy=args.proxy_min)
    elif pool.healthy_count() < args.proxy_min:
        pool.ensure(min_healthy=args.proxy_min)         # self-adjusting refill
    if pool.healthy_count():
        log(f"net: {pool.healthy_count()} healthy proxies "
            f"(strict rotation ON — your IP is never used)")
    else:
        log("net: NO healthy proxies -> strict mode: sites will be SKIPPED "
            "honestly, never scraped from your IP")
    mode = "allow-direct" if args.allow_direct else "strict-no-direct"
    nr.health_dump({"script": "erlangen_all_portals", "mode":
                    f"{mode}:pool:{pool.healthy_count()}"})

    seen, rows = set(), []
    out_json = f"{RAW_DIR}/erlangen_ALL_portals_{STAMP}.json"
    # AIMD per site: base pause, doubles on failure (cap 120s), decays when clean
    site_gap = {"indeed": [6.0, 6.0], "linkedin": [30.0, 30.0], "google": [8.0, 8.0]}
    site_px_fails = {"indeed": 0, "linkedin": 0, "google": 0}

    def adapt(site, ok):
        base, cur = site_gap[site]
        cur = max(base, cur * 0.75) if ok else min(120.0, max(base, cur * 2.0))
        site_gap[site][1] = cur
        return cur * random.uniform(0.9, 1.15)

    def add(df, site, tag):
        n_new = 0
        if df is None or len(df) == 0:
            return 0
        for _, r in df.iterrows():
            row = {k: (None if pd.isna(v) else v) for k, v in r.items()}
            row["source_site"] = row.get("site") or site
            k = key_of(row)
            if k in seen:
                continue
            seen.add(k)
            rows.append(trim(row))
            n_new += 1
        log(f"  {tag}: +{n_new} new (total {len(rows)})")
        return n_new

    class NoProxySkip(Exception):
        """Raised when strict mode has no proxy -> site skipped, never direct."""

    def scrape(site, term, loc, results=RESULTS_WANTED, hours=HOURS_OLD):
        use_px = pool.as_list()
        if not use_px:
            # strict: auto-refill once, then skip — NEVER scrape from your IP
            pool.ensure(min_healthy=1)
            use_px = pool.as_list()
            if not use_px:
                if args.allow_direct:
                    use_px = None            # explicit opt-out: direct allowed
                    log(f"  {site}: no proxy + --allow-direct -> DIRECT (YOUR IP)")
                else:
                    raise NoProxySkip(
                        f"no healthy proxy for {site} (strict: your IP is never used)")
        try:
            df = scrape_jobs(
                site_name=[site],
                search_term=term,
                location=loc,
                distance=DISTANCE_MI,
                results_wanted=results,
                hours_old=hours,
                country_indeed="Germany",
                linkedin_fetch_description=False,
                verbose=0,
                proxies=use_px,
            )
            if use_px:
                site_px_fails[site] = 0        # proxies working again
            return df
        except Exception:
            if use_px:
                site_px_fails[site] += 1
                if site_px_fails[site] >= 2:
                    # self-adjusting: re-harvest proxies before the next query
                    log(f"  {site}: {site_px_fails[site]} proxy failures in a "
                        f"row -> refreshing pool (never falling back to your IP)")
                    pool.ensure(min_healthy=args.proxy_min)
            raise

    queries_a = QUERIES[: args.queries] if args.queries else QUERIES

    # Phase A: indeed + linkedin
    for site, _base in (("indeed", 6), ("linkedin", 30)):
        for q in queries_a:
            try:
                df = scrape(site, q, LOCATION)
                add(df, site, f"{site} '{q}' rows={len(df)}")
                site_gap[site][1] = adapt(site, True)
            except NoProxySkip as e:
                log(f"  {site} '{q}' SKIPPED: {e}")
                site_gap[site][1] = adapt(site, False)
            except Exception as e:
                log(f"  {site} '{q}' FAIL: {str(e)[:120]}")
                site_gap[site][1] = adapt(site, False)
            with open(out_json, "w") as f:
                json.dump(rows, f, default=str, ensure_ascii=False)
            time.sleep(site_gap[site][1])

    # Phase B: google with location fallbacks (aggregator)
    for loc in GOOGLE_LOCATION_FALLBACKS:
        got_any = False
        for q in GOOGLE_QUERIES:
            try:
                df = scrape("google", q, loc)
                n = add(df, "google", f"google '{q}' @'{loc}' rows={len(df)}")
                if n:
                    got_any = True
                time.sleep(adapt("google", True))
            except NoProxySkip as e:
                log(f"  google '{q}' @'{loc}' SKIPPED: {e}")
                time.sleep(adapt("google", False))
            except Exception as e:
                log(f"  google '{q}' @'{loc}' FAIL: {str(e)[:120]}")
                time.sleep(adapt("google", False))
        log(f"google location '{loc}' -> got_any={got_any}")
        if got_any:
            break

    # Final save: JSON (roh) + CSV (vorgefiltert)
    with open(out_json, "w") as f:
        json.dump(rows, f, default=str, ensure_ascii=False)
    csv_rows = rows
    if not args.no_prefilter and rows:
        csv_rows, rej, pf = prefilter_jobs(rows)
        log("pre-filter CSV: %d -> %d rows (%d removed: %s)"
            % (len(rows), len(csv_rows), len(rej),
               ", ".join(f"{k}={v}" for k, v in sorted(pf["by_rule"].items(),
                                                      key=lambda x: -x[1]))))
    csv_path = out_json.replace(".json", ".csv").replace(RAW_DIR, OUT_DIR)
    if csv_rows:
        pd.DataFrame(csv_rows).to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
    pool.save()
    log(f"DONE total={len(rows)} json={out_json} csv={csv_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL " + traceback.format_exc()[-500:])
        sys.exit(1)
