#!/usr/bin/env python3
"""Create verified surge.sh account: fresh mail.tm mailbox (creds saved) ->
create surge account -> deploy site -> read verification mail -> click link."""
import json, os, re, secrets, string, subprocess, time
import requests

rnd = lambda n: "".join(secrets.choice(string.ascii_lowercase) for _ in range(n))
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/127.0.0.0 Safari/537.36",
     "Accept-Language": "de-DE,de;q=0.9"}

# ---- 1. fresh mailbox with SAVED password ----
dom = requests.get("https://api.mail.tm/domains", headers=H, timeout=20).json()["hydra:member"][0]["domain"]
email, pwd = f"ashajt{rnd(7)}@{dom}", "Vv" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))
mtok = None
for i in range(6):
    r = requests.post("https://api.mail.tm/accounts", headers={**H, "Content-Type": "application/json"},
                      data=json.dumps({"address": email, "password": pwd}), timeout=20)
    if r.status_code in (200, 201):
        break
    print(f"    account create attempt {i+1}: {r.status_code} {r.text[:120]}", flush=True)
    email, pwd = f"ashajt{rnd(7)}@{dom}", "Vv" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))
    time.sleep(8)
assert r.status_code in (200, 201), f"mail.tm account failed: {r.text[:200]}"
for i in range(6):
    rt = requests.post("https://api.mail.tm/token", headers={**H, "Content-Type": "application/json"},
                       data=json.dumps({"address": email, "password": pwd}), timeout=20)
    if rt.status_code == 200 and "token" in rt.json():
        mtok = rt.json()["token"]
        break
    print(f"    token attempt {i+1}: {rt.status_code} {rt.text[:120]}", flush=True)
    time.sleep(12)
assert mtok, "mail.tm token failed"
print(f"[+] mailbox: {email}", flush=True)

# ---- 2. surge account + token via pseudo-tty ----
res = subprocess.run("script -qec 'npx -y surge token' /dev/null", shell=True,
                     input=f"{email}\n{pwd}\n", text=True, capture_output=True, timeout=150)
out = (res.stdout or "") + (res.stderr or "")
m = re.search(r"\b([0-9a-f]{32,40})\b\s*$", out.strip())
if not m:
    print("[!] no token; raw:", out[-600:], flush=True)
    raise SystemExit(2)
token = m.group(1)
print(f"[+] surge token: {token}", flush=True)

# ---- 3. deploy (new domain; remove stale CNAME) ----
if os.path.exists("/home/z/my-project/site/CNAME"):
    os.remove("/home/z/my-project/site/CNAME")
DOMAIN = "asha-fisi-jobtoolkit.surge.sh"
env = {**os.environ, "SURGE_LOGIN": email, "SURGE_TOKEN": token}
res = subprocess.run(["npx", "-y", "surge", "/home/z/my-project/site", DOMAIN],
                     env=env, text=True, capture_output=True, timeout=280)
out = (res.stdout or "") + (res.stderr or "")
print("[deploy tail]", out.strip()[-300:].replace("\n", " | "), flush=True)
assert "Success" in out, "deploy failed"

# ---- 4. read verification mail, click link ----
print("[*] waiting for surge verification mail...", flush=True)
verify_url = None
for i in range(24):
    time.sleep(10)
    msgs = requests.get("https://api.mail.tm/messages", headers={**H, "Authorization": f"Bearer {mtok}"}, timeout=20).json()
    for msg in msgs.get("hydra:member", []):
        full = requests.get(f"https://api.mail.tm/messages/{msg['id']}", headers={**H, "Authorization": f"Bearer {mtok}"}, timeout=20).json()
        body = str(full.get("html", "")) + str(full.get("text", ""))
        m = re.search(r'https?://[^\s"\'<>]*(?:verify|confirm)[^\s"\'<>]*', body, re.I)
        if m:
            verify_url = m.group(0).replace("&amp;", "&")
            break
    if verify_url:
        break
    print(f"    ...{i+1}/24", flush=True)
if not verify_url:
    print("[!] no verification mail — site may expire; check manually", flush=True)
else:
    r = requests.get(verify_url, headers=H, timeout=30)
    print(f"[+] clicked verify link -> HTTP {r.status_code}", flush=True)

json.dump({"email": email, "password": pwd, "mailtm_token": mtok,
           "surge_token": token, "site": f"https://{DOMAIN}/"},
          open("/home/z/my-project/backups/surge_account.json", "w"), indent=2)
print(f"[+] DONE — site: https://{DOMAIN}/  (creds in backups/surge_account.json)", flush=True)
