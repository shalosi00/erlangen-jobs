"""Task 12: GitHub star counts via shields.io badge JSON (no API rate limit)."""
import json, re, time, urllib.request

REPOS = ["caronc/apprise", "binwiederhier/ntfy", "simonw/sqlite-utils",
         "simonw/datasette", "duckdb/duckdb", "rapidfuzz/rapidfuzz",
         "seatgeek/thefuzz", "D4Vinci/Scrapling", "unclecode/crawl4ai",
         "stephanlensky/zendriver", "omkarcloud/botasaurus",
         "dgtlmoon/changedetection.io", "healthchecks/healthchecks",
         "ollama/ollama", "simonw/llm", "AmruthPillai/Reactive-Resume",
         "xitanggg/open-resume", "restic/restic"]

def stars(repo):
    url = f"https://img.shields.io/github/stars/{repo}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "asha-research"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
        m = re.search(r"([\d.]+[kM]?)", d.get("value", ""))
        return m.group(1) if m else d.get("value", "?")
    except Exception as e:
        return f"ERR {str(e)[:40]}"

for repo in REPOS:
    print(f"{repo:<34} {stars(repo):>8} stars")
    time.sleep(0.3)
