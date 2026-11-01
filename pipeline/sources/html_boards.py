"""The 5 HTML boards verified working with plain requests from this IP (round-2
probes): Connecticum, Get-in-IT, Berufsstart.de, Jobs.InFranken.de, Talent.com DE.
Parse recipes in research/aggregators-round2/findings.md §A."""
import json, re, time
import requests
from pipeline.core import Job, SourceError, date_from_text, strip_html
from pipeline.sources._base import register, check_http

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
      "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}

def _get(ctx, url):
    try:
        r = requests.get(url, headers=UA, timeout=ctx.timeout, allow_redirects=True)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"timeout after {ctx.timeout}s: {url}", url=url)
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"connection failed: {str(e)[:110]}", url=url)
    check_http(r, "html", url)
    time.sleep(ctx.sleep)
    return r.text

@register("connecticum", geo_scope="country")
def fetch(ctx) -> list[Job]:
    h = _get(ctx, f"https://www.connecticum.de/jobs?searchterm={ctx.query}&submit=1")
    jobs, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="((?:https://www\.connecticum\.de)?/jobs/[a-z0-9-]+-\d{6,})"[^>]*>(.*?)</a>', h, re.S):
        url, inner = m.group(1), strip_html(m.group(2))
        if url in seen or len(inner) < 8:
            continue
        seen.add(url)
        ctx_before = strip_html(h[max(0, m.start() - 700):m.start()])
        comp = re.search(r'arbeitgeber/[a-z0-9-]+-\d+" title="([^"]{2,60})"', h[max(0, m.start() - 900):m.start()])
        jobs.append(Job(
            source="Connecticum", title=inner[:140], company=strip_html(comp.group(1)) if comp else "",
            date_posted=date_from_text(h[max(0, m.start() - 220):m.end() + 220]),
            url=url if url.startswith("http") else "https://www.connecticum.de" + url,
            description=ctx_before[:800],
        ))
    return jobs

@register("getinit", geo_scope="query")
def fetch(ctx) -> list[Job]:
    h = _get(ctx, f"https://www.get-in-it.de/jobsuche?was={ctx.query}&wo={ctx.city}")
    jobs, seen = [], set()
    for m in re.finditer(r'<a[^>]+class="CardJob_jobCard[^"]*"[^>]+href="(/jobsuche/p\d+)[^"]*"[^>]*>(.*?)</a>', h, re.S):
        url, block = m.group(1), m.group(2)
        if url in seen:
            continue
        seen.add(url)
        mt = re.search(r'CardJob_jobTitle[^>]*>([^<]+)<', block)
        mc = re.search(r'CardJob_logo[^>]*>.*?title="([^"]{2,80})"', block, re.S)
        title = strip_html(mt.group(1)) if mt else strip_html(block)
        if len(title) < 6:
            continue
        jobs.append(Job(
            source="Get-in-IT", title=title[:140],
            company=strip_html(mc.group(1)) if mc else "",
            date_posted=date_from_text(strip_html(block)[:400]),
            url="https://www.get-in-it.de" + url,
            description=strip_html(block)[:800],
        ))
    return jobs

@register("berufsstart", geo_scope="country")
def fetch(ctx) -> list[Job]:
    h = _get(ctx, f"https://www.berufsstart.de/ergebnisliste.php?suchbegriff={ctx.query}")
    jobs, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(appscripts/jobs/anzeigenAusgabe\.php\?AnzeigenID=\d+)"[^>]*>(.*?)</a>', h, re.S):
        url, inner = m.group(1), strip_html(m.group(2))
        if url in seen or len(inner) < 8:
            continue
        seen.add(url)
        jobs.append(Job(
            source="Berufsstart", title=inner[:140], company="",
            date_posted=date_from_text(strip_html(h[max(0, m.start() - 220):m.end() + 220])),
            url="https://www.berufsstart.de/" + url,
            description=strip_html(h[max(0, m.start() - 220):m.end() + 300])[:800],
        ))
    return jobs

@register("infranken", geo_scope="query")
def fetch(ctx) -> list[Job]:
    h = _get(ctx, f"https://jobs.infranken.de/suchergebnisse?Searchterm={ctx.query}")
    jobs, seen = [], set()
    # split into cards: <h2 class="job-name"> ... up to next <h2 class="job-name">
    starts = [m.start() for m in re.finditer(r'<h2 class="job-name">\s*<a href="(/jobs/\d+/[^"]*)"[^>]*>(.*?)</a>', h, re.S)]
    for idx, sm in enumerate(re.finditer(r'<h2 class="job-name">\s*<a href="(/jobs/\d+/[^"]*)"[^>]*>(.*?)</a>', h, re.S)):
        url = sm.group(1)
        title = strip_html(sm.group(2))
        if url in seen or len(title) < 6:
            continue
        seen.add(url)
        block = h[sm.start(): starts[idx + 1] if idx + 1 < len(starts) else sm.start() + 4000]
        md = re.search(r'<div class="date-company-city">\s*<span>([^<]{6,12})</span>\s*'
                       r'<a[^>]*>\s*<span[^>]*>([^<]+)</span>\s*</a>\s*<span>([^<]+)</span>', block, re.S)
        date = md.group(1).strip() if md else ""
        company = strip_html(md.group(2)) if md else ""
        city = strip_html(md.group(3)) if md else ""
        mdesc = re.search(r'<div class="job-description">(.*?)</div>', block, re.S)
        jobs.append(Job(
            source="InFranken", title=title[:140], company=company, city=city,
            date_posted=date_from_text(date),
            url="https://jobs.infranken.de" + url,
            description=strip_html(mdesc.group(1))[:3000] if mdesc else "",
        ))
    return jobs

@register("talent", geo_scope="query")
def fetch(ctx) -> list[Job]:
    h = _get(ctx, f"https://de.talent.com/jobs?k={ctx.query}&l={ctx.city}")
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
    if not urls:
        urls = ["https://de.talent.com" + u for u in re.findall(r'href="(/view\?id=\d+)"', h)]
    blocks = re.findall(r'<h2[^>]*>(.*?)</h2>(.*?)(?=<h2|\Z)', h, re.S)
    jobs, seen = [], set()
    for i, url in enumerate(urls):
        title, company, loc = "", "", ctx.city
        after = ""
        if i < len(blocks):
            title = strip_html(blocks[i][0])
            after = strip_html(blocks[i][1])[:160]
            parts = after.split("•")
            if len(parts) >= 2:
                company = parts[0].strip()[:70]
                loc = parts[1].split()[0].strip()[:40] or ctx.city
        if not title or len(title) < 8 or re.search(r"mehr anzeigen|faq|städte", title, re.I):
            continue
        if url in seen:
            continue
        seen.add(url)
        jobs.append(Job(
            source="Talent.com", title=title[:140], company=company, city=loc,
            url=url if url.startswith("http") else "https://de.talent.com" + url,
            description=after[:800],
        ))
    return jobs
