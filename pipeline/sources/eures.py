"""EURES (EU portal) — POST search with full text in the response.
Mirrors BA postings + EU cross-border. Working host verified: europa.eu/eures/api."""
import time
import requests
from pipeline.core import Job, SourceError, strip_html, parse_date
from pipeline.sources._base import register, check_http

URL = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"
H = {"User-Agent": "asha-jobtoolkit/1.0", "Content-Type": "application/json"}

@register("eures", geo_scope="country")
def fetch(ctx) -> list[Job]:
    jobs = []
    for page in range(1, ctx.max_pages + 1):
        body = {
            "resultsPerPage": 50, "page": page, "sortSearch": "BEST_MATCH",
            "keywords": [{"keyword": ctx.query, "specificSearchCode": "EVERYWHERE"}],
            "publicationPeriod": None, "occupationUris": [], "skillUris": [],
            "requiredExperienceCodes": [], "positionScheduleCodes": [], "sectorCodes": [],
            "educationAndQualificationLevelCodes": [], "positionOfferingCodes": [],
            "locationCodes": [], "euresFlagCodes": [], "otherBenefitsCodes": [],
            "requiredLanguages": [],
        }
        try:
            r = requests.post(URL, json=body, headers=H, timeout=ctx.timeout)
        except requests.exceptions.Timeout:
            raise SourceError("timeout", f"EURES timeout after {ctx.timeout}s", url=URL)
        except requests.exceptions.ConnectionError as e:
            raise SourceError("net", f"EURES connection failed: {str(e)[:120]}", url=URL)
        check_http(r, "eures", URL)
        try:
            data = r.json()
        except Exception as e:
            raise SourceError("parse", f"EURES non-JSON ({str(e)[:80]})", http_status=200, url=URL)
        jvs = data.get("jvs")
        if jvs is None:
            raise SourceError("shape", "EURES: key 'jvs' missing", http_status=200, url=URL,
                              detail=str(list(data.keys()))[:200])
        for v in jvs:
            loc = v.get("locationMap") or {}
            loc_str = ", ".join(str(x) for x in [loc.get("city"), loc.get("country", {}).get("label", "") if isinstance(loc.get("country"), dict) else loc.get("country")] if x)
            emp = v.get("employer") or {}
            jobs.append(Job(
                source="EURES",
                title=(v.get("title") or "").strip(),
                company=(emp.get("name") or emp.get("displayName") or "").strip(),
                city=(loc.get("city") or "").strip(),
                location_raw=loc_str,
                date_posted=parse_date(v.get("creationDate")),
                description=strip_html(v.get("description") or "")[:6000],
                employment_raw=",".join(v.get("positionScheduleCodes") or []),
                external_id=str(v.get("id") or ""),
                url=f"https://europa.eu/eures/portal/jv-se/jv-details/{v.get('id') or ''}",
                notes=f"euresFlag={v.get('euresFlag')}" if v.get("euresFlag") is not None else "",
            ))
        if len(jvs) < 50 or len(jobs) >= ctx.max_per_source:
            break
        time.sleep(ctx.sleep)
    return jobs
