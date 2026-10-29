#!/usr/bin/env python3
"""Quick live check: pipeline kimeta source (requests + validated pool) vs
proxyfetch (aiohttp). Proves which proxied stack fetches kimeta today."""
import sys, time
sys.path.insert(0, "/home/z/my-project")

from pipeline.sources.kimeta import _fetch_serp
from pipeline.core import FetchCtx  # guess ctx name

URL = "https://www.kimeta.de/fachinformatiker-systemintegration-jobs-erlangen"

def main() -> None:
    import inspect
    from pipeline import core
    # locate ctx class
    cand = [n for n, o in inspect.getmembers(core, inspect.isclass) if "Ctx" in n or "Context" in n]
    print("ctx classes:", cand)
    ctx_cls = getattr(core, cand[0])
    sig = inspect.signature(ctx_cls)
    print("ctx params:", list(sig.parameters)[:12])
    kwargs = {"query": "fachinformatiker systemintegration", "city": "Erlangen",
              "radius": 50, "days": 14, "timeout": 25}
    kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
    ctx = ctx_cls(**kwargs)
    t0 = time.time()
    html = _fetch_serp(ctx, URL)
    dt = time.time() - t0
    ok = "kimeta" in html.lower() and len(html) > 5000
    print(f"kimeta via pipeline stack: {len(html):,} bytes in {dt:.1f}s | looks-like-SERP: {ok}")
    print("title:", html.split("<title>")[1].split("</title>")[0][:90] if "<title>" in html else "?")

if __name__ == "__main__":
    main()
