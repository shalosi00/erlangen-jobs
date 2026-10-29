"""Bundesagentur für Arbeit Jobsuche v6 — the authoritative German source.
Public static key (jobboerse-jobsuche), angebotsart=1 (SV-pflichtig, excludes
Ausbildung server-side), pav=false (excludes agencies), exact km radius."""
import base64, time
import requests
from pipeline.core import Job, SourceError, strip_html
from pipeline.sources._base import register, check_http

H = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "asha-jobtoolkit/1.0"}
BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"

@register("ba", geo_scope="query")
def fetch(ctx) -> list[Job]:
    jobs, seen = [], set()
    for page in range(1, ctx.max_pages + 1):
        url = (f"{BASE}/pc/v6/jobs?was={ctx.query}&wo={ctx.city}&umkreis={ctx.radius}"
               f"&veroeffentlichtseit={ctx.days}&angebotsart=1&pav=false&size=100&page={page}")
        try:
            r = requests.get(url, headers=H, timeout=ctx.timeout)
        except requests.exceptions.Timeout:
            raise SourceError("timeout", f"BA v6 list timeout after {ctx.timeout}s", url=url)
        except requests.exceptions.ConnectionError as e:
            raise SourceError("net", f"BA v6 connection failed: {str(e)[:120]}", url=url)
        check_http(r, "ba", url)
        try:
            data = r.json()
        except Exception as e:
            raise SourceError("parse", f"BA v6 non-JSON body ({str(e)[:80]})", http_status=200, url=url,
                              detail=r.text[:200])
        sts = data.get("ergebnisliste")
        if sts is None:
            raise SourceError("shape", "BA v6: key 'ergebnisliste' missing — API contract changed",
                              http_status=200, url=url, detail=str(list(data.keys()))[:200])
        for s in sts:
            refnr = s.get("referenznummer")
            if not refnr or refnr in seen:
                continue
            seen.add(refnr)
            loc = (s.get("stellenlokationen") or [{}])[0].get("adresse") or {}
            j = Job(
                source="BA",
                title=(s.get("stellenangebotsTitel") or "").strip(),
                company=(s.get("firma") or "").strip(),
                city=(loc.get("ort") or "").strip(),
                plz=str(loc.get("plz") or ""),
                date_posted=(s.get("datumErsteVeroeffentlichung")
                             or (s.get("veroeffentlichungszeitraum") or {}).get("von") or "")[:10],
                url="https://www.arbeitsagentur.de/jobsuche/jobdetail/" + refnr,
                employment_raw="Vollzeit" if s.get("arbeitszeitVollzeit") else "Teilzeit" if s.get("arbeitszeitTeilzeit") else "",
                external_id=refnr,
                notes=f"{s.get('entfernung','')}km" if s.get("entfernung") else "",
            )
            jobs.append(j)
        if len(sts) < 100 or len(jobs) >= ctx.max_per_source:
            break
        time.sleep(ctx.sleep)
    if not jobs:
        return []
    if ctx.deep:
        _enrich_descriptions(jobs, ctx)
    return jobs

def _enrich_descriptions(jobs: list[Job], ctx):
    """v4 jobdetails (base64 refnr) — description powers the experience filter.
    F17: logs the X-API-BLOCKED response header (early warning if the public
    key ever gets gated) and retries once on 429."""
    ok = 0
    blocked_seen = 0
    for j in jobs:
        if len(j.description) > 0:
            continue
        url = f"{BASE}/pc/v4/jobdetails/{base64.b64encode(j.external_id.encode()).decode()}"
        for attempt in (1, 2):                     # F17: single retry on 429
            try:
                r = requests.get(url, headers=H, timeout=ctx.timeout)
                if r.status_code == 429 and attempt == 1:
                    time.sleep(2)
                    continue
                break
            except Exception:
                r = None
                break
        if r is None:
            j.notes = (j.notes + " detail:fail").strip()
        elif r.status_code == 200:
            if r.headers.get("X-API-BLOCKED"):
                blocked_seen += 1
                j.notes = (j.notes + " api-blocked-flag").strip()
            try:
                d = r.json()
                txt = strip_html(d.get("stellenbeschreibung") or "")
                j.description = txt[:6000]
                if d.get("arbeitgeberdarstellung"):
                    pass
                # ausbildung/parttime live in detail text -> recheck there is done by filters
                ok += 1
            except Exception:
                j.notes = (j.notes + " detail:parse").strip()
        elif r.status_code == 404:
            j.notes = (j.notes + " detail:404").strip()
        else:
            j.notes = (j.notes + f" detail:{r.status_code}").strip()
        time.sleep(0.25)
    if blocked_seen:
        # early warning: the BA public key may be getting gated
        print(f"BA WARNING: X-API-BLOCKED header on {blocked_seen} detail responses "
              f"— key gating possible, monitor", file=__import__("sys").stderr)
