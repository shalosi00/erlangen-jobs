#!/usr/bin/env python3
"""de_job_scan.py - Germany job scan via python-jobspy (Agentur fur Arbeit excluded by design).

Scrapes Indeed DE + LinkedIn for fresh software/AI roles in top German hubs,
saves CSV + JSON to download/, prints the top hits for scoring.
"""
import json, os, sys, time

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "download")
os.makedirs(OUT_DIR, exist_ok=True)

QUERIES = [
    # (search_term, location)
    ("software engineer", "Berlin, Germany"),
    ("AI engineer", "Munich, Germany"),
    ("python developer", "Remote (Germany)"),
]

def main():
    try:
        from jobspy import scrape_jobs
    except ImportError:
        sys.exit("jobspy not installed")

    import pandas as pd
    frames = []
    for term, loc in QUERIES:
        for site in (["indeed"], ["linkedin"]):
            try:
                print(f"[scan] {site} | {term} @ {loc}", flush=True)
                df = scrape_jobs(
                    site_name=site,
                    search_term=term,
                    location=loc,
                    results_wanted=15,
                    hours_old=168,          # last 7 days
                    country_indeed="Germany",
                    linkedin_fetch_description=True,
                )
                print(f"  -> {len(df)} jobs", flush=True)
                if len(df):
                    df["query"] = f"{term} @ {loc}"
                    frames.append(df)
            except Exception as e:
                print(f"  !! {site} failed: {str(e)[:180]}", flush=True)
            time.sleep(2)

    if not frames:
        sys.exit("no results from any board")

    all_df = pd.concat(frames).drop_duplicates(subset=["title", "company", "location"])
    stamp = time.strftime("%Y%m%d_%H%M", time.gmtime())
    csv_path = f"{OUT_DIR}/germany_jobs_{stamp}.csv"
    json_path = f"{OUT_DIR}/germany_jobs_{stamp}.json"
    cols = ["title", "company", "location", "date_posted", "job_url", "description",
            "min_amount", "max_amount", "currency", "query"]
    slim = all_df[[c for c in cols if c in all_df.columns]].copy()
    if "description" in slim.columns:
        slim["description"] = slim["description"].astype(str).str.slice(0, 900)
    slim.to_csv(csv_path, index=False)
    slim.head(40).to_json(json_path, orient="records", indent=1)
    print(f"saved {len(slim)} unique jobs -> {csv_path}", flush=True)

    for _, r in all_df.head(25).iterrows():
        pay = ""
        if r.get("min_amount"):
            pay = f" | {r.get('currency','EUR')} {r.get('min_amount')}–{r.get('max_amount','?')}"
        print(f"- {r['title']} @ {r['company']} ({r['location']}){pay}", flush=True)
        print(f"  {r['job_url'][:110]}", flush=True)

if __name__ == "__main__":
    main()
