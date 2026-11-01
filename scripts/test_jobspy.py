#!/usr/bin/env python3
"""Live test: python-jobspy (speedyapply/JobSpy) against the German market.
Read-only guest scraping; small result counts; no credentials."""
import sys, traceback

OUT = "/home/z/my-project/research/github-repos/tests"
import os
os.makedirs(OUT, exist_ok=True)

def run(label, **kw):
    from jobspy import scrape_jobs
    print(f"\n=== {label} ===")
    try:
        jobs = scrape_jobs(**kw)
        n = len(jobs)
        print(f"rows: {n}")
        if n:
            cols = [c for c in ["title", "company", "location", "date_posted",
                                "min_amount", "max_amount", "currency", "job_url"] if c in jobs.columns]
            print(jobs[cols].head(8).to_string())
            fn = f"{OUT}/jobspy_{label}.csv"
            jobs.to_csv(fn, index=False)
            print(f"saved -> {fn}  | columns: {list(jobs.columns)}")
        return n
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {str(e)[:300]}")
        return None

# Test 1: Indeed Germany — FISI around Erlangen (core use case)
n1 = run("indeed_fisi_erlangen",
         site_name=["indeed"], search_term="Fachinformatiker",
         location="Erlangen", results_wanted=15, hours_old=21 * 24,
         country_indeed="germany")

# Test 2: Indeed Germany — broader junior IT support, 50 km commute radius
n2 = run("indeed_itsupport_nuremberg",
         site_name=["indeed"], search_term="IT-Support",
         location="Nürnberg", results_wanted=15, hours_old=21 * 24,
         country_indeed="germany")

# Test 3: LinkedIn guest mode (expected flaky without credentials/proxies)
n3 = run("linkedin_guest",
         site_name=["linkedin"], search_term="Systemintegration",
         location="Germany", results_wanted=10, hours_old=21 * 24)

# Test 4: Glassdoor Germany (often needs cookie/extractor warm-up)
n4 = run("glassdoor_guest",
         site_name=["glassdoor"], search_term="IT Support",
         location="Nürnberg, Germany", results_wanted=10, country_indeed="germany")

print("\n=== SUMMARY ===")
print(f"indeed_fisi_erlangen:      {n1}")
print(f"indeed_itsupport_nuremberg:{n2}")
print(f"linkedin_guest:            {n3}")
print(f"glassdoor_guest:           {n4}")
