#!/usr/bin/env python3
"""GitHub Search API sweep: broad categories of programmatic-job-search repos.
Unauthenticated: 10 search calls/min — we use 8, keeping 2 spare."""
import json, urllib.request, urllib.parse, time, os

OUT = "/home/z/my-project/research/github-repos/gh_search"
os.makedirs(OUT, exist_ok=True)
H = {"Accept": "application/vnd.github+json", "User-Agent": "jobhunt-research"}

QUERIES = {
    "scrapers_py":    "job scraper language:python stars:>50",
    "search_agent":   "job search agent stars:>20",
    "easy_apply":     "linkedin easy apply stars:>15",
    "auto_apply":     "auto apply jobs stars:>15",
    "trackers":       "job application tracker stars:>30",
    "jobspy":         "jobspy",
    "llm_apply":      "job application LLM stars:>30",
    "ats_feeds":      "greenhouse lever jobs scraper stars:>10",
}

def get(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

index = {}
for name, q in QUERIES.items():
    url = ("https://api.github.com/search/repositories?q=" + urllib.parse.quote(q)
           + "&sort=stars&order=desc&per_page=12")
    try:
        d = get(url)
        items = d.get("items", [])
        json.dump(d, open(f"{OUT}/{name}.json", "w"), indent=1)
        for it in items:
            index[it["full_name"]] = {
                "stars": it["stargazers_count"], "pushed": it["pushed_at"][:10],
                "lang": it.get("language"), "desc": (it.get("description") or "")[:130],
                "archived": it.get("archived"), "url": it["html_url"], "cat": name}
        print(f"{name:<14} {len(items):>2} repos (total {d.get('total_count')})")
        time.sleep(7)  # stay under 10/min comfortably
    except Exception as e:
        print(f"{name:<14} FAILED: {e}")
        time.sleep(10)

json.dump(index, open(f"{OUT}/_index.json", "w"), indent=1)
print(f"\nmerged unique: {len(index)}")
for fn, v in sorted(index.items(), key=lambda x: -x[1]["stars"]):
    flag = " [ARCHIVED]" if v["archived"] else ""
    print(f"{v['stars']:>5}* {fn:<52} {v['pushed']} {v['lang'] or '':<12}{flag} {v['desc'][:70]}")
