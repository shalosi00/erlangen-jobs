#!/usr/bin/env python3
"""v21 gofile mirror with the proven fallback path.
api.gofile.io /servers first (3 attempts); on failure POST directly to a
known storage host (store-eu-par-8 worked for v18). Verifies server-side
MD5 + exact size against the local file. Dumps response to data/gofile_v21.json.
"""
import hashlib
import json
import sys
import time
import urllib.request
import uuid

BUNDLE = "/home/z/my-project/backups/asha-jobtoolkit-v21.bundle"
OUTJSON = "/home/z/my-project/data/gofile_v21.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) asha-jobtoolkit/19"


def http(url, data=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def pick_server():
    for attempt in range(3):
        try:
            js = json.loads(http("https://api.gofile.io/servers", timeout=30))
            if js.get("status") == "ok" and js.get("data", {}).get("servers"):
                return js["data"]["servers"][0]["name"]
        except Exception as e:
            print(f"servers attempt {attempt + 1} failed: {e}")
            time.sleep(15)
    return None


def upload(host):
    boundary = uuid.uuid4().hex
    with open(BUNDLE, "rb") as f:
        payload = f.read()
    pre = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
           f"filename=\"asha-jobtoolkit-v21.bundle\"\r\n"
           f"Content-Type: application/octet-stream\r\n\r\n").encode()
    body = pre + payload + f"\r\n--{boundary}--\r\n".encode()
    headers = {"User-Agent": UA,
               "Content-Type": f"multipart/form-data; boundary={boundary}",
               "Content-Length": str(len(body))}
    js = json.loads(http(f"https://{host}.gofile.io/contents/uploadfile", data=body,
                         headers=headers, timeout=900))
    return js


def main():
    raw = open(BUNDLE, "rb").read()
    md5 = hashlib.md5(raw).hexdigest()
    size = len(raw)
    sha = hashlib.sha256(raw).hexdigest()
    print(f"local: {size:,} B  md5={md5}  sha256={sha}")

    host = pick_server() or "store-eu-par-8"
    print("uploading via", host)
    js = upload(host)
    print(json.dumps(js, indent=1)[:600])

    if js.get("status") != "ok":
        sys.exit("upload failed")
    d = js["data"]
    dl, smd5, ssize = d["downloadPage"], d.get("md5", ""), int(d.get("size", 0))
    if smd5 != md5:
        sys.exit(f"MD5 MISMATCH server={smd5} local={md5}")
    if ssize != size:
        sys.exit(f"SIZE MISMATCH server={ssize} local={size}")
    print(f"VERIFIED: md5 == server md5, size exact -> {dl}")
    json.dump({"downloadPage": dl, "md5": md5, "size": size, "sha256": sha,
               "host": host}, open(OUTJSON, "w"), indent=1)


if __name__ == "__main__":
    main()
