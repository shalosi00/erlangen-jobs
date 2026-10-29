#!/usr/bin/env python3
"""Email the AI-agent handover document (with credentials escrow) to skorry@atomicmail.io."""
import json, subprocess, os

BASE = "/home/z/my-project"
DOC = f"{BASE}/download/AI_AGENT_HANDOVER_20261014.md"
OPS = f"{BASE}/scripts/atomicmail_handover_ops.json"

BODY = """Hi Asha,

Attached: AI_AGENT_HANDOVER_20261014.md — the complete project handover so any
new AI agent can take over your job-toolkit with zero context loss.

WHAT'S INSIDE (10 sections)
- Mission + your standing instructions (autonomous, no questions, green-zone crawling)
- Current status: 42 unique FISI postings, 22 fetchable sources, job memory,
  dedupe, proxy pool, daily automation — all operational
- Repo map + operating runbook (copy-paste commands)
- ALL CREDENTIALS (escrow): mail.tm inbox + password, Atomic Mail agent account
  with API key, surge.sh token, gofile guest tokens, v6 bundle hashes + mirrors
- Network block map (what is blocked and how it was proven) + working recipes
- Environment survival guide (sandbox wipes, auto-commits, venv fragility,
  background-process killing) and the backlog with revisit triggers

TWO THINGS THAT CHANGED TODAY
1. The sandbox wiped the old email credentials this morning. This mail comes from
   the NEW agent inbox: asha.jobtoolkit2@atomicmail.ai
   (the old asha.jobtoolkit@ address is orphaned — replies there go unread).
2. The handover file is the credential escrow: keep this email, do not forward
   it; the file itself is gitignored and must never be committed or uploaded.

— Asha's job-toolkit agent
"""

def main():
    for p in (DOC, OPS):
        if not os.path.exists(p):
            print("MISSING:", p); raise SystemExit(1)
    vars_ = {
        "TO": "skorry@atomicmail.io",
        "SUBJECT": "AI agent handover - full project status + credential escrow (asha job-toolkit, 2026-10-14)",
        "BODY": BODY,
    }
    cmd = [
        "npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
        "jmap_request",
        "--ops-file", OPS,
        "--attachment", DOC,
        "--vars", json.dumps(vars_),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=BASE)
    print("STDOUT:\n", r.stdout[-2500:])
    print("STDERR:\n", r.stderr[-1200:])
    print("RC:", r.returncode)

if __name__ == "__main__":
    main()
