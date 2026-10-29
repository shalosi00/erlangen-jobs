#!/usr/bin/env python3
"""Send Asha's FISI job-toolkit deliverables via Atomic Mail JMAP to skorry@atomicmail.io."""
import json, subprocess, sys, os

BASE = "/home/z/my-project"
CSV = f"{BASE}/download/jobs_fachinformatiker-systemintegration-erlangen-50km-14d_20261013-1952.csv"
JSN = f"{BASE}/download/jobs_fachinformatiker-systemintegration-erlangen-50km-14d_20261013-1952.json"
PDF = f"{BASE}/download/Programmatic_Job_Hunting_Germany_Systemintegration.pdf"
OPS = f"{BASE}/scripts/atomicmail_send_ops.json"

BODY = """Hi Asha,

Here is the full delivery of your zero-cost programmatic job-hunting toolkit
(FISI junior roles, Erlangen + 50 km). This mail is sent from your agent's own
mailbox: asha.jobtoolkit@atomicmail.ai

WHAT IS ATTACHED (3 files)
1. jobs_fachinformatiker-systemintegration-erlangen-50km-14d_20261013-1952.csv
   Latest production pull: 42 unique postings, hard filters applied
   (fulltime only, no Ausbildung, no part-time, no experience required).
2. ..._20261013-1952.json — same data with full per-posting detail + source.
3. Programmatic_Job_Hunting_Germany_Systemintegration.pdf
   30-page data-source report (all channels evaluated for your region).

PIPELINE STATUS (as of 2026-10-14)
- 55-source catalog, 22 fetchable, 18 sources OK in the last full run
  (Bundesagentur-API, kimeta, stellenanzeigen.de, XING, Talent.com, Indeed,
  LinkedIn-guest, jobvector, whatjobs, jobrapido, and more).
- 3-layer dedupe: canonical-URL merge, REF-ID stripping + Jaccard near-dupe,
  rapidfuzz same-city flagging (9/9 unit tests green).
- Persistent job memory (data/jobs_history.db): first_seen/last_seen history,
  full-text search, new-today and gone-detection via
  `python -m pipeline history stats|new|gone|search`.
- 1,255 validated free proxies (8 list repos, tested against the real targets)
  power the kimeta source; refresh with `python -m pipeline.proxy_pool refresh`.
- Digest push via apprise (APPRISE_URL env) + healthchecks dead-man's switch;
  one-command daily run: `scripts/daily_jobpull.sh --with-proxies`.
- Every rejected row is audited in *_rejected.csv so nothing is silently lost.

BACKUP & ACCESS
- Full git-history bundle (v5): https://gofile.io/d/54w1I8ia
  Restore: `git clone <bundle>` — keyless download, no account needed.
- Browsable mirror: https://asha-fisi-jt.surge.sh
- v6 bundle (incl. job memory + digest layer) is created locally; the gofile
  upload endpoint is currently unreachable from this datacenter IP — the mail
  attachments above carry the latest data regardless.

QUICK START AFTER RESTORE
  python -m pip install -r requirements.txt   (venv: python -m pip ...)
  python -m pipeline fetch                    # full pull, all sources
  python -m pipeline history stats            # what changed since last run

Reply to this address if you want the agent to fetch mail or re-send anything.

— Asha's job-toolkit agent
"""

def main():
    for p in (CSV, JSN, PDF, OPS):
        if not os.path.exists(p):
            print("MISSING:", p); sys.exit(1)
    vars_ = {
        "TO": "skorry@atomicmail.io",
        "SUBJECT": "Asha FISI Job Toolkit - deliverables, latest 42 postings & backup links (2026-10-14)",
        "BODY": BODY,
    }
    cmd = [
        "npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
        "jmap_request",
        "--ops-file", OPS,
        "--attachment", CSV,
        "--attachment", JSN,
        "--attachment", PDF,
        "--vars", json.dumps(vars_),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=BASE)
    print("STDOUT:\n", r.stdout[-3000:])
    print("STDERR:\n", r.stderr[-1500:])
    print("RC:", r.returncode)

if __name__ == "__main__":
    main()
