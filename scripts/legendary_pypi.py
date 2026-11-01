"""Task 12: verify pip-installable legendary candidates via PyPI JSON API."""
import json, urllib.request, time

PKGS = ["apprise", "sqlite-utils", "datasette", "rapidfuzz", "duckdb",
        "scrapling", "crawl4ai", "zendriver", "botasaurus", "llm",
        "requests-cache", "trafilatura", "ntfy", "pandera", "thefuzz",
        "ollama", "tenacity", "dateparser"]

def pypi(pkg):
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=20) as r:
            d = json.load(r)
        info = d["info"]
        rel = d["releases"].get(info["version"], [])
        uploaded = rel[0]["upload_time"][:10] if rel else "?"
        deps = info.get("requires_dist") or []
        return (info["version"], uploaded, len(deps), (info["summary"] or "")[:70])
    except Exception as e:
        return ("ERR", str(e)[:50], "", "")

print(f"{'package':<16} {'version':<12} {'released':>11} {'deps':>5}  summary")
print("-" * 120)
for p in PKGS:
    v, up, nd, s = pypi(p)
    print(f"{p:<16} {v:<12} {up:>11} {str(nd):>5}  {s}")
    time.sleep(0.3)
