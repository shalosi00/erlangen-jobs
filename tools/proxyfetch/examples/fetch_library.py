#!/usr/bin/env python3
"""Library usage: fetch an arbitrary URL through the auto proxy pool.

Requires network access. The stealth browser is optional; without it the
tool still works via the urllib rotation path.
"""
from proxyfetch import Config, run

payload = run(Config(
    url="https://www.autoscout24.de/lst/dacia/jogger?atype=C&cy=D&ustate=N%2CU",
    pages=2,
    name="dacia-jogger",
    out_dir="out",
))

print(f"ok={payload['ok']} count={payload['count']}")
for item in payload["items"][:5]:
    print("-", item.get("title"), item.get("price_eur"))
