#!/usr/bin/env python3
"""Task 24 daily email: morning briefing + enriched contact sheet.
Usage: python3 scripts/atomicmail_send_daily.py <summary.md> <enriched.csv> <gold.csv> [to1,to2]
Default recipients: skorry@atomicmail.io, feebee231@outlook.com (Task 24 add-on)
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = "/home/z/my-project"
OPS = f"{BASE}/scripts/atomicmail_daily_ops.json"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

summary_md = sys.argv[1] if len(sys.argv) > 1 else ""
enrich_csv = sys.argv[2] if len(sys.argv) > 2 else ""
gold_csv = sys.argv[3] if len(sys.argv) > 3 else ""

# parse headline numbers from the summary for the mail body
stats = {"direct": "?", "mediator": "?", "phone": "?", "email": "?",
         "orig": "?", "new": "?"}
try:
    for line in Path(summary_md).read_text(encoding="utf-8").splitlines():
        if line.startswith("- Direkt:"):
            parts = line.replace("*", "").replace("|", "").split()
            stats["direct"], stats["mediator"] = parts[1].strip(), parts[4].strip()
        if "Telefon gefunden" in line:
            import re
            m = re.findall(r"\*\*(\d+)\*\*", line)
            if len(m) >= 4:
                stats["phone"], stats["email"] = m[0], m[1]
                stats["orig"], stats["web"] = m[2], m[3]
        if line.startswith("_Keine neuen Jobs heute"):
            stats["new"] = "0"
except Exception:
    pass
if stats["new"] == "?":
    import re
    try:
        for line in Path(summary_md).read_text(encoding="utf-8").splitlines():
            m = re.match(r"_(\d+) Postings im Bestand, (\d+) neu heute", line)
            if m:
                stats["new"] = m.group(2)
    except Exception:
        pass

BODY = f"""Hi Asha,

daily job task completed (auto-scheduled, runs every day at 07:00).

WHAT THIS RUN DID
1. Fetched new jobs from all portals (BA-API, kimeta, Talent, Get-in-IT,
   Indeed, LinkedIn, EURES, InFranken — 14-day window).
2. Visited every posting and enriched it:
   WHERE  — source portal documented per job
   WHEN   — posting date with evidence (BA-API / JSON-LD / page date);
            if a page carries no date, the exact time-period filter that
            source used is documented instead (e.g. BA veroeffentlichtseit=14)
   WHO    — original employer identified, mediators/Zeitarbeit flagged out
   CONTACT— recruiter phone, recruiter email, employer website,
            original posting URL (not the portal wrapper)

NUMBERS TODAY
- new jobs today: {stats['new']}
- direct employers: {stats['direct']} | mediators flagged: {stats['mediator']}
- contacts found: phone {stats['phone']} / email {stats['email']} /
  original URLs {stats['orig']}

ATTACHED
- daily_summary_{TODAY}.md  — the full briefing (WHERE/WHEN tables, gold list)
- jobs_enriched CSV         — every job: date + evidence + employer + contacts
- direct_employers CSV      — the gold sheet: direct employers with contacts

Apply strategy: work the gold sheet top-down — direct employer, phone and
email in hand, no recruiter detour.

- Asha's job-toolkit agent (daily task, {TODAY})
"""

attachments = [p for p in (summary_md, enrich_csv, gold_csv) if p and Path(p).exists()]
recipients = (sys.argv[4].split(",") if len(sys.argv) > 4 else
              ["skorry@atomicmail.io", "feebee231@outlook.com"])

cmd_base = ["npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
            "jmap_request", "--ops-file", OPS]
for a in attachments:
    cmd_base += ["--attachment", a]

rc_all = 0
results = {}
for to in recipients:
    to = to.strip()
    vars_ = {"TO": to,
             "SUBJECT": f"Daily job briefing {TODAY}: {stats['new']} new, "
                        f"{stats['direct']} direct employers w/ contacts",
             "BODY": BODY}
    r = subprocess.run(cmd_base + ["--vars", json.dumps(vars_)],
                       capture_output=True, text=True, timeout=300, cwd=BASE)
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "notCreated" in out and ": null" in out
    results[to] = "sent" if ok else f"FAILED rc={r.returncode}"
    print(f"[{to}] {results[to]}")
    print(out[-400:])
    if not ok:
        rc_all = 1
json.dump(results, open(f"{BASE}/scripts/atomicmail_daily_result.json", "w"),
          indent=1)
sys.exit(rc_all)
