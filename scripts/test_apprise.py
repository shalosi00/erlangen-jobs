"""Smoke test 1: apprise — URL validation for 3 channels + REAL end-to-end push
via public ntfy.sh (no signup, no server) with delivery proof."""
import time, json, urllib.request, uuid

import apprise

# --- 1) URL validation for the 3 channel types we'd actually use
tests = {
    "ntfy (public, zero signup)": "ntfys://ntfy.sh/asha-jobtoolkit-e2e-<rand>",
    "telegram (bot token)":       "tgram://123456:AA FakeTokenTooShort/chan",
    "smtp (gmail)":               "mailtos://user:pass@gmail.com/?to=x@y.z",
}
print("== URL validation ==")
for name, url in tests.items():
    ap = apprise.Apprise()
    ok = ap.add(url.replace("<rand>", "tmp"))
    print(f"  {name:<28} add() -> {ok}")

# --- 2) REAL push to public ntfy.sh, then read it back = delivery proof
topic = f"asha-e2e-{uuid.uuid4().hex[:8]}"
print(f"\n== end-to-end: apprise -> ntfys://ntfy.sh/{topic} ==")
ap = apprise.Apprise()
assert ap.add(f"ntfys://ntfy.sh/{topic}"), "add failed"
ok = ap.notify(title="Asha jobtoolkit digest", body="smoke test: 3 new FISI postings today")
print(f"  notify() -> {ok}")

time.sleep(3)
with urllib.request.urlopen(f"https://ntfy.sh/{topic}/json?poll=1", timeout=20) as r:
    msgs = [json.loads(l) for l in r.read().decode().splitlines() if l.strip()]
received = [m for m in msgs if m.get("event") == "message"]
print(f"  delivered messages read back: {len(received)}")
for m in received:
    print(f"  proof: title={m.get('title')!r} body={m.get('message')!r}")
print("E2E", "PASS" if (ok and received) else "FAIL")
