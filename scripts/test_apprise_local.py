"""Smoke test 1b: apprise REAL end-to-end delivery to a local webhook
(json:// schema) — proves the full send path: Apprise.notify -> HTTP POST -> receipt."""
import json, threading, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

received = []
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        received.append({"path": self.path, "payload": json.loads(body)})
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":true}')
    def log_message(self, *a): pass

srv = HTTPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

import apprise
ap = apprise.Apprise()
token = uuid.uuid4().hex[:8]
assert ap.add(f"json://127.0.0.1:{port}/asha-{token}"), "add failed"
res = ap.notify(title="Asha jobtoolkit digest", body="3 new FISI postings in Erlangen 50km")
print("notify() ->", res.status)
for r in res:
    print("  per-plugin:", r.status)
print("webhook received:", len(received))
if received:
    p = received[0]["payload"]
    print("  path:", received[0]["path"])
    print("  title:", p.get("title"))
    print("  body:", p.get("message"))
ok = res.status.name == "SUCCESS" and received and "3 new FISI" in received[0]["payload"].get("message", "")
print("E2E", "PASS" if ok else "FAIL")
srv.shutdown()
