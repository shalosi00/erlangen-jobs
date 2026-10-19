#!/usr/bin/env python3
"""merge_erlangen.py - union all Erlangen+50km sources into one master dataset.

Sources:
  1. download/erlangen_ALL_portals_<latest>.json  (jobspy sweep: indeed+linkedin+google)
  2. download/erlangen_50km_jobs_20261017_1630.csv (previous scan)
  3. career-ops data/scan-interamt*.json           (public-sector Interamt board)
Dedupe key: (title, company, location, url). Records with description win.
Output: download/erlangen_master_<stamp>.csv/.json + stats print.
"""
import json, glob, os, re, sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Pre-Filter: Negativ-Liste + Frische-Check VOR dem Schreiben des Masters
# (deaktivierbar mit: python3 scripts/merge_erlangen.py --no-prefilter)
NO_PREFILTER = "--no-prefilter" in sys.argv
if not NO_PREFILTER:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from job_prefilter import prefilter_jobs
    except ImportError:
        prefilter_jobs = None
        print("! job_prefilter.py nicht importierbar - Master wird UNGEFILTERT geschrieben")

OUT = os.path.join(BASE_DIR, "download")

def _arg(name, default=None):
    """Simple CLI: --name value (optional)."""
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

OUT = _arg("--outdir", OUT)
FRESH_DAYS = int(_arg("--fresh-days", 30))
os.makedirs(OUT, exist_ok=True)

def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())

def key(row):
    return (
        norm(row.get("title")),
        norm(row.get("company")),
        norm(row.get("location"))[:60],
        norm(row.get("job_url") or row.get("url")),
    )

rows, seen = [], {}
stats = {}

def add(row, source):
    row["source_portal"] = source
    k = key(row)
    if k in seen:
        old = seen[k]
        # prefer row that has a description
        if not old.get("description") and row.get("description"):
            seen[k] = row
            rows[rows.index(old)] = row
        stats[source] = stats.get(source, 0) + 1
        return False
    seen[k] = row
    rows.append(row)
    return True

# 1) jobspy sweep — raw sweeps live in data/raw/ (immutable scrape outputs);
#    fallback: OUT (legacy layout)
RAW = os.path.join(os.path.dirname(OUT), "data", "raw") if OUT.endswith("download") \
    else os.path.join(BASE_DIR, "data", "raw")
sweep_files = sorted(glob.glob(f"{RAW}/erlangen_ALL_portals_*.json") +
                     glob.glob(f"{OUT}/erlangen_ALL_portals_*.json"))
if sweep_files:
    data = json.load(open(sweep_files[-1]))
    for r in data:
        add(r, "jobspy-" + str(r.get("source_site") or r.get("site") or "?"))
    print(f"sweep file: {os.path.basename(sweep_files[-1])} -> {len(data)} rows")

# 2) previous scan (CSV)
prev_cands = sorted(glob.glob(f"{RAW}/erlangen_50km_jobs_*.csv") +
                    glob.glob(f"{OUT}/erlangen_50km_jobs_*.csv"))
prev = prev_cands[-1] if prev_cands else None
if prev and os.path.exists(prev):
    df = pd.read_csv(prev)
    n = 0
    for _, r in df.iterrows():
        if add({k: (None if pd.isna(v) else v) for k, v in r.items()}, "prev-scan"):
            n += 1
    print(f"prev scan: {len(df)} rows -> {n} added")

# 3) interamt (career-ops pipeline.md rows, region-filtered)
REGION = re.compile(r"Erlangen|Nürnberg|Nurnberg|Fürth|Bamberg|Bayreuth|Herzogenaurach|Schwabach|Ansbach|Lauf an der|Forchheim|Höchstadt", re.I)
pm = os.path.join(BASE_DIR, "data", "interamt_pipeline.md")
n = 0
if os.path.exists(pm):
    for line in open(pm):
        line = line.strip()
        m = re.match(r"^- \[.\]\s*(https?://\S+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)", line)
        if not m:
            continue
        url, company, title, loc = (g.strip() for g in m.groups())
        if not REGION.search(loc):
            continue
        posted = None
        pm2 = re.search(r"posted:\s*(\d{4}-\d{2}-\d{2})", line)
        if pm2:
            posted = pm2.group(1)
        if add({"title": title, "company": company, "location": loc, "job_url": url,
                "description": None, "date_posted": posted}, "interamt"):
            n += 1
print(f"interamt (region-filtered from pipeline.md): {n} added")

# Save master
stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M")

# Pre-Filter VOR dem CSV-Schreiben (Negativ-Liste + 30-Tage-Frische)
if not NO_PREFILTER and prefilter_jobs:
    n_in = len(rows)
    rows, rejected, pf = prefilter_jobs(rows, fresh_days=FRESH_DAYS)
    print(f"\nPRE-FILTER: {n_in} -> {len(rows)} rows "
          f"({len(rejected)} entfernt, {len(rejected)/max(1,n_in)*100:.1f}%)")
    for reason, n in sorted(pf["by_rule"].items(), key=lambda x: -x[1]):
        print(f"   - {reason}: {n}")
    print(f"   (Junior-Ausnahme behielt {pf['kept_by_junior_exception']}, "
          f"FP-Guard behielt {pf['kept_by_fp_guard']})")
    rj = f"{OUT}/erlangen_master_{stamp}_prefilter_rejected.json"
    json.dump(rejected, open(rj, "w"), default=str, ensure_ascii=False, indent=1)
    print(f"   rejected audit: {rj}")

mj = f"{OUT}/erlangen_master_{stamp}.json"
mc = f"{OUT}/erlangen_master_{stamp}.csv"
json.dump(rows, open(mj, "w"), default=str, ensure_ascii=False)
pd.DataFrame(rows).to_csv(mc, index=False)

print(f"\nMASTER (vorgefiltert): {len(rows)} unique jobs")
print(f"  json: {mj}")
print(f"  csv : {mc}")
print("\nby portal:")
by = {}
for r in rows:
    p = r["source_portal"]
    by[p] = by.get(p, 0) + 1
for p, c in sorted(by.items(), key=lambda x: -x[1]):
    print(f"  {p:24s} {c}")
dup_hits = {k: v for k, v in stats.items() if v}
print(f"\ncross-source overlaps absorbed: {dup_hits}")

with_sal = sum(1 for r in rows if r.get("salary_min_amount") or r.get("salary_max_amount") or r.get("min_amount") or r.get("max_amount"))
remote = sum(1 for r in rows if str(r.get("is_remote") or "").lower() in ("true", "1"))
print(f"with salary: {with_sal} | remote-flagged: {remote}")
