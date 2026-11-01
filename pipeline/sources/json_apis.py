"""Keyless JSON APIs: Arbeitnow, Remotive, RemoteOK, Jobicy v2. All remote/global
boards except Arbeitnow (DE) — geo filter client-side via ctx.near_re."""
import time
import requests
from pipeline.core import Job, SourceError, strip_html, parse_date
from pipeline.sources._base import register, check_http

H = {"User-Agent": "asha-jobtoolkit/1.0"}

@register("arbeitnow", geo_scope="country")
def fetch(ctx) -> list[Job]:
    url = "https://www.arbeitnow.com/api/job-board-api"
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"Arbeitnow timeout after {ctx.timeout}s", url=url)
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"Arbeitnow connection failed: {str(e)[:110]}", url=url)
    check_http(r, "arbeitnow", url)
    data = r.json().get("data")
    if data is None:
        raise SourceError("shape", "Arbeitnow: key 'data' missing", http_status=200, url=url)
    out = []
    for j in data:
        out.append(Job(
            source="Arbeitnow",
            title=(j.get("title") or "").strip(),
            company=(j.get("company_name") or "").strip(),
            location_raw=j.get("location") or "",
            city=(j.get("location") or "").split(",")[0].strip(),
            date_posted=parse_date(j.get("created_at")),
            url=j.get("url") or "",
            description=strip_html(j.get("description") or "")[:6000],
            employment_raw=",".join(j.get("job_types") or []),
            is_remote=bool(j.get("remote")),
            external_id=j.get("slug") or "",
        ))
    return out

@register("remotive", geo_scope="country")
def fetch(ctx) -> list[Job]:
    url = "https://remotive.com/api/remote-jobs?limit=100"
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"Remotive timeout after {ctx.timeout}s", url=url)
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"Remotive connection failed: {str(e)[:110]}", url=url)
    check_http(r, "remotive", url)
    jobs = r.json().get("jobs")
    if jobs is None:
        raise SourceError("shape", "Remotive: key 'jobs' missing", http_status=200, url=url)
    out = []
    for j in jobs:
        out.append(Job(
            source="Remotive",
            title=(j.get("title") or "").strip(),
            company=(j.get("company_name") or "").strip(),
            location_raw=j.get("candidate_required_location") or "",
            date_posted=parse_date(j.get("publication_date")),
            url=j.get("url") or "",
            description=strip_html(j.get("description") or "")[:6000],
            employment_raw=j.get("job_type") or "",
            is_remote=True,
            external_id=str(j.get("id") or ""),
        ))
    return out

@register("remoteok", geo_scope="country")
def fetch(ctx) -> list[Job]:
    url = "https://remoteok.com/api"
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"RemoteOK timeout after {ctx.timeout}s", url=url)
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"RemoteOK connection failed: {str(e)[:110]}", url=url)
    check_http(r, "remoteok", url)
    data = r.json()
    if not isinstance(data, list):
        raise SourceError("shape", "RemoteOK: expected list", http_status=200, url=url)
    out = []
    for j in data:
        if not isinstance(j, dict) or "position" not in j:
            continue  # first element = legal notice
        out.append(Job(
            source="RemoteOK",
            title=(j.get("position") or "").strip(),
            company=(j.get("company") or "").strip(),
            location_raw=j.get("location") or "",
            date_posted=parse_date(j.get("epoch")),
            url=j.get("url") or "",
            description=strip_html(j.get("description") or "")[:6000],
            employment_raw=",".join(j.get("tags") or [])[:60],
            is_remote=True,
            salary_min=j.get("salary_min"), salary_max=j.get("salary_max"),
            currency="USD" if (j.get("salary_min") or j.get("salary_max")) else "",
            external_id=str(j.get("id") or ""),
        ))
    return out

@register("jobicy", geo_scope="country")
def fetch(ctx) -> list[Job]:
    url = "https://jobicy.com/api/v2/remote-jobs?count=50"
    try:
        r = requests.get(url, headers=H, timeout=ctx.timeout)
    except requests.exceptions.Timeout:
        raise SourceError("timeout", f"Jobicy timeout after {ctx.timeout}s", url=url)
    except requests.exceptions.ConnectionError as e:
        raise SourceError("net", f"Jobicy connection failed: {str(e)[:110]}", url=url)
    check_http(r, "jobicy", url)
    jobs = r.json().get("jobs")
    if jobs is None:
        raise SourceError("shape", "Jobicy: key 'jobs' missing", http_status=200, url=url)
    out = []
    for j in jobs:
        out.append(Job(
            source="Jobicy",
            title=(j.get("jobTitle") or "").strip(),
            company=(j.get("companyName") or "").strip(),
            location_raw=j.get("jobGeo") or "",
            date_posted=parse_date(j.get("pubDate")),
            url=j.get("url") or "",
            description=strip_html(j.get("jobExcerpt") or "")[:6000],
            employment_raw=j.get("jobLevel") or "",
            is_remote=True,
            external_id=str(j.get("id") or ""),
        ))
    return out
