#!/usr/bin/env python3
"""Unified search across the 5 aggregators that work with plain requests
(verified live 2026-10-13): Connecticum, Get-in-IT, Berufsstart.de,
Jobs.InFranken.de, Talent.com DE. Merges, dedupes, extracts dates best-effort,
sorts by date desc -> CSV. Politeness: 1.5 s sleep between hits."""
import csv, html, json, re, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}
# repo root (scrapers/ is one level below) — clone-safe, no hardcoded sandbox path
_REPO = Path(__file__).resolve().parent.parent
OUT = str(_REPO / "download" / "aggregator_multi_source_FISI_erlangen.csv")
_REPO.joinpath("download").mkdir(parents=True, exist_ok=True)
KEYWORD = sys.argv[1] if len(sys.argv) > 1 else "Fachinformatiker"
CITY = "Erlangen"
JUNIOR_RX = re.compile(r"junior|einsteiger|absolvent|trainee|azubi|berufseinsteiger|assistant|praktikum|werkstudent", re.I)

def get(url):
    r = requests.get(url, headers=H, timeout=25, allow_redirects=True)
    time.sleep(1.5)
    return r.text if r.status_code == 200 else ""

def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def date_iso(text, base=None):
    if not text:
        return ""
    t = text.lower()
    base = base or datetime.now()
    if re.search(r"\bheute\b|today|vor (einer? )?stunde|hours? ago|vor \d+ stunden?", t):
        return base.strftime("%Y-%m-%d")
    if "gestern" in t or "yesterday" in t:
        return (base - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"vor (\d+) tagen?", t) or re.search(r"(\d+) days? ago", t)
    if m:
        return (base - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r"vor (\d+) wochen?", t) or re.search(r"(\d+) weeks? ago", t)
    if m:
        return (base - timedelta(weeks=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)
    return ""

def cards_from_anchors(h, href_rx, site):
    """generic: for each matching anchor, take its inner text as title, plus
    +/-220 chars context for company/date extraction."""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(' + href_rx + r')"[^>]*>(.*?)</a>', h, re.S):
        url, inner = m.group(1), clean(m.group(2))
        ctx = h[max(0, m.start() - 220): m.end() + 220]
        if not inner or len(inner) < 8:
            t = re.search(r'title="([^"]{8,140})"', m.group(0))
            if not t:
                continue
            inner = clean(t.group(1))
        if url in seen or re.search(r"magazin|ratgeber|service|kontakt|login|news|tipps", inner, re.I):
            continue
        seen.add(url)
        out.append({"source": site, "title": inner[:140], "url": url,
                    "context": clean(ctx)[:300]})
    return out

def src_connecticum():
    h = get(f"https://www.connecticum.de/jobs?searchterm={KEYWORD}&submit=1")
    rx = r"(?:https://www\.connecticum\.de)?/jobs/[a-z0-9-]+-\d{6,}"
    rows = cards_from_anchors(h, rx, "connecticum")
    if not rows:  # transient WAF flake -> one retry after pause
        time.sleep(6)
        h = get(f"https://www.connecticum.de/jobs?searchterm={KEYWORD}&submit=1")
        rows = cards_from_anchors(h, rx, "connecticum")
    for r in rows:
        pos = h.find(r["url"])
        before = clean(h[max(0, pos - 700):pos]) if pos > 0 else ""
        m = re.search(r"/arbeitgeber/[a-z0-9-]+-\d+\" title=\"([^\"]{2,60})", before)
        r["company"] = clean(m.group(1)) if m else ""
        r["location"] = CITY
        r["date"] = date_iso(before) or date_iso(r["context"])
        if not r["url"].startswith("http"):
            r["url"] = "https://www.connecticum.de" + r["url"]
    return rows

def src_getinit():
    h = get(f"https://www.get-in-it.de/jobsuche?was={KEYWORD}&wo={CITY}")
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+class="CardJob_jobCard[^"]*"[^>]+href="(/jobsuche/p\d+)[^"]*"[^>]*>(.*?)</a>', h, re.S):
        url, block = m.group(1), clean(m.group(2))
        if url in seen or len(block) < 8:
            continue
        seen.add(url)
        out.append({"source": "get-in-it", "title": block[:140], "company": "",
                    "location": CITY, "date": date_iso(block),
                    "url": "https://www.get-in-it.de" + url, "context": block[:300]})
    return out

def src_berufsstart():
    h = get(f"https://www.berufsstart.de/ergebnisliste.php?suchbegriff={KEYWORD}")
    rows = cards_from_anchors(h, r"appscripts/jobs/anzeigenAusgabe\.php\?AnzeigenID=\d+", "berufsstart")
    for r in rows:
        r["url"] = "https://www.berufsstart.de/" + r["url"]
        r["company"], r["location"] = "", ""
        r["date"] = date_iso(r["context"])
    return rows

def src_infranken():
    h = get(f"https://jobs.infranken.de/suchergebnisse?Searchterm={KEYWORD}")
    out, seen = [], set()
    for m in re.finditer(r'<h2 class="job-name">\s*<a href="(/jobs/\d+/[^"]*)"[^>]*>(.*?)</a>', h, re.S):
        url, title = m.group(1), clean(m.group(2))
        if url in seen or len(title) < 8:
            continue
        seen.add(url)
        ctx = clean(h[m.start(): m.end() + 700])
        out.append({"source": "infranken", "title": title[:140], "company": "",
                    "location": CITY, "date": date_iso(ctx),
                    "url": "https://jobs.infranken.de" + url, "context": ctx[:300]})
    return out

def src_talent():
    h = get(f"https://de.talent.com/jobs?k={KEYWORD}&l={CITY}")
    urls = []
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)
    if m:
        try:
            j = json.loads(m.group(1))
            for node in j.get("@graph", []):
                if node.get("@type") == "ItemList" and node.get("@id") == "#jobList":
                    urls = [it["item"]["url"] for it in node.get("itemListElement", [])]
        except Exception:
            pass
    if not urls:  # fallback: plain /view links
        urls = ["https://de.talent.com" + u for u in re.findall(r'href="(/view\?id=\d+)"', h)]
    # h2 blocks carry title + "company • location" after them
    blocks = re.findall(r'<h2[^>]*>(.*?)</h2>(.*?)(?=<h2|\Z)', h, re.S)
    out, seen = [], set()
    for i, url in enumerate(urls):
        title, company, loc = "", "", CITY
        if i < len(blocks):
            title = clean(blocks[i][0])
            after = clean(blocks[i][1])[:160]
            parts = after.split("•")
            if len(parts) >= 2:
                company = parts[0].strip()[:70]
                loc = parts[1].split()[0].strip()[:40] or CITY
        if not title or len(title) < 8 or re.search(r"mehr anzeigen|faq|städte", title, re.I):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append({"source": "talent.com", "title": title[:140], "company": company,
                    "location": loc, "date": "",
                    "url": url if url.startswith("http") else "https://de.talent.com" + url,
                    "context": after if i < len(blocks) else ""})
    return out

