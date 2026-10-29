"""RSS sources: We Work Remotely (DevOps/Sysadmin + Programming), Himalayas.
Remote/global — geo + keyword filter client-side. Parse via stdlib xml.etree."""
import re, time
import xml.etree.ElementTree as ET
import requests
from pipeline.core import Job, SourceError, strip_html
from pipeline.sources._base import register, check_http

H = {"User-Agent": "asha-jobtoolkit/1.0"}

def _parse_rss(url: str, ctx) -> list:
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"RSS timeout after {ctx.timeout}s: {url}", url=url)
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"RSS connection failed: {str(e)[:110]}", url=url)
    check_http(r, "rss", url)
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        raise SourceError("parse", f"RSS XML invalid: {e}", http_status=200, url=url,
                          detail=r.text[:200])
    items = root.findall(".//item")
    out = []
    for it in items:
        get = lambda tag: (it.findtext(tag) or "").strip()
        out.append(dict(
            title=get("title"), company="", url=get("link"),
            date=(get("pubDate") or "")[:25],
            desc=strip_html(get("description"))[:4000],
            cats=",".join(e.text or "" for e in it.findall("category")),
        ))
    return out

def _pubdate_to_iso(s: str) -> str:
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return ""

@register("wwr", geo_scope="country")
def fetch(ctx) -> list[Job]:
    feeds = ["https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
             "https://weworkremotely.com/categories/remote-programming-jobs.rss"]
    out = []
    for f in feeds:
        for it in _parse_rss(f, ctx):
            comp_title = it["title"] or ""
            # WWR title format: "Company: Job Title"
            company, _, title = comp_title.partition(":")
            out.append(Job(
                source="WWR", title=title.strip()[:140] or comp_title[:140],
                company=company.strip(), date_posted=_pubdate_to_iso(it["date"]),
                url=it["url"], description=it["desc"][:4000],
                employment_raw=it["cats"][:60], is_remote=True,
            ))
        time.sleep(ctx.sleep)
    return out

@register("himalayas", geo_scope="country")
def fetch(ctx) -> list[Job]:
    out = []
    for it in _parse_rss("https://himalayas.app/jobs/rss", ctx):
        out.append(Job(
            source="Himalayas", title=it["title"][:140], company=it["company"],
            date_posted=_pubdate_to_iso(it["date"]), url=it["url"],
            description=it["desc"][:4000], employment_raw=it["cats"][:60], is_remote=True,
        ))
    return out
