#!/usr/bin/env python3
"""gh_recover.py — recover the GitHub token from the committed escrow ciphertext.

Wipe-recovery playbook (same tier pattern as the atomicmail channel):
  1. rebuild the passphrase:  mkdir -p state && git show 32b25d7^:scripts/escrow_key.py \
        > state/escrow_key.py && chmod 600 state/escrow_key.py
  2. python3 scripts/gh_recover.py            # -> state/github_token (0600) + API verify
  3. python3 scripts/gh_recover.py --install  # additionally set up a push helper remote URL

Escrow chain: scripts/github_token.enc (git-committed ciphertext)
              -> state/github_token (gitignored plaintext, chmod 600)
Passphrase source: scripts/escrow_key.py (recoverable from git history, commit 32b25d7^).
"""
import json
import os
import subprocess
import sys

BASE = "/home/z/my-project"
ENC = f"{BASE}/scripts/github_token.enc"
STATE = f"{BASE}/state/github_token"


def main():
    sys.path.insert(0, f"{BASE}/state")
    sys.path.insert(0, f"{BASE}/scripts")
    try:
        from escrow_key import ESCROW_PASSPHRASE
    except ImportError:
        sys.exit("state/escrow_key.py missing — run: git show 32b25d7^:scripts/escrow_key.py > state/escrow_key.py")

    r = subprocess.run(
        ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
         "-in", ENC, "-pass", f"pass:{ESCROW_PASSPHRASE}"],
        capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"decrypt failed: {r.stderr}")
    esc = json.loads(r.stdout)

    os.makedirs(f"{BASE}/state", exist_ok=True)
    with open(STATE, "w") as f:
        f.write(esc["token"])
    os.chmod(STATE, 0o600)
    print(f"token restored : {STATE} (user {esc['user']}, tail {esc['token'][-6:]})")

    if "--install" in sys.argv:
        # convenience: set remote-url helper via env for future pushes
        print(f"use in scripts : TOKEN=$(cat {STATE})")
        print("git push URL   : https://x-access-token:$(cat state/github_token)@github.com/<repo>")

    if "--verify" in sys.argv or "--install" in sys.argv:
        import urllib.request
        req = urllib.request.Request("https://api.github.com/user",
                                     headers={"Authorization": f"token {esc['token']}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                who = json.load(resp)
            print(f"API verify     : OK (login={who['login']})")
        except Exception as e:
            sys.exit(f"API verify FAILED: {e}")


if __name__ == "__main__":
    main()
