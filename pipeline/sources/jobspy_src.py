"""Indeed DE + LinkedIn guest via python-jobspy (optional dependency).
Runs in-process; if the lib is missing the runner records a SKIP with install hint."""
import re, sys
from pipeline.core import Job, SourceError, parse_date
from pipeline.sources._base import register

try:
    import pandas  # jobspy dep check
    import jobspy
    HAS_JOBSPY = True
except Exception:
    HAS_JOBSPY = False

SKIP_MSG = "python-jobspy not installed -> run: /home/z/.venv/bin/pip3 install python-jobspy"

def _is_near(ctx, text: str) -> bool:
    return bool(ctx.near_re and ctx.near_re.search(text or ""))

@register("indeed", geo_scope="country")
def fetch(ctx) -> list[Job]:
    if not HAS_JOBSPY:
        raise SourceError("auth", SKIP_MSG)
    try:
        df = jobspy.scrape_jobs(
            site_name=["indeed"], search_term=ctx.query,
            location=f"{ctx.city}, Bayern", results_wanted=60,
            hours_old=ctx.days * 24, country_indeed="germany")
    except Exception as e:
        raise SourceError("net", f"jobspy indeed failed: {type(e).__name__}: {str(e)[:140]}")
    out = []
    for row in df.to_dict(orient="records"):
        loc = row.get("location") or ""
        if not _is_near(ctx, loc):
            continue
        m = re.search(r"\b(\d{5})\b", loc)
        out.append(Job(
            source="Indeed",
            title=(row.get("title") or "").strip(),
            company=(row.get("company") or "").strip(),
            city=loc.split(",")[0].strip(),
            plz=m.group(1) if m else "",
            location_raw=loc,
            date_posted=parse_date(row.get("date_posted")),
            url=row.get("job_url") or "",
            description=(row.get("description") or "")[:6000],
            employment_raw=str(row.get("job_type") or ""),
            is_remote=bool(row.get("is_remote")),
            salary_min=row.get("min_amount"), salary_max=row.get("max_amount"),
            currency=row.get("currency") or "",
            external_id=str(row.get("id") or ""),
            notes="jobspy",
        ))
    return out

@register("linkedin", geo_scope="country")
def fetch(ctx) -> list[Job]:
    if not HAS_JOBSPY:
        raise SourceError("auth", SKIP_MSG)
    try:
        df = jobspy.scrape_jobs(
            site_name=["linkedin"], search_term=ctx.query,
            location=f"{ctx.city}, Bavaria", results_wanted=40,
            hours_old=ctx.days * 24)
    except Exception as e:
        raise SourceError("net", f"jobspy linkedin failed: {type(e).__name__}: {str(e)[:140]}")
    out = []
    for row in df.to_dict(orient="records"):
        loc = row.get("location") or ""
        if not _is_near(ctx, loc):
            continue
        m = re.search(r"\b(\d{5})\b", loc)
        out.append(Job(
            source="LinkedIn",
            title=(row.get("title") or "").strip(),
            company=(row.get("company") or "").strip(),
            city=loc.split(",")[0].strip(),
            plz=m.group(1) if m else "",
            location_raw=loc,
            date_posted=parse_date(row.get("date_posted")),
            url=row.get("job_url") or "",
            description=(row.get("description") or "")[:6000],
            is_remote=bool(row.get("is_remote")),
            salary_min=row.get("min_amount"), salary_max=row.get("max_amount"),
            currency=row.get("currency") or "",
            external_id=str(row.get("id") or ""),
            notes="jobspy-guest",
        ))
    return out
