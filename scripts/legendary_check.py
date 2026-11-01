"""Task 12: verify legendary-repo candidates via GitHub API (anon, 60 req/h)."""
import json, urllib.request, time

REPOS = [
    # --- notification / digest layer
    ("caronc/apprise",            "notification hub: 100+ services (Telegram/ntfy/mail)"),
    ("binwiederhier/ntfy",        "push via plain HTTP POST (public ntfy.sh free)"),
    # --- persistent storage / exploration
    ("simonw/sqlite-utils",       "CLI+lib: JSON/CSV -> SQLite + FTS5 search"),
    ("simonw/datasette",          "instant interactive web UI for SQLite"),
    ("duckdb/duckdb",             "SQL analytics directly on CSV"),
    # --- dedupe / matching
    ("rapidfuzz/rapidfuzz",       "C++ fuzzy matching (successor of fuzzywuzzy/thefuzz)"),
    ("seatgeek/thefuzz",          "old fuzzy matching (superseded?)"),
    # --- scraping resilience (browser tier)
    ("D4Vinci/Scrapling",         "adaptive auto-healing selectors"),
    ("unclecode/crawl4ai",        "LLM-friendly crawler (Playwright)"),
    ("stephanlensky/zendriver",   "undetected-chrome successor, no selenium"),
    ("omkarcloud/botasaurus",     "scraping framework w/ anti-detection"),
    # --- change monitoring
    ("dgtlmoon/changedetection.io", "website diff monitoring + alerts"),
    # --- cron reliability
    ("healthchecks/healthchecks", "dead-man's switch for cron"),
    # --- local AI layer (zero-cost)
    ("ollama/ollama",             "local LLM runtime"),
    ("simonw/llm",                "CLI/lib for LLMs incl. local models"),
    # --- career side (Asha-facing)
    ("AmruthPillai/Reactive-Resume", "CV builder (self-host)"),
    ("xitanggg/open-resume",      "resume parser + builder"),
    # --- backup upgrade candidate
    ("restic/restic",             "encrypted incremental backups"),
]

def get(repo):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}",
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": "asha-research"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
        return (d.get("stargazers_count"), d.get("pushed_at", "")[:10],
                d.get("archived"), d.get("open_issues_count"),
                (d.get("description") or "")[:80])
    except Exception as e:
        return ("ERR", str(e)[:60], "", "", "")

print(f"{'repo':<34} {'stars':>7} {'pushed':>11} {'arch':<5} {'issues':>6}  aspect")
print("-" * 110)
for repo, why in REPOS:
    stars, pushed, arch, issues, desc = get(repo)
    print(f"{repo:<34} {stars:>7} {pushed:>11} {str(arch):<5} {str(issues):>6}  {why}")
    time.sleep(0.4)
