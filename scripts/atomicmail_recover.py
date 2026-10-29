#!/usr/bin/env python3
"""Mail-channel recovery — RUN THIS FIRST in every new session, before any email work.

Restores ~/.atomicmail from the escrow tiers (order = durability):
  1. git-committed ciphertext  scripts/atomicmail_escrow.json.enc  (survives every wipe)
  2. /home/z/my-project/state/atomicmail_escrow.json               (gitignored)
  3. /home/z/.config/atomicmail/escrow.json                        (outside repo)

then LIVE-VERIFIES the escrowed apiKey through the real auth chain
(`atomicmail register --api-key ...` = challenge -> PoW -> session ->
capability) and refreshes the session/capability JWTs. If the server rotated
the apiKey during login, the escrow is refreshed automatically.

Exit codes: 0 = channel OK · 2 = escrow restore failed verification · 3 = no escrow found
Flags:      --verify-only (sandboxed temp dir, no live writes) · --quiet

DO NOT register a new mailbox unless verification fails with auth rejection.
See CHANNEL.md for the last-resort flow.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from escrow_key import ESCROW_PASSPHRASE

HOME = os.path.expanduser("~")
BASE = "/home/z/my-project"
AM_DIR = f"{HOME}/.atomicmail"
CREDS = f"{AM_DIR}/credentials.json"
STATE = f"{BASE}/state/atomicmail_escrow.json"
CFG = f"{HOME}/.config/atomicmail/escrow.json"
ENC = f"{BASE}/scripts/atomicmail_escrow.json.enc"
JWT_FILES = ["session.jwt", "capability.jwt"]
NPX = ["npx", "-y", "--package=@atomicmail/agent-skill", "atomicmail"]
# Project-documented operator choice (worklog Task 18-b): --watch on-demand.
# The CLI refuses register without an explicit watch value by design.
WATCH_ARGS = ["--watch", "on-demand"]


def decrypt_enc() -> dict | None:
    if not os.path.exists(ENC):
        return None
    r = subprocess.run(
        ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
         "-in", ENC, "-pass", f"pass:{ESCROW_PASSPHRASE}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"  tier 1 (git .enc): decrypt FAILED ({r.stderr.strip()[:120]})")
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        print("  tier 1 (git .enc): decrypted garbage")
        return None


def load_json(path) -> dict | None:
    try:
        return json.load(open(path))
    except Exception:
        return None


def cli_login(api_key: str, creds_dir: str, timeout: int = 300) -> tuple[bool, str]:
    """Run the real auth chain into creds_dir. Returns (ok, tail-of-output)."""
    os.makedirs(creds_dir, mode=0o700, exist_ok=True)
    with open(f"{creds_dir}/credentials.json", "w") as f:
        json.dump({"apiKey": api_key}, f)
    os.chmod(f"{creds_dir}/credentials.json", 0o600)
    r = subprocess.run(
        NPX + ["register", "--api-key", api_key, "--credentials-dir", creds_dir] + WATCH_ARGS,
        capture_output=True, text=True, timeout=timeout, cwd=BASE,
    )
    tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    return r.returncode == 0, "\n".join(tail[-6:])


def backup_live_creds() -> str | None:
    if os.path.exists(CREDS):
        bak = CREDS + ".bak"
        shutil.copy2(CREDS, bak)
        return bak
    return None


def restore_live_creds(bak: str | None) -> None:
    if bak and os.path.exists(bak):
        shutil.copy2(bak, CREDS)
        os.chmod(CREDS, 0o600)


def verify_escrow_key(esc: dict) -> tuple[bool, str, str]:
    """Verify escrowed key in a sandboxed temp dir. -> (ok, detail, new_api_key_or_empty)"""
    key = (esc.get("credentials") or {}).get("apiKey", "")
    if not key:
        return False, "escrow has no apiKey", ""
    with tempfile.TemporaryDirectory(prefix="amverify-", dir=f"{BASE}/state") as tmp:
        ok, out = cli_login(key, tmp)
        new_key = ""
        if ok:
            # promote the CLI's authoritative output (full credentials + fresh JWTs)
            for f in ["credentials.json"] + JWT_FILES:
                src = f"{tmp}/{f}"
                if os.path.exists(src):
                    shutil.copy2(src, f"{BASE}/state/.promoted.{f}")
            fresh = load_json(f"{BASE}/state/.promoted.credentials.json") or {}
            new_key = fresh.get("apiKey", "")
        return ok, (out if not ok else "register --api-key: RC 0 (PoW session + capability OK)"), new_key


def promote_jwts() -> None:
    for f in JWT_FILES:
        src, dst = f"{BASE}/state/.promoted.{f}", f"{AM_DIR}/{f}"
        if os.path.exists(src):
            shutil.copy2(src, dst)
            os.chmod(dst, 0o600)
            print(f"  jwt refresh : {f}")


def write_am_dir(cred: dict) -> None:
    os.makedirs(AM_DIR, mode=0o700, exist_ok=True)
    promoted = f"{BASE}/state/.promoted.credentials.json"
    if os.path.exists(promoted):
        shutil.copy2(promoted, CREDS)
        os.chmod(CREDS, 0o600)
        print(f"  restored    : {CREDS} (0600, from verified CLI login)")
        return
    os.makedirs(AM_DIR, mode=0o700, exist_ok=True)
    with open(CREDS, "w") as f:
        json.dump(cred, f, indent=1)
    os.chmod(CREDS, 0o600)
    print(f"  restored    : {CREDS} (0600)")


def write_weak_tiers(esc: dict) -> None:
    for path in (STATE, CFG):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(esc, f, indent=1)
            os.chmod(path, 0o600)
            print(f"  self-healed : {path}")
        except Exception as e:
            print(f"  tier skip   : {path} ({e})")


def reescrow(esc: dict, note: str) -> None:
    write_weak_tiers(esc)
    r = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt",
         "-in", STATE, "-out", ENC, "-pass", f"pass:{ESCROW_PASSPHRASE}"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"  re-escrowed : {ENC} ({note}) — COMMIT it: git add {ENC.replace(BASE + '/', '')} && git commit")


def last_resort() -> str:
    return (
        "\nLAST-RESORT re-registration (only after both escrow and live keys fail auth):\n"
        "  1. python3 scripts/mailtm.py            # fresh verification inbox\n"
        "  2. npx -y --package=@atomicmail/agent-skill atomicmail register --username <newname> --watch on-demand\n"
        "     (PoW signup; caps 20 msgs/h, 100 msgs/d; watch value = project-documented choice)\n"
        "  3. python3 scripts/make_escrow.py --address <new>@atomicmail.ai --note 're-registered <date>: <reason>'\n"
        "  4. git add scripts/atomicmail_escrow.json.enc scripts/escrow_key.py && git commit\n"
        "  5. EMAIL skorry@atomicmail.io the new address (old replies bounce otherwise!)\n"
        "  6. Update CHANNEL.md channel block + worklog."
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true", help="sandboxed check, no live writes")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if not a.quiet:
        print("== atomicmail channel recovery ==")

    os.makedirs(f"{BASE}/state", exist_ok=True)

    # --- gather escrow candidates, strongest first -------------------------
    esc, tier = None, ""
    e = decrypt_enc()
    if e:
        print("  tier 1 (git .enc): OK")
        esc, tier = e, "1"
    if esc is None:
        e = load_json(STATE)
        if e:
            print("  tier 2 (state/): OK  (tier 1 missing/corrupt!)")
            esc, tier = e, "2"
    if esc is None:
        e = load_json(CFG)
        if e:
            print("  tier 3 (~/.config): OK  (tiers 1+2 missing!)")
            esc, tier = e, "3"
    if esc is None:
        print("  NO ESCROW FOUND in any tier.")
        print(last_resort())
        sys.exit(3)

    esc_key = esc["credentials"]["apiKey"]
    live = load_json(CREDS) or {}
    live_key = live.get("apiKey", "")
    print(f"  escrow      : {esc.get('address')} (created {esc.get('created_utc')}, tier {tier})")

    # --- verification paths -------------------------------------------------
    if a.verify_only:
        ok, detail, new_key = verify_escrow_key(esc)
        print(f"  live check  : {detail}")
        if new_key:
            print("  NOTE        : server returned a ROTATED apiKey — run full recovery to adopt it")
        sys.exit(0 if ok else 2)

    if live_key and live_key == esc_key:
        # canonical already in place: verify + refresh JWTs in the live dir
        bak = backup_live_creds()
        ok, out = cli_login(esc_key, AM_DIR)
        print(f"  live check  : {'OK (JWTs refreshed)' if ok else 'FAILED'}")
        if not ok:
            restore_live_creds(bak)
            print(out)
            print("\nEscrowed key rejected — see last-resort below.")
            print(last_resort())
            sys.exit(2)
        # rotation note (empirically verified 2026-10-14): the server may hand a
        # NEW apiKey per login, but OLD keys stay valid — escrow never strands.
        fresh = load_json(CREDS) or {}
        if fresh.get("apiKey") and fresh["apiKey"] != esc_key:
            esc = {**esc, "credentials": {**esc["credentials"], "apiKey": fresh["apiKey"]}}
            reescrow(esc, "apiKey rotated by server during in-place login")
    else:
        # escrow key vs whatever lives in ~/.atomicmail — verify escrow canonically
        ok, detail, new_key = verify_escrow_key(esc)
        print(f"  live check  : {detail}")
        if ok:
            if live_key and live_key != esc_key:
                print("  note        : ~/.atomicmail held a DIFFERENT key; escrow key verified — escrow stays canonical")
            write_am_dir({**esc["credentials"], **({"apiKey": new_key} if new_key else {})})
            promote_jwts()
            if new_key and new_key != esc_key:
                esc = {**esc, "credentials": {**esc["credentials"], "apiKey": new_key}}
                reescrow(esc, "apiKey rotated by server during recovery login")
        else:
            # maybe the live dir holds a NEWER rotated key that escrow predates
            if live_key:
                print("  fallback    : escrow key rejected — trying the key already in ~/.atomicmail")
                bak = backup_live_creds()
                ok2, out2 = cli_login(live_key, AM_DIR)
                if not ok2:
                    restore_live_creds(bak)
                if ok2:
                    print("  live check  : OK — live key is newer than escrow; re-escrowing it")
                    fresh = load_json(CREDS) or live
                    esc = {**esc, "credentials": {**esc["credentials"], "apiKey": fresh.get("apiKey", live_key)}}
                    reescrow(esc, "live key newer than escrow")
                else:
                    print(out2)
                    print(last_resort())
                    sys.exit(2)
            else:
                print(last_resort())
                sys.exit(2)

    # --- self-heal weaker tiers --------------------------------------------
    if not os.path.exists(STATE) or not os.path.exists(CFG):
        write_weak_tiers(esc)

    print(f"\nCHANNEL READY: {esc.get('address')}")
    print("Send pattern: see scripts/atomicmail_send_task18.py (ops json + npx atomicmail jmap_request).")


if __name__ == "__main__":
    main()
