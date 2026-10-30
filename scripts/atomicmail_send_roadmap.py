#!/usr/bin/env python3
"""Send the Certificate Roadmap deliverables via Atomic Mail JMAP.
Reuses the proven daily-send mechanism (ops template + --attachment).
Run scripts/atomicmail_recover.py FIRST (standing rule before any email work).
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = "/home/z/my-project"
OPS = f"{BASE}/scripts/atomicmail_daily_ops.json"
PDF = f"{BASE}/download/Certificate_Roadmap_Erlangen_Corpus_2026-10-30.pdf"
DOCX = f"{BASE}/download/Certificate_Roadmap_Erlangen_Corpus_2026-10-30.docx"

BODY = """Hi Asha,

certificate roadmap completed - which certificates to pursue, in which
order, and how to fund them (Bildungsgutschein).

EVIDENCE BASE
3,902 unique postings scanned (3,825 regional baseline + 77 active FISI
postings of 2026-10-30): 26 explicit certificate patterns (AZ-900 ... CCNA,
ITIL, VCP, ...) + 18 skill stacks, every hit stored as verbatim evidence.

KEY FINDINGS
- Certificates almost never GATE roles here (3 of 77 active postings name
  concrete certs) - they DIFFERENTIATE entry applicants.
- Skill demand in the 77 active postings: network 33.8%, security 20.8%,
  IT service management 18.2%, virtualization 15.6%, Linux 14.3%,
  cloud 13.0% (Azure 3.9%), Microsoft 365/endpoint 6.5%.
- Explicit cert asks found: iT4Network GmbH ("Ideale Kenntnisse:
  VMWare Zertifizierung (VCP), Microsoft Zertifizierung (MCP, MCSA,
  MCSE, ...)"), ITIL at FERCHAU + Brunel; ncsolution GmbH funds certs.

THE ANSWER (pursue in this order)
1. AZ-900 Azure Fundamentals (EUR 53) - voucher entry stage, now
2. AZ-104 Azure Administrator Associate - the core voucher module
   (cloud/MS demand union 23.4% = 18/77 active postings)
3. CompTIA Network+ (USD 399 list) or MD-102 - largest observed stacks
4. CompTIA Security+ (USD 439 list; V8 ~17 Nov 2026) - 20.8% stack
5. After placement, employer-funded: ITIL 4 Foundation, AZ-800,
   LPIC-1/VCP only if the employer's stack demands it

ATTACHED
- Certificate_Roadmap_Erlangen_Corpus_2026-10-30.pdf (8 pages, evidence
  tables + verbatim quotes + fees + phased funding plan)
- Certificate_Roadmap_Erlangen_Corpus_2026-10-30.docx (editable version)

This complements the Azure & Cloud Demand Justification dossier of this
morning - the voucher application keeps AZ-900 + AZ-104 as its training
goal; the roadmap documents the sequenced path around it.

- Asha's job-toolkit agent (2026-10-30)
"""

attachments = [p for p in (PDF, DOCX) if Path(p).exists()]
if len(attachments) != 2:
    print("MISSING deliverables:", PDF, DOCX)
    sys.exit(2)

recipients = ["skorry@atomicmail.io", "feebee231@outlook.com"]
cmd_base = ["npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
            "jmap_request", "--ops-file", OPS]
for a in attachments:
    cmd_base += ["--attachment", a]

rc_all = 0
results = {}
for to in recipients:
    vars_ = {"TO": to,
             "SUBJECT": "Certificate roadmap: AZ-900/AZ-104 first, then Network+/MD-102 "
                        "(evidence from 3,902 postings)",
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
json.dump(results, open(f"{BASE}/scripts/atomicmail_roadmap_result.json", "w"), indent=1)
sys.exit(rc_all)
