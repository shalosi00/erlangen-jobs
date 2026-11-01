"""Stellenanzeigen.de — one of Germany's largest commercial boards. Fully unlocked
via its own JSON search API (robots: /api/ is allowed except /api/tracking/*).

Recipe (reverse-engineered via headless-browser network capture, Task 11):
  1. GET /api/suggest/?value={city}          -> location id (M-DE-2076 = Erlangen)
     (suggest 400s from plain clients sometimes; hard-coded fallback below)
  2. GET /api/jobs/?backfillTypes=Internal&backfillTypes=Paid&backfillTypes=Free
         &includeVariants=true&limit=50&locationIds={loc}&onlyTopJobs=false
         &perimeterRadius={radius}&setRelevanceMarker=true&sort=Datum
         &fulltext={query}&skip={page*50}
     -> jobAdSearchResultModel.jobAds[] (distance km, 3500 = no geo/national)
Requires curl_cffi (TLS fingerprint passes the WAF; plain requests gets 403).
"""
from __future__ import annotations

from datetime import datetime, timezone

from pipeline.core import Job, SourceError, parse_date
from pipeline.sources._base import register

try:
    from curl_cffi import requests as cr
except ImportError:
    cr = None

BASE = "https://www.stellenanzeigen.de"
HEADERS = {"Accept": "application/json",
           "Accept-Language": "de-DE,de;q=0.9",
           "Referer": f"{BASE}/suche/"}
# location ids seen live (city -> id); suggest endpoint is flaky from scripts
LOCATION_IDS = {"erlangen": "M-DE-2076", "nürnberg": "M-DE-2214", "nuernberg": "M-DE-2214"}
NATIONAL_DISTANCE = 3500.0  # sentinel the API returns when a job has no geo


def _cffi_get(ctx, url: str):
    if cr is None:
        raise SourceError("auth", "curl_cffi not installed -> run: "
                          "/home/z/.venv/bin/python -m pip install curl_cffi")
    try:
        r = cr.get(url, impersonate="chrome124", timeout=ctx.timeout, headers=HEADERS)
    except Exception as e:
        raise SourceError("net", f"curl_cffi request failed: {type(e).__name__}: {str(e)[:90]}", url=url)
    if r.status_code != 200:
        raise SourceError("waf" if r.status_code in (403, 429) else "http",
                          f"HTTP {r.status_code} from {url}", r.status_code, url, r.text[:160])
    return r


def _resolve_location(ctx) -> str:
    city = (ctx.city or "").strip()
    key = city.lower()
    if key in LOCATION_IDS:
        return LOCATION_IDS[key]
    try:
        r = cr.get(f"{BASE}/api/suggest/?value={city}", impersonate="chrome124",
                   timeout=10, headers=HEADERS)
        for hit in r.json().get("locations", []) or []:
            lid = hit.get("idLocation") or hit.get("id")
            if lid and str(lid).startswith(("M-DE", "P-DE")):
                LOCATION_IDS[key] = lid
                return lid
    except Exception:
        pass
    raise SourceError("shape", f"unknown location id for '{ctx.city}' — extend "
                      f"LOCATION_IDS in pipeline/sources/stellenanzeigen.py "
                      f"(live via browser: /api/suggest/?value={city})", url=f"{BASE}/api/suggest/")


@register("stellenanzeigen", geo_scope="query")
def fetch(ctx) -> list[Job]:
    loc = _resolve_location(ctx)
    url = (f"{BASE}/api/jobs/?backfillTypes=Internal&backfillTypes=Paid&backfillTypes=Free"
           f"&includeVariants=true&limit=50&locationIds={loc}&onlyTopJobs=false"
           f"&perimeterRadius={min(ctx.radius, 150)}&setRelevanceMarker=true&sort=Datum"
           f"&fulltext={ctx.query}")
    r = _cffi_get(ctx, url)
    try:
        model = r.json()["jobAdSearchResultModel"]
    except Exception as e:
        raise SourceError("shape", f"unexpected API body: {e}", 200, url, r.text[:160])
    jobs = []
    for a in model.get("jobAds", []):
        ja = a.get("jobAd") or {}
        title = (ja.get("positionTitle") or "").strip()
        if len(title) < 6:
            continue
        dist = a.get("distance") or 0
        if dist >= NATIONAL_DISTANCE:      # no geo -> national ad, out of scope
            continue
        regs = (ja.get("regions") or [{}])[0] if isinstance(ja.get("regions"), list) else {}
        city = ja.get("region") or regs.get("region") or ""
        is_remote = city.lower() == "home office"
        jobs.append(Job(
            source="Stellenanzeigen.de",
            title=title[:140],
            company=(ja.get("companyName") or "").strip()[:90],
            city="" if is_remote else city,
            plz=str(regs.get("zip") or ""),
            location_raw=f"{city} ({dist:.0f}km)" if not is_remote else "Home Office",
            date_posted=parse_date(ja.get("originalStartDate") or ja.get("startDate")),
            url=ja.get("link") or "",
            description=(ja.get("positionAddition") or "")[:800],
            salary_min=float(ja["salaryMin"]) if ja.get("salaryMin") else None,
            salary_max=float(ja["salaryMax"]) if ja.get("salaryMax") else None,
            currency=ja.get("salaryCurrency") or "",
            external_id=str(ja.get("id") or ""),
            is_remote=is_remote,
            notes=f"distance={dist:.1f}km" + ("; relevant" if a.get("isRelevant") else ""),
        ))
        if len(jobs) >= ctx.max_per_source:
            break
    return jobs
