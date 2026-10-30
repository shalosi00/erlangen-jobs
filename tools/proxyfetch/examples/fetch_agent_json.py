#!/usr/bin/env python3
"""Agent-style usage: parse the JSON payload programmatically.

The subprocess boundary is the safest integration point for agents:
stdout carries exactly one JSON document (proxyfetch.result/v1).
"""
import json
import subprocess

proc = subprocess.run(
    [
        "proxyfetch",
        "https://www.autoscout24.de/lst/dacia/jogger",
        "--pages", "2",
        "--json",
        "--no-save",
    ],
    capture_output=True, text=True, timeout=600,
)

payload = json.loads(proc.stdout)
if payload["ok"]:
    for it in payload["items"]:
        print(it.get("price_eur"), it.get("title"), it.get("url"))
else:
    print("failed:", payload["error"], file=__import__("sys").stderr)
print("exit code:", proc.returncode)
