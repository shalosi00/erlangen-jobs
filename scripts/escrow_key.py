"""Escrow passphrase loader — PUBLIC-SAFE STUB (Task 24d secret hygiene).

The real passphrase lives in `state/escrow_key.py` (0600, gitignored).
Layout of the real file:  ESCROW_PASSPHRASE = "..."
If missing after a wipe: ask the user (tier-3 escrow). Never commit the
real passphrase — this repo is public and the escrow ciphertext (tier-1)
is committed alongside it by design.
"""
import importlib.util
from pathlib import Path

_STATE_KEY = Path(__file__).resolve().parent.parent / "state" / "escrow_key.py"

def _load():
    if _STATE_KEY.exists():
        spec = importlib.util.spec_from_file_location("escrow_key_real", _STATE_KEY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.ESCROW_PASSPHRASE
    raise SystemExit(
        "escrow passphrase missing: expected state/escrow_key.py "
        "(tier-3 — ask the user). NEVER hardcode it here: repo is public.")

ESCROW_PASSPHRASE = _load()
