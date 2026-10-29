#!/usr/bin/env python3
"""Parse raw web-search results -> unique GitHub repo candidates."""
import json, re, glob, collections, os

RAW = "/home/z/my-project/research/github-repos/raw"
OUT = "/home/z/my-project/research/github-repos/candidates.json"

REPO_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", re.I)
SKIP_PARTS = {"topics", "search", "features", "collections", "trending", "sponsors",
              "marketplace", "settings", "orgs", "about", "site", "docs", "security"}
SKIP_TAILS = {"", "stargazers", "forks", "issues", "pulls", "watchers", "graphs", "network", "pulse"}

hits = []          # (repo, source_query, title, snippet, rank)
for path in sorted(glob.glob(f"{RAW}/q*.json")):
    qid = os.path.basename(path).replace(".json", "")
    try:
        data = json.load(open(path))
    except Exception:
        continue
    for item in data if isinstance(data, list) else data.get("results", []):
        url, title, snip = item.get("url", ""), item.get("name", ""), item.get("snippet", "")
        host = item.get("host_name", "")
        found = set()
        for m in REPO_RE.finditer(url):
            found.add(m.groups())
        if "github.com" in host:
            # repo shown as "owner/repo: description" in the title
            for m in re.finditer(r"\b([A-Za-z0-9_.-]{2,})/([A-Za-z0-9_.-]{2,})(?=\s*[:\-—\]|]|$)", title):
                found.add(m.groups())
        for owner, repo in found:
            if owner.lower() in SKIP_PARTS or repo.lower() in SKIP_TAILS:
                continue
            hits.append((f"{owner}/{repo}", qid, title[:90], snip[:150], item.get("rank")))

# dedupe by repo, keep sources
by_repo = collections.OrderedDict()
for repo, qid, title, snip, rank in hits:
    e = by_repo.setdefault(repo, {"repo": repo, "queries": [], "titles": [], "snippets": [], "count": 0})
    if qid not in e["queries"]:
        e["queries"].append(qid)
    e["count"] += 1
    if title and title not in e["titles"] and len(e["titles"]) < 3:
        e["titles"].append(title)
    if snip and snip not in e["snippets"] and len(e["snippets"]) < 3:
        e["snippets"].append(snip)

cands = sorted(by_repo.values(), key=lambda e: (-e["count"], e["repo"]))
json.dump(cands, open(OUT, "w"), indent=1)
print(f"unique repos: {len(cands)}  (raw hits: {len(hits)})")
for c in cands[:60]:
    print(f"{c['count']:>2}x  {c['repo']:<58} {','.join(q.split('_')[0] for q in c['queries'])}")
