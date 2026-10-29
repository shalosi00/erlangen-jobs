"""Key-gated APIs (free registration). Missing key -> SKIP with a clear hint.
  adzuna    ADZUNA_APP_ID + ADZUNA_APP_KEY   developer.adzuna.com
  jooble    JOOBLE_API_KEY                   jooble.org/api
  careerjet CAREERJET_AFFID                  careerjet.com/partners/api
  whatjobs  WHATJOBS_PUBLISHER_KEY           whatjobs affiliate program"""
import time
import requests
from pipeline.core import Job, SourceError, strip_html
from pipeline.sources._base import register, check_http

H = {"User-Agent": "asha-jobtoolkit/1.0"}

def _missing(key: str, hint: str):
    raise SourceError("auth", f"missing API key: set {key} ({hint})")

@register("adzuna", geo_scope="query")
def fetch(ctx) -> list[Job]:
    app_id, app_key = ctx.keys.get("ADZUNA_APP_ID"), ctx.keys.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        _missing("ADZUNA_APP_ID + ADZUNA_APP_KEY", "free: developer.adzuna.com")
    url = (f"https://api.adzuna.com/v1/api/jobs/de/search/1"
           f"?app_id={app_id}&app_key={app_key}&what={ctx.query}&where={ctx.city}"
           f"&max_days_old={ctx.days}&results_per_page=50")
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"Adzuna timeout after {ctx.timeout}s", url="api.adzuna.com")
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"Adzuna connection failed: {str(e)[:110]}", url="api.adzuna.com")
    check_http(r, "adzuna", "api.adzuna.com/v1/api/jobs/de/search")
    out = []
    for j in r.json().get("results", []):
        out.append(Job(
            source="Adzuna",
            title=(j.get("title") or "").strip(),
            company=((j.get("company") or {}).get("display_name") or "").strip(),
            city=((j.get("location") or {}).get("display_name") or "").strip(),
            location_raw=((j.get("location") or {}).get("display_name") or ""),
            date_posted=(j.get("created") or "")[:10],
            url=j.get("redirect_url") or "",
            description=strip_html(j.get("description") or "")[:6000],
            salary_min=j.get("salary_min"), salary_max=j.get("salary_max"),
            is_remote=bool(j.get("latitude") is None and "remote" in (j.get("description") or "").lower()[:2000]),
            external_id=str(j.get("id") or ""),
        ))
    return out

@register("jooble", geo_scope="query")
def fetch(ctx) -> list[Job]:
    key = ctx.keys.get("JOOBLE_API_KEY")
    if not key:
        _missing("JOOBLE_API_KEY", "free: jooble.org/api")
    url = f"https://jooble.org/api/{key}"
    body = {"keywords": ctx.query, "location": ctx.city, "page": 1}
    try:
        r = requests.post(url, json=body, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"Jooble timeout after {ctx.timeout}s", url="jooble.org/api")
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"Jooble connection failed: {str(e)[:110]}", url="jooble.org/api")
    if r.status_code in (403, 404):
        raise SourceError("auth", f"Jooble rejected key (HTTP {r.status_code}) — check JOOBLE_API_KEY",
                          r.status_code, url, r.text[:150])
    check_http(r, "jooble", "jooble.org/api")
    out = []
    for j in r.json().get("jobs", []):
        out.append(Job(
            source="Jooble",
            title=(j.get("title") or "").strip(),
            company=(j.get("company") or "").strip(),
            location_raw=j.get("location") or "",
            city=(j.get("location") or "").split(",")[0].strip(),
            date_posted=(j.get("updated") or "")[:10],
            url=j.get("link") or "",
            description=strip_html(j.get("snippet") or "")[:6000],
            salary_min=j.get("salary_min"), salary_max=j.get("salary_max"),
            external_id=str(j.get("id") or ""),
        ))
    return out

@register("careerjet", geo_scope="query")
def fetch(ctx) -> list[Job]:
    affid = ctx.keys.get("CAREERJET_AFFID")
    if not affid:
        _missing("CAREERJET_AFFID", "free: careerjet.com/partners/api")
    url = ("https://public.api.careerjet.net/v4/search?"
           f"keywords={ctx.query}&location={ctx.city}&locale_code=de_DE&affid={affid}")
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", "Careerjet timeout", url="public.api.careerjet.net")
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"Careerjet unreachable from this network (known DC block): {str(e)[:90]}",
                          url="public.api.careerjet.net")
    check_http(r, "careerjet", "public.api.careerjet.net/v4/search")
    data = r.json()
    if data.get("type") == "ERROR":
        raise SourceError("auth", f"Careerjet error: {data.get('error', '')[:120]}", url=url)
    out = []
    for j in data.get("jobs", []):
        out.append(Job(
            source="Careerjet",
            title=(j.get("title") or "").strip(),
            company=(j.get("company") or "").strip(),
            location_raw=j.get("locations") or "",
            city=(j.get("locations") or "").split(",")[0].strip(),
            date_posted=(j.get("date") or "")[:10],
            url=j.get("url") or "",
            description=strip_html(j.get("description") or "")[:6000],
            salary_min=j.get("salary_min"), salary_max=j.get("salary_max"),
            currency=j.get("salary_currency") or "",
            external_id=j.get("jobid") or "",
        ))
    return out

@register("whatjobs", geo_scope="query")
def fetch(ctx) -> list[Job]:
    key = ctx.keys.get("WHATJOBS_PUBLISHER_KEY")
    if not key:
        _missing("WHATJOBS_PUBLISHER_KEY", "whatjobs affiliate/publisher program")
    url = (f"https://api.whatjobs.com/api/v1/jobs.json?publisher={key}"
           f"&user_ip=127.0.0.1&user_agent=asha&keyword={ctx.query}&location={ctx.city}")
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", "WhatJobs timeout", url="api.whatjobs.com")
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"WhatJobs connection failed: {str(e)[:110]}", url="api.whatjobs.com")
    if r.status_code in (401, 403, 410):
        raise SourceError("auth", f"WhatJobs rejected credentials (HTTP {r.status_code})",
                          r.status_code, url, r.text[:150])
    check_http(r, "whatjobs", "api.whatjobs.com/api/v1/jobs.json")
    out = []
    for j in (r.json().get("jobs") or {}).get("data", []) if isinstance((r.json() or {}).get("jobs"), dict) else []:
        out.append(Job(
            source="WhatJobs", title=(j.get("title") or "").strip(),
            company=(j.get("companyName") or "").strip(),
            location_raw=j.get("location") or "", city=(j.get("location") or "").split(",")[0].strip(),
            date_posted=(j.get("date") or "")[:10], url=j.get("jobUrl") or "",
            description=strip_html(j.get("description") or "")[:6000],
        ))
    return out
