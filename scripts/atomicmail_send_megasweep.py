#!/usr/bin/env python3
"""Send the MEGA SWEEP results via Atomic Mail JMAP (reuses daily ops template).
Run scripts/atomicmail_recover.py first (standing rule)."""
import json
import subprocess
import sys
from pathlib import Path

BASE = "/home/z/my-project"
OPS = f"{BASE}/scripts/atomicmail_daily_ops.json"
D = f"{BASE}/download/mega_sweep_2026-10-30"
ATT = [f"{D}/mega_sweep_summary_20261030-1638.md",
       f"{D}/junior_shortlist_20261030-1638.csv",
       f"{D}/master_ALL_20261030-1638.csv"]

BODY = """Hi Asha,

MEGA SWEEP done - the insanely large job search you asked for, then filtered
to junior. Funnel:

- Raw rows fetched: 4,907 (BA bulk + 20 portals + daily)
- MASTER unique postings: 3,788 (deduped across all sources)
- FISI-relevant titles: 470
- Junior strong (title-level): 43 | Junior medium (description-level): 566
- **JUNIOR SHORTLIST (relevant AND strong/medium): 78 postings**

HOW IT WAS BUILT
1. BA Jobsuche v6 bulk: 14 IT queries (Fachinformatiker Systemintegration,
   Systemadministrator, IT-Support, EDV, IT-Service, ...) x 2 geo-tiers
   (Erlangen 50 km + Nuernberg 100 km) x 90-day window, no Ausbildung, no
   agencies -> 3,137 unique postings.
2. Deep-fetched full descriptions for all 2,713 non-excluded candidates
   (100% success) to catch description-level entry signals.
3. Wide portal run: kimeta, XING, Talent, Get-in-IT, Stellenanzeigen.de,
   Indeed, LinkedIn, EURES, Arbeitnow, InFranken, Connecticum + more
   (30-day window, Nuernberg 100 km).
4. 3-layer dedupe (canonical URL + fuzzy title/company/city) + junior
   classification (strong/medium/weak/excluded) with evidence per row.

KEY FACTS
- 78 junior-relevant postings ready to work, ranked strong-first, newest-first.
- 15 are explicit junior/1st-level titles (Junior IT-Administrator ncsolution,
  NConsult x2, Simba-Dickie Fürth, Neumüller Nürnberg, ...).
- 1,194 postings are long-running (first published >90 days ago but STILL
  LIVE) - those employers struggle to fill, prime junior targets.
- All 3,788 postings absorbed into job memory (jobs_history.db) so the daily
  run now tracks new/gone against this baseline.

ATTACHED
1. mega_sweep_summary - funnel stats + method
2. junior_shortlist CSV - the 78 rows to work top-down
3. master_ALL CSV - all 3,788 with junior_class + relevance + freshness flags

Known gaps: Indeed/LinkedIn needed a library reinstall (wipe aftermath) and
4 keyed APIs (Adzuna/Jooble/Careerjet/WhatJobs) need API keys we don't hold;
volume therefore leans on the BA API (the largest, cleanest source anyway).

- Asha's job-toolkit agent (2026-10-30)
"""

attachments = [p for p in ATT if Path(p).exists()]
if len(attachments) != 3:
    print("MISSING:", [p for p in ATT if not Path(p).exists()])
    sys.exit(2)

rc_all = 0
results = {}
for to in ["skorry@atomicmail.io", "feebee231@outlook.com"]:
    vars_ = {"TO": to,
             "SUBJECT": "MEGA SWEEP: 3,788 postings -> 78 junior targets (BA bulk 14x queries x 2 tiers)",
             "BODY": BODY}
    r = subprocess.run(["npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
                        "jmap_request", "--ops-file", OPS] +
                       sum([["--attachment", a] for a in attachments], []) +
                       ["--vars", json.dumps(vars_)],
                       capture_output=True, text=True, timeout=300, cwd=BASE)
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "notCreated" in out and ": null" in out
    results[to] = "sent" if ok else f"FAILED rc={r.returncode}"
    print(f"[{to}] {results[to]}")
    if not ok:
        print(out[-500:])
        rc_all = 1
json.dump(results, open(f"{BASE}/scripts/atomicmail_megasweep_result.json", "w"), indent=1)
sys.exit(rc_all)
