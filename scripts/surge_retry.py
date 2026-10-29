#!/usr/bin/env python3
"""Clean retry: purge ~/.surge cache, create fresh surge account bound to the
SAVED mail.tm mailbox, deploy, trigger verification, click the link."""
import glob, json, os, re, subprocess, time
import requests

BASE = "/home/z/my-project"
d = json.load(open(f"{BASE}/backups/surge_account.json"))
email, pwd, mtok = d["email"], d["password"], d.get("mailtm_token")
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/127.0.0.0 Safari/537.36"}

# 1. purge surge credential cache
for f in [os.path.expanduser("~/.surge"), os.path.expanduser("~/.surge/config")] + glob.glob(os.path.expanduser("~/.config/surge*")):
    if os.path.isfile(f):
        os.remove(f)
        print(f"[+] removed {f}", flush=True)

# 2. fresh JWT for the saved mailbox
rt = requests.post("https://api.mail.tm/token", headers={**H, "Content-Type": "application/json"},
                   data=json.dumps({"address": email, "password": pwd}), timeout=20)
assert rt.status_code == 200, f"mailbox login failed: {rt.text[:120]}"
mtok = rt.json()["token"]
print(f"[+] mailbox OK: {email}", flush=True)

# 3. fresh surge account -> token (pty)
res = subprocess.run("script -qec 'npx -y surge token' /dev/null", shell=True,
                     input=f"{email}\n{pwd}\n", text=True, capture_output=True, timeout=150)
out = (res.stdout or "") + (res.stderr or "")
lines = [l for l in out.splitlines() if re.fullmatch(r"\s*[0-9a-f]{32,40}\s*", l)]
assert lines, f"token not found; tail: {out[-400:]!r}"
token = lines[-1].strip()
print(f"[+] new surge token: {token}", flush=True)

# sanity: whoami
w = subprocess.run("npx -y surge whoami", shell=True, text=True, capture_output=True,
                   env={**os.environ, "SURGE_LOGIN": email, "SURGE_TOKEN": token}, timeout=90)
print(f"[+] whoami: {(w.stdout or w.stderr).strip()[:120]}", flush=True)

# 4. deploy to fresh domain
DOMAIN = "asha-fisi-jt.surge.sh"
if os.path.exists(f"{BASE}/site/CNAME"):
    os.remove(f"{BASE}/site/CNAME")
res = subprocess.run(["npx", "-y", "surge", f"{BASE}/site", DOMAIN], text=True,
                     capture_output=True, timeout=280,
                     env={**os.environ, "SURGE_LOGIN": email, "SURGE_TOKEN": token})
out = (res.stdout or "") + (res.stderr or "")
print("[deploy]", out.strip()[-200:].replace("\n", " | "), flush=True)
assert "Success" in out, "deploy failed"

# 5. trigger verification mail
res = subprocess.run("npx -y surge verify", shell=True, text=True, capture_output=True, timeout=120,
                     env={**os.environ, "SURGE_LOGIN": email, "SURGE_TOKEN": token})
print("[verify trigger]", ((res.stdout or "") + (res.stderr or "")).strip()[-160:].replace("\n", " | "), flush=True)

# 6. poll mailbox, click link
link = None
for i in range(30):
    time.sleep(10)
    msgs = requests.get("https://api.mail.tm/messages", headers={**H, "Authorization": f"Bearer {mtok}"}, timeout=20).json()
    for m in msgs.get("hydra:member", []):
        full = requests.get(f"https://api.mail.tm/messages/{m['id']}", headers={**H, "Authorization": f"Bearer {mtok}"}, timeout=20).json()
        body = str(full.get("html", "")) + str(full.get("text", ""))
        cands = re.findall(r'https?://[^\s"\'<>]+', body)
        for u in cands:
            if "surge" in u and ("verify" in u or "confirm" in u or "token" in u):
                link = u.replace("&amp;", "&")
                break
        if link:
            break
    if link:
        break
    print(f"    ...{i+1}/30", flush=True)
if link:
    r = requests.get(link, headers=H, timeout=30, allow_redirects=True)
    ok = "verif" in r.text.lower() or r.status_code == 200
    print(f"[+] clicked link -> HTTP {r.status_code}", flush=True)
else:
    print("[!] no verification mail received", flush=True)

json.dump({"email": email, "password": pwd, "mailtm_token": mtok,
           "surge_token": token, "site": f"https://{DOMAIN}/", "verified": bool(link)},
          open(f"{BASE}/backups/surge_account.json", "w"), indent=2)
print(f"[+] site: https://{DOMAIN}/ verified={bool(link)}", flush=True)
