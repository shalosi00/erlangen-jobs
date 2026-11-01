#!/usr/bin/env python3
"""Rebuild ALL mail-channel escrow tiers from the live ~/.atomicmail credentials.

Run this after every (re-)registration or login so the key is never again
trapped in ~/.atomicmail, which sandbox wipes destroy.

Tier layout (order = durability):
  1. scripts/atomicmail_escrow.json.enc   git-committed AES-256 ciphertext
                                          -> survives every wipe, rides in bundles
  2. /home/z/my-project/state/atomicmail_escrow.json   gitignored working copy
  3. /home/z/.config/atomicmail/escrow.json            outside-repo copy

Usage:
  python3 scripts/make_escrow.py --address <addr>@atomicmail.ai [--note "..."]

Only run when ~/.atomicmail/credentials.json is LIVE (verify first with
scripts/atomicmail_recover.py --verify-only).
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from escrow_key import ESCROW_PASSPHRASE

HOME = os.path.expanduser("~")
CREDS = f"{HOME}/.atomicmail/credentials.json"
STATE = "/home/z/my-project/state/atomicmail_escrow.json"
CFG = f"{HOME}/.config/atomicmail/escrow.json"
ENC = "/home/z/my-project/scripts/atomicmail_escrow.json.enc"
CRED_KEYS = ["apiKey", "apiUrl", "authUrl", "downloadUrl", "uploadUrl", "inboxId", "scryptSalt"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True, help="full mailbox address, e.g. asha.jobtoolkit3@atomicmail.ai")
    ap.add_argument("--note", default="", help="provenance note (registered when, why re-escrowed)")
    a = ap.parse_args()

    cred = json.load(open(CREDS))
    missing = [k for k in CRED_KEYS if k not in cred]
    if missing:
        print(f"WARN: credentials.json missing keys {missing} — escrow will still be written")

    esc = {
        "escrow_version": 1,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "address": a.address,
        "provider": "atomicmail (JMAP; `atomicmail register --api-key <key>` re-logs in)",
        "rate_caps": "PoW signup caps: 20 msgs/h, 100 msgs/d",
        "note": a.note,
        "credentials": {k: cred.get(k) for k in CRED_KEYS},
    }

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    for path in (STATE, CFG):
        with open(path, "w") as f:
            json.dump(esc, f, indent=1)
        os.chmod(path, 0o600)
        print(f"tier written : {path}")

    r = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt",
         "-in", STATE, "-out", ENC, "-pass", f"pass:{ESCROW_PASSPHRASE}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit(f"openssl encrypt failed: {r.stderr}")
    print(f"tier written : {ENC} (git-committed ciphertext)")

    # roundtrip check
    chk = subprocess.run(
        ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
         "-in", ENC, "-pass", f"pass:{ESCROW_PASSPHRASE}"],
        capture_output=True, text=True,
    )
    if chk.returncode != 0 or json.loads(chk.stdout) != esc:
        sys.exit("ROUNDTRIP FAILED — ciphertext does not decrypt to identical escrow")
    print("roundtrip    : OK (decrypts to identical escrow)")
    print(f"escrowed key : {esc['credentials'].get('apiKey', '?')[:8]}... for {esc['address']}")


if __name__ == "__main__":
    main()
