#!/usr/bin/env python3
"""mail.tm disposable inbox helper — create account, poll messages, extract links.
Usage:
  python3 mailtm.py create                 -> prints address; stores creds in /home/z/my-project/.mailtm.json
  python3 mailtm.py list                   -> list inbox messages
  python3 mailtm.py read <msg_id>          -> print message text/links
  python3 mailtm.py wait-for <substring>   -> poll until a message contains substring; prints its id
"""
import json, sys, time, re
import requests

BASE = "https://api.mail.tm"
CREDS = "/home/z/my-project/.mailtm.json"

def _headers(tok=None):
    h = {"Accept": "application/json", "Content-Type": "application/json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h

def _token(addr, pw):
    r = requests.post(f"{BASE}/token", json={"address": addr, "password": pw}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]

def create():
    dom = requests.get(f"{BASE}/domains", headers=_headers(), timeout=20).json()
    items = dom["hydra:member"] if isinstance(dom, dict) else dom
    domain = next(d["domain"] for d in items if d.get("isActive"))
    addr = f"ashajt{int(time.time())%10000000}@{domain}"
    pw = "Ash!2026Toolkit#" + str(int(time.time()))[-4:]
    r = requests.post(f"{BASE}/accounts", json={"address": addr, "password": pw},
                      headers=_headers(), timeout=20)
    if r.status_code not in (200, 201):
        print("account create failed:", r.status_code, r.text[:200]); sys.exit(1)
    tok = _token(addr, pw)
    json.dump({"address": addr, "password": pw, "token": tok}, open(CREDS, "w"))
    print(addr)

def _auth():
    d = json.load(open(CREDS))
    try:
        requests.get(f"{BASE}/me", headers=_headers(d["token"]), timeout=15).raise_for_status()
    except Exception:
        d["token"] = _token(d["address"], d["password"])
        json.dump(d, open(CREDS, "w"))
    return d

def list_msgs():
    d = _auth()
    r = requests.get(f"{BASE}/messages?page=1", headers=_headers(d["token"]), timeout=20)
    for m in r.json()["hydra:member"]:
        print(f"{m['id']}  from={m['from']['address']}  subj={m.get('subject','')!r}")

def read(msg_id):
    d = _auth()
    r = requests.get(f"{BASE}/messages/{msg_id}", headers=_headers(d["token"]), timeout=20)
    m = r.json()
    print("FROM:", m["from"]["address"])
    print("SUBJ:", m.get("subject"))
    body = m.get("text") or ""
    html = m.get("html") or ""
    links = re.findall(r'https?://[^\s"\'<>]+', html) + re.findall(r'https?://[^\s"\'<>]+', body)
    print("TEXT:", body[:2000])
    print("LINKS:")
    for l in dict.fromkeys(links):
        print("  ", l)

def wait_for(sub, timeout=180):
    d = _auth()
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{BASE}/messages?page=1", headers=_headers(d["token"]), timeout=20)
        for m in r.json()["hydra:member"]:
            if sub.lower() in (m.get("subject","") + m["from"]["address"]).lower():
                print(m["id"]); return
        time.sleep(6)
    print("TIMEOUT")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "create": create()
    elif cmd == "list": list_msgs()
    elif cmd == "read": read(sys.argv[2])
    elif cmd == "wait-for": wait_for(sys.argv[2])
