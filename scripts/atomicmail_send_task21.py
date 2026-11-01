#!/usr/bin/env python3
"""Task 21 email: methodology research + perfect-files system to skorry@atomicmail.io."""
import json
import subprocess

BASE = "/home/z/my-project"
OPS = f"{BASE}/scripts/atomicmail_daily_ops.json"
PDF = f"{BASE}/download/reports/Job_Search_Methodology_and_Results_Organization_2026-10-15.pdf"
CSV = f"{BASE}/download/tracker/application_tracker_2026-10-15.csv"

BODY = """Hi Asha,

Task 21 done: internet research on HOW to run a job search and HOW to
organize the results — then the findings implemented as "perfect files".

THE RESEARCH (report attached, 10 pages, every claim sourced)
- The funnel model is the standard: ~32 applications -> 4 interviews ->
  1 offer (2025 avg); median 68.5 days to first offer; ~250 resumes per
  posting; 97.4% of Fortune 500 filter via an ATS before humans read.
- Timing: 41% of all applications land within 48h of posting (St. Louis
  Fed); Tue-Thu mornings get ~30% better response.
- Follow-up: wait 5-7 business days after applying, then one polite note.
- Files: CESSDA/UK-Data-Service rules — YYYY-MM-DD names, hyphens,
  folders beat name-only conventions, stable pointers for "current".
- Germany calibration: a logged junior-IT search took 11 months at 12.5
  applications/month (7.1% interview rate); 3-6 months is normal here;
  3-5 h per tailored application.

WHAT SHIPPED (all git-committed)
1. download/ reorganized from 35 flat files into:
   daily/YYYY-MM-DD/  (immutable run history)
   reports/  tracker/  archive/  + README runbook
   Root keeps only 2 stable pointers (jobs_latest.csv/json).
   New script scripts/organize_downloads.py maintains the layout and
   now runs as step 5/6 inside daily_jobpull.sh.
2. download/tracker/application_tracker_2026-10-15.xlsx (+ CSV twin,
   attached): one row per posting, 46 rows pre-seeded from yesterday's
   run, status funnel (discovered -> shortlisted -> applied ->
   interviewing -> offer / closed), follow-up date auto-fills +7 days
   once marked applied, overdue follow-ups highlighted, live metrics
   sheet (stage conversion, source yield) and a Playbook sheet.
3. The 10-page report (attached PDF).

FRIDAY REVIEW (the 10-minute habit the research says wins the search)
- Clear overdue follow-ups (target: 0).
- Review every "discovered" row: shortlist or close, never let them pile.
- Read the conversion rates; fix the leaking stage, not the loudest one.
- Commit the tracker to git.

BACKUP NOTE
v9 bundle created + verified locally (147,959,460 B,
sha256 7d2cdaf5...a0ab8) but ALL five mirror hosts rejected uploads today
(litterbox 413/403, filebin API regression, catbox 412 after full upload,
x0.at size ban, 0x0.st unreachable). Retry recipe documented in
BACKUPS.md; v8 mirrors still live; deliverables travel here as attachments.

- Asha's job-toolkit agent (Task 21, 2026-10-15)
"""

vars_ = {"TO": "skorry@atomicmail.io",
         "SUBJECT": "Task 21: job-search methodology report + perfect-files system (PDF+CSV)",
         "BODY": BODY}
cmd = ["npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
       "jmap_request", "--ops-file", OPS,
       "--attachment", PDF, "--attachment", CSV,
       "--vars", json.dumps(vars_)]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=BASE)
out = (r.stdout or "") + (r.stderr or "")
print(out[-1400:])
print("RC:", r.returncode)
