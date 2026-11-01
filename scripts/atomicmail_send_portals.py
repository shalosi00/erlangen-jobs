#!/usr/bin/env python3
"""Send the German job-portal catalog digest via Atomic Mail JMAP.
Reuses the proven send mechanism (ops template + --attachment).
Run scripts/atomicmail_recover.py FIRST (standing rule before any email work).
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = "/home/z/my-project"
OPS = f"{BASE}/scripts/atomicmail_daily_ops.json"
XLSX = f"{BASE}/download/jobportals_deutschland_2026-10-31.xlsx"
CSV = f"{BASE}/download/jobportals_scan_2026-10-31.csv"

BODY = """Hi Asha,

job-portal discovery for Germany completed - every portal we could find,
live-probed, classified, and ranked for the daily pipeline.

NUMBERS
- 156 German job portals identified and HTTP-probed (direct, retry pass,
  then a 49-proxy pool for WAF sites)
- 89 verified reachable: 78 direct + 10 via proxy + 1 JS-only
- 39 hard-blocked (Cloudflare/WAF), 67 dead/unreachable/legacy
- Categories: generalists, public/authority, tech/IT, junior/apprentice,
  regional (Franconia focus), aggregators, staffing, niches, expat,
  remote, and ATS direct-feeds

HIGHLIGHTS (new, verified-live, not yet in the daily pipeline)
- Junior/entry: Absolventa, ausbildung.de, azubi.de, IHK-Lehrstellen,
  Lehrstellen-Radar, Praktikum.info, Berufsstart, Ausbildungspark
- IT niche: ITsax.de, ITmitte.de, Joberty, Get in IT/Engineering,
  GermanTechJobs (redirects to DevITjobs), Instaffo
- Regional: InFranken (already core), Nordbayern->vnp.de/karriere,
  RegioJobs-NI, Karriere-Hamburg/Bremen, Munich Startup Jobs
- Public sector: Interamt (federal), Berlin.de Karriereportal,
  Stellenwerk (university boards incl. FAU Erlangen-Nuernberg),
  academics.de, oeffentlicher-dienst.info
- Classic boards, directly scrapable: Jobware, ZEIT Jobs, SZ Jobs,
  FAZJOB.NET (-> stellenmarkt.faz.net), Stellenmarkt.de, Jobworld
- Staffing volume for FISI: Hays, Adecco (-> jobs.de.adecco.com),
  Manpower, DIS AG, Hofmann, Amadeus Fire, persona
- Aggregators live: Talent.com, Jobijoba, WhatJobs, Jobsora, JobisJob
- Free official APIs instead of scraping: Jooble, Adzuna, Careerjet
  (registration keys) - recommended long-term sources
- ATS direct-feeds (Greenhouse/Lever/Ashby/Personio/SmartRecruiters):
  employer-direct postings with zero mediators - exactly the Task-24 goal

BLOCKED (known good, need fresh proxy pool or API key)
Indeed, LinkedIn, StepStone(->proxy OK), kimeta, meinestadt,
stellenanzeigen.de, Jooble, Careerjet, Adzuna, Jobrapido, Jobleads,
Yourfirm, jobvector. kimeta/stellenanzeigen were harvested via proxies
in earlier sessions; the pool file is 4 days old and should be refreshed.

ATTACHED
- jobportals_deutschland_2026-10-31.xlsx (+ flat CSV of the full scan)
  Sheets: Uebersicht (stats) | Master (156) | Live & erntbar (89) |
  Blockiert & legacy (67) | Integrationsplan (18-step wiring plan) |
  Review (self-check, all PASS)

Next step proposal: wire the top-12 wiring-plan sources into the daily
pull and run the junior-filter sweep over them.

- Asha's job-toolkit agent (2026-10-31)
"""

if not (Path(XLSX).exists() and Path(CSV).exists()):
    print("MISSING deliverable:", XLSX, CSV)
    sys.exit(2)

recipients = ["skorry@atomicmail.io", "feebee231@outlook.com"]
cmd_base = ["npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
            "jmap_request", "--ops-file", OPS, "--attachment", XLSX, "--attachment", CSV]

rc_all = 0
results = {}
for to in recipients:
    vars_ = {"TO": to,
             "SUBJECT": "Jobportal-Scan Deutschland: 156 Portale geprueft, 89 live erreichbar (XLSX)",
             "BODY": BODY}
    r = subprocess.run(cmd_base + ["--vars", json.dumps(vars_)],
                       capture_output=True, text=True, timeout=300, cwd=BASE)
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "notCreated" in out and ": null" in out
    results[to] = "sent" if ok else f"FAILED rc={r.returncode}"
    print(f"[{to}] {results[to]}")
    print(out[-300:])
    if not ok:
        rc_all = 1
json.dump(results, open(f"{BASE}/scripts/atomicmail_portal_result.json", "w"), indent=1)
sys.exit(rc_all)
