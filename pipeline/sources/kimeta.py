"""Kimeta.de — one of Germany's largest job meta-search engines (57 FISI postings in
Erlangen at probe time). Server-rendered React cards, but the datacenter IP is
nginx-503-blocked, so fetching goes through the validated proxy pool
(pipeline/proxy_pool.py). Card recipe (verified on live sample, see
data/proxies/kimeta_sample.html):

  <a href="/display-job/{company-slug}/{title-slug}-N.html">
    <div class="jsx-... cn">COMPANY</div>
    <h3 class="jsx-... jt">TITLE (search term wrapped in <b>)</h3>
    ... <svg ...#pin-svg></svg><span>Nuremberg</span>
  </a>
  <div class="jsx-... offer-body"> ... <div class="jsx-... summary">TEASER</div>

Kimeta shows no posting dates on SERP cards -> convention: date_posted = first-seen
(today, live-SERP listing is verifiably active), noted per row in `notes`.
Apprenticeship-heavy results are cut by the pipeline's hard filters (AUSBILDUNG_RX).
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import requests

from pipeline.core import Job, SourceError, date_from_text, strip_html
from pipeline.sources._base import register, check_http
from pipeline.proxy_pool import pick, mark_dead

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
      "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}

MAX_PROXY_TRIES = 6


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _fetch_serp(ctx, url: str) -> str:
    """Fetch the SERP through rotating validated proxies; pinpoint failures."""
    last_err = None
    for attempt in range(MAX_PROXY_TRIES):
        entry = pick("kimeta")
        if entry is None:
            raise SourceError("waf", "no alive kimeta-validated proxy in pool — run: "
                             "python -m pipeline.proxy_pool refresh")
        try:
            r = requests.get(url, headers=UA, proxies=entry["proxies"], timeout=ctx.timeout)
            if r.status_code == 200 and len(r.text) > 50000:
                return r.text
            # reachable but not a SERP -> WAF-ish, try next proxy
            check_http(r, "kimeta", url)
            last_err = SourceError("parse", f"kimeta 200 but page too small ({len(r.text)}B) "
                                   f"via {entry['host']}", 200, url, r.text[:160])
        except requests.exceptions.Timeout:
            last_err = SourceError("timeout", f"proxy {entry['host']}:{entry['port']} timed out "
                                   f"after {ctx.timeout}s", url=url)
            mark_dead(entry)
        except requests.exceptions.ProxyError as e:
            last_err = SourceError("net", f"proxy dead: {entry['protocol']}://{entry['host']}:"
                                   f"{entry['port']} — {str(e)[:80]}", url=url)
            mark_dead(entry)
        except requests.exceptions.ConnectionError as e:
            last_err = SourceError("net", f"connection failed via proxy {entry['host']} — "
                                   f"{str(e)[:80]}", url=url)
            mark_dead(entry)
        time.sleep(0.3)
    raise last_err or SourceError("net", "all proxy attempts failed", url=url)


# card anchor: href="/display-job/..."  (redirect hop to the original board)
CARD_RX = re.compile(
    r'<a[^>]+href="(/display-job/[^"]+)"[^>]*>(.*?)</a>', re.S)
COMPANY_RX = re.compile(r'\b cn">([^<]{2,90})<')
TITLE_RX = re.compile(r'\b jt">(.*?)</h3>', re.S)
CITY_RX = re.compile(r'pin-svg[^>]*>.*?<span[^>]*>([^<]{2,60})</span>', re.S)


@register("kimeta", geo_scope="query")
def fetch(ctx) -> list[Job]:
    url = f"https://www.kimeta.de/{_slug(ctx.query)}-jobs-{_slug(ctx.city)}"
    h = _fetch_serp(ctx, url)
    today = datetime.now(timezone.utc).date().isoformat()
    jobs, seen = [], set()
    for m in CARD_RX.finditer(h):
        href, block = m.group(1), m.group(2)
        if href in seen:
            continue
        mt, mc, mcity = TITLE_RX.search(block), COMPANY_RX.search(block), CITY_RX.search(block)
        title = strip_html(mt.group(1)) if mt else ""
        if len(title) < 6:
            continue
        seen.add(href)
        # teaser lives after the anchor, inside offer-body summary div
        tail = h[m.end(): m.end() + 1200]
        ms = re.search(r'\b summary">([^<]{20,900})', tail)
        teaser = strip_html(ms.group(1)) if ms else ""
        city = strip_html(mcity.group(1)) if mcity else ctx.city
        jobs.append(Job(
            source="Kimeta",
            title=title[:140],
            company=strip_html(mc.group(1)) if mc else "",
            city=city,
            location_raw=city,
            date_posted=date_from_text(teaser[:200]) or today,
            url="https://www.kimeta.de" + href,
            description=teaser[:800],
            notes="kimeta live-SERP; date=first-seen (cards carry no posting date)",
        ))
        if len(jobs) >= ctx.max_per_source:
            break
    return jobs