all_rows = []
for fn in (src_connecticum, src_getinit, src_berufsstart, src_infranken, src_talent):
    name = fn.__name__.replace("src_", "")
    try:
        rows = fn()
        print(f"{name:12} -> {len(rows)} jobs", flush=True)
        all_rows += rows
    except Exception as e:
        print(f"{name:12} -> ERROR {type(e).__name__}: {str(e)[:70]}", flush=True)

seen, final = set(), []
for r in all_rows:
    key = re.sub(r"\W+", "", r["title"].lower())[:60]
    if not key or key in seen:
        continue
    seen.add(key)
    r["junior_hit"] = "YES" if JUNIOR_RX.search(r["title"] + " " + r.get("context", "")) else ""
    r["date"] = r.get("date") or ""
    final.append(r)

final.sort(key=lambda r: (r["date"] or "0000-00-00"), reverse=True)
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["source", "title", "company", "location", "date", "junior_hit", "url", "context"])
    for r in final:
        w.writerow([r["source"], r["title"], r["company"], r["location"], r["date"], r["junior_hit"], r["url"], r["context"]])
print(f"\nTOTAL {len(final)} unique jobs -> {OUT}")
print("per source:", {s: sum(1 for r in final if r['source'] == s) for s in set(r['source'] for r in final)})
