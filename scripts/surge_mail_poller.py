#!/usr/bin/env python3
"""Background poller: if surge verification mail arrives within 60 min, click it."""
import json, re, time, requests

BASE = "/home/z/my-project"
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/127.0.0.0 Safari/537.36"}
deadline = time.time() + 3600
while time.time() < deadline:
    try:
        d = json.load(open(f"{BASE}/backups/surge_account.json"))
        r = requests.post("https://api.mail.tm/token", headers={**H, "Content-Type": "application/json"},
                          data=json.dumps({"address": d["email"], "password": d["password"]}), timeout=20)
        if r.status_code == 200:
            tok = r.json()["token"]
            msgs = requests.get("https://api.mail.tm/messages", headers={**H, "Authorization": f"Bearer {tok}"}, timeout=20).json()
            for m in msgs.get("hydra:member", []):
                full = requests.get(f"https://api.mail.tm/messages/{m['id']}", headers={**H, "Authorization": f"Bearer {tok}"}, timeout=20).json()
                body = str(full.get("html", "")) + str(full.get("text", ""))
                for u in re.findall(r'https?://[^\s"\'<>]+', body):
                    if "surge" in u and any(k in u for k in ("verify", "confirm", "token")):
                        resp = requests.get(u.replace("&amp;", "&"), headers=H, timeout=30, allow_redirects=True)
                        open(f"{BASE}/backups/surge_verify_status.txt", "a").write(
                            f"{time.strftime('%F %T')} clicked {u[:100]} -> {resp.status_code}\n")
                        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        pass
    time.sleep(240)
open(f"{BASE}/backups/surge_verify_status.txt", "a").write(f"{time.strftime('%F %T')} no mail within 60min, giving up\n")
