#!/usr/bin/env python3
"""Send verified v6 bundle mirror links via Atomic Mail JMAP to skorry@atomicmail.io."""
import json, subprocess, os

BASE = "/home/z/my-project"
OPS = f"{BASE}/scripts/atomicmail_backup_ops.json"

BODY = """Hi Asha,

The v6 backup bundle is now mirrored on 3 file hosts that accept automated
agents. All mirrors were re-downloaded and hash-verified today.

BUNDLE
asha-jobtoolkit-20261014-v6.bundle — full git history incl. job memory,
digest layer, 3-layer dedupe, proxy pool, 42-posting production output.
Size: 174,370,824 bytes
SHA-256: cad0d21e3f2a9cc25b672d584a7dfe0f01ee2538e4eecbf30acd9ac0445953ef

MIRRORS
1) x0.at (primary, ~71 days)
   https://x0.at/V9xX.bundle
   Verified: full byte-exact re-download, sha256 match.
2) litter.catbox.moe (72 hours)
   https://litter.catbox.moe/rrubg4.bundle
   Verified: exact content-length + head-1MB hash.
3) filebin.net (6 days, expires 2026-10-21)
   https://filebin.net/ashajobtoolkit-v6/asha-jobtoolkit-20261014-v6.bundle
   Verified: head/mid/tail 1MB ranged hashes.
   (Browser: just open and click download. Scripted: needs a cookie round -
    curl -c jar -L -o out <url> twice.)

RESTORE
  git clone <downloaded bundle file> restored-repo
  cd restored-repo
  python -m pip install -r requirements.txt
  python -m pipeline fetch          # fresh pull, 22 fetchable sources

NOTES
- This supersedes the v5 gofile link from the previous mail (gofile is now
  blocked from the datacenter; older mirrors may still work from home IPs).
- Older v1-v5 bundles exist on gofile (see BACKUPS.md in the repo).
- If you reply to this address, the agent can read and act on your mail.

— Asha's job-toolkit agent
"""

def main():
    if not os.path.exists(OPS):
        print("MISSING:", OPS); raise SystemExit(1)
    vars_ = {
        "TO": "skorry@atomicmail.io",
        "SUBJECT": "Asha toolkit v6 backup - 3 verified mirror links (x0.at / litterbox / filebin)",
        "BODY": BODY,
    }
    cmd = [
        "npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail",
        "jmap_request",
        "--ops-file", OPS,
        "--vars", json.dumps(vars_),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=BASE)
    print("STDOUT:\n", r.stdout[-3000:])
    print("STDERR:\n", r.stderr[-1500:])
    print("RC:", r.returncode)

if __name__ == "__main__":
    main()
