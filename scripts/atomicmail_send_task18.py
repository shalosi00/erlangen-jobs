#!/usr/bin/env python3
"""Task 18 completion email: fix campaign + report v1.1 addendum (attached) + v7 mirrors."""
import json, subprocess, os

BASE = "/home/z/my-project"
OPS = f"{BASE}/scripts/atomicmail_task18_ops.json"
PDF = f"{BASE}/download/FISI_Toolkit_Report_v1.1_Addendum_20261014.pdf"

BODY = """Hi Asha,

"Fix everything" is done. Every finding from the full code review has been
implemented, tested, and verified on live production runs. The short version:

WHAT WAS FIXED (all 19 actionable findings from the 20-finding review)
- The train-commute filter was wrong in BOTH directions. It accepted towns
  that need a transfer since the Dec-2025 timetable change (Neumarkt, Feucht,
  Altdorf, Schwabach, Zirndorf...) and missed ~20 towns with real direct
  trains (Coburg 47 min!, Lichtenfels, Hassfurt, Bamberg suburbs...). It is
  now generated from the verified GTFS timetable analysis, and every row
  carries a "transit" column: 0-xfer (minutes) / limited / borderline /
  1-xfer / none. See section 3 of the attached addendum.
- Three filter false-positives fixed: "450 Mitarbeitern" no longer looks
  like a minijob, "...erwartet wir nicht" no longer rejects junior-friendly
  postings, Ausbildung boilerplate no longer silently drops whole sources.
  Each fix has a regression test pinned to the exact sentence that broke.
- The CLI survives a wiped dependency again (proved live), the daily script
  self-heals the venv from requirements.txt, overlapping runs are locked
  out, every run writes a persistent manifest, and the digest no longer
  calls a posting "expired" when its source was merely down today.
- Plus: post-merge audit gap, catalog/README truth-out (22 fetchable),
  proxy-pool staleness signal, richer job memory, optional parallel fetch,
  snippet column, BA key-gating early warning, dedupe stopword hygiene.

VERIFIED ON TODAY'S LIVE RUN
- 44 unique postings (was 42) with all fixes active; 801 rejected rows in
  the audit; 17 of 17 credential-free sources OK.
- The old 4 violation rows are now correctly labelled 1-xfer / none.
- Two previously-lost valid jobs RECOVERED: (Junior) IT Manager First Level
  Support at SIMBA DICKIE (Fuerth) and IT-Systemadministrator at HEGMANNS
  (Nuernberg) - both were false-positive victims.
- 45/45 unit tests green. Full evidence: section 7 of the addendum.

REPORT v1.1 ADDENDUM (attached, 8 pages)
Updates the 30-page baseline report with everything from Tasks 9-18:
new sources, the corrected train whitelist, the fix campaign, job memory
+ digest, repo adoptions, verified numbers, and the new runbook.

BACKUP v7 (current head, 147,362,954 bytes)
sha256 ccb7cbc6eb751f710e2e895f5e264737378b31c45dfecbbd4067484868cab9c1
1) litter.catbox.moe/zfqaa3.bundle (72 h) - head+tail hashes verified
2) filebin.net/ashajobtoolkit-v7/asha-jobtoolkit-20261014-v7.bundle (6 d)
   - head+mid ranged hashes verified; scripted download needs cookies:
   curl -c jar -L <url> then curl -b jar -L -H "Referer: ..." <url>
Note: x0.at has banned this datacenter's uploads (403), so the ~70-day
durable mirror remains the v6 bundle (V9xX.bundle) while this IP situation
lasts. Restore: git clone <bundle> then pip install -r requirements.txt.

MAIL CHANNEL
This inbox is asha.jobtoolkit3@atomicmail.ai (the previous two accounts'
credentials died with sandbox wipes; the key for #3 is escrowed in my
records). Replies still reach me.

- Asha's job-toolkit agent (Task 18, 2026-10-14)
"""

vars_ = {"TO": "skorry@atomicmail.io",
         "SUBJECT": "Asha toolkit: all 19 fixes shipped + Report v1.1 Addendum (attached) + v7 backup",
         "BODY": BODY}
cmd = ["npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
       "jmap_request", "--ops-file", OPS, "--attachment", PDF,
       "--vars", json.dumps(vars_)]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=BASE)
print("STDOUT:\n", r.stdout[-2500:])
print("STDERR:\n", r.stderr[-800:])
print("RC:", r.returncode)
