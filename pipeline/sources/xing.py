"""XING Jobs via logged-out server-side-rendered search page.
The /ki page embeds the full GraphQL response in serverData.APOLLO_STATE.
Yellow zone: ONE request per poll, polite sleep, back off immediately on 403."""
import json, re
import requests
from pipeline.core import Job, SourceError, parse_date
from pipeline.sources._base import register, check_http

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
     "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}

def _extract_apollo_state(html: str) -> dict:
    """Find APOLLO_STATE"?:{...} and brace-match (string-aware) to its end."""
    m = re.search(r'APOLLO_STATE"?\s*[:=]\s*', html)
    if not m:
        raise SourceError("parse", "XING: APOLLO_STATE marker not found (layout changed?)",
                          http_status=200, detail=f"html size {len(html)}")
    start = html.find("{", m.end() - 1)
    if start < 0:
        raise SourceError("parse", "XING: APOLLO_STATE opening brace missing", http_status=200)
    depth, in_str, esc = 0, False, False
    raw = None
    for i in range(start, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    raw = html[start:i + 1]
                    break
    if not raw:
        raise SourceError("parse", "XING: APOLLO_STATE braces unbalanced", http_status=200)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise SourceError("parse", f"XING: APOLLO_STATE invalid JSON ({str(e)[:80]})", http_status=200,
                          detail=f"raw size {len(raw)}")

@register("xing", geo_scope="query")
def fetch(ctx) -> list[Job]:
    url = f"https://www.xing.com/jobs/search?keywords={ctx.query}&location={ctx.city}"
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout, allow_redirects=True)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"XING timeout after {ctx.timeout}s", url=url)
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"XING connection failed: {str(e)[:120]}", url=url)
    check_http(r, "xing", url)
    r.encoding = "utf-8"   # requests defaults to latin-1 for text/html w/o charset
    state = _extract_apollo_state(r.text)
    jobs = []
    for key, node in state.items():
        if not key.startswith("VisibleJob:") or not isinstance(node, dict):
            continue
        loc = node.get("location") or {}
        comp = node.get("companyInfo") or {}
        salary = node.get("salary") or {}
        app = node.get("application") or {}
        et = node.get("employmentType")
        if isinstance(et, dict):
            ref = et.get("__ref")
            employment = et.get("localizationValue") or \
                ((state.get(ref) or {}).get("localizationValue", "") if ref else "")
        else:
            employment = str(et or "")
        jobs.append(Job(
            source="XING",
            title=(node.get("title") or "").strip(),
            company=(comp.get("companyNameOverride") or "").strip(),
            city=(loc.get("city") or "").strip(),
            date_posted=parse_date(node.get("refreshedAt") or node.get("activeUntil")),
            url=(lambda u: u if u.startswith("http") else "https://www.xing.com" + u)(
                node.get("url") or node.get("slug") or ""),
            employment_raw=employment,
            salary_min=salary.get("minimum"), salary_max=salary.get("maximum"),
            currency=salary.get("currency") or "",
            external_id=node.get("globalId") or key,
            notes="one-click" if app.get("__typename") == "XingApplication" else "",
        ))
    return jobs
