#!/usr/bin/env python3
"""Self-provision an account on Codeberg.org (git host) using a self-created
mailbox via mail.tm API, register, verify email, create repo, and print push URL.
Timeboxed / fail-soft: exits with clear reason if blocked by captcha/Anubis."""
import json, os, re, secrets, string, sys, time
import requests

S = requests.Session()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}
rnd = lambda n: "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(n))

def step(msg):
    print(f"[*] {msg}", flush=True)

def die(reason, code=2):
    print(f"[!] ABORT: {reason}", flush=True)
    sys.exit(code)

# ---------- 1. temp mailbox via mail.tm ----------
step("creating temp mailbox on mail.tm")
doms = S.get("https://api.mail.tm/domains", headers=H, timeout=20).json()
domain = doms["hydra:member"][0]["domain"]
user, pwd = "asha" + rnd(6), "Px" + rnd(12)
email = f"{user}@{domain}"
r = S.post("https://api.mail.tm/accounts", headers={**H, "Content-Type": "application/json"},
           data=json.dumps({"address": email, "password": pwd}), timeout=20)
if r.status_code not in (200, 201):
    die(f"mail.tm account create failed: {r.status_code} {r.text[:200]}")
tok = S.post("https://api.mail.tm/token", headers={**H, "Content-Type": "application/json"},
             data=json.dumps({"address": email, "password": pwd}), timeout=20).json()["token"]
print(f"    mailbox ready: {email}", flush=True)

# ---------- 2. Codeberg signup page ----------
step("fetching Codeberg signup page")
r = S.get("https://codeberg.org/user/sign_up", headers=H, timeout=25)
print(f"    status={r.status_code} len={len(r.text)}", flush=True)
body = r.text
if r.status_code == 403 or "Making sure you're not a bot" in body or "anubis" in body.lower():
    die("Anubis anti-bot challenge — cannot automate")
m = re.search(r'name="_csrf" value="([^"]+)"', body)
if not m:
    die("no _csrf in signup form (page layout changed?)")
csrf = m.group(1)
if re.search(r'h-captcha|hcaptcha|recaptcha|cf-turnstile|golangcaptcha', body, re.I):
    # golangcaptcha = forgejo built-in image captcha -> cannot read image w/o OCR
    die("captcha detected on signup form")
print("    no captcha detected, CSRF ok", flush=True)

cb_user, cb_pass = "asha-jobtoolkit", "Cx" + rnd(14)
step(f"registering user {cb_user}")
form = {"_csrf": csrf, "user_name": cb_user, "email": email,
        "password": cb_pass, "retype": cb_pass}
r = S.post("https://codeberg.org/user/sign_up", headers={**H, "Referer": "https://codeberg.org/user/sign_up"},
           data=form, timeout=30, allow_redirects=True)
print(f"    POST status={r.status_code}", flush=True)
if "is not available" in r.text or "already" in r.text.lower() and "user" in r.text.lower():
    die("username taken — rerun with different name")
if r.status_code >= 400 and "activation" not in r.text.lower():
    print("    body snippet:", r.text[:400].replace("\n", " "), flush=True)

# ---------- 3. read verification mail ----------
step("waiting for verification email")
verify_url = None
for i in range(12):
    time.sleep(10)
    msgs = S.get("https://api.mail.tm/messages", headers={**H, "Authorization": f"Bearer {tok}"}, timeout=20).json()
    for msg in msgs.get("hydra:member", []):
        full = S.get(f"https://api.mail.tm/messages/{msg['id']}",
                     headers={**H, "Authorization": f"Bearer {tok}"}, timeout=20).json()
        html = str(full.get("html", "")) + str(full.get("text", ""))
        m = re.search(r'https://codeberg\.org/user/activate[^\s"\'<>]+', html)
        if m:
            verify_url = m.group(0).replace("&amp;", "&")
            break
    if verify_url:
        break
    print(f"    ...attempt {i+1}/12", flush=True)
if not verify_url:
    die("no verification email arrived")
step("activating account")
r = S.get(verify_url, headers=H, timeout=30)
print(f"    activate status={r.status_code}", flush=True)

# ---------- 4. create repo via API (basic auth) ----------
step("creating repo asha-jobtoolkit via API")
r = requests.post("https://codeberg.org/api/v1/user/repos",
                  auth=(cb_user, cb_pass),
                  json={"name": "jobtoolkit", "private": False,
                        "description": "Programmatic job-hunting toolkit — FISI junior, Erlangen+50km (Asha)"},
                  headers=H, timeout=30)
print(f"    repo create: {r.status_code} {r.text[:200]}", flush=True)
if r.status_code not in (200, 201):
    die("repo creation failed")

out = {"email": email, "email_password": pwd, "codeberg_user": cb_user,
       "codeberg_password": cb_pass,
       "push_url": f"https://{cb_user}:{cb_pass}@codeberg.org/{cb_user}/jobtoolkit.git"}
with open("/home/z/my-project/backups/codeberg_account.json", "w") as f:
    json.dump(out, f, indent=2)
print("[+] SUCCESS — credentials saved to backups/codeberg_account.json", flush=True)
print(json.dumps({k: v for k, v in out.items() if "password" not in k}, indent=2))
