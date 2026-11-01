#!/usr/bin/env python3
"""Task 24: per-job enrichment for the FISI job corpus.

For EVERY posting answers:
  WHERE  — source portal (from DB `source`, always carried through)
  WHEN   — posting date with evidence method; if no date extractable,
           the exact time-period filter the source search used
           (registry mirrors the real pipeline parameters)
  WHO    — original employer (direct vs mediator/Zeitarbeit, with evidence)
  CONTACT— recruiter phone, recruiter email, employer website,
           original posting URL (not the portal's wrapper URL)

Fetch stack (proven in Task 22):
  BA/BA+XING -> arbeitsagentur detail API (JSON: veroeffentlichtAm, kontakt)
  Kimeta     -> validated proxy pool rotation (TLS fingerprint workaround)
  others     -> direct first, then pool ("any")

Outputs (data/enriched/):
  jobs_enriched_<ts>.json / .csv          — all rows, full evidence
  direct_employers_<ts>.csv               — direct employers w/ contacts only
Prints a compact summary (also consumed by daily_summary.py).
"""
from __future__ import annotations

import base64
import csv
import json
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.proxy_pool import pick, mark_dead  # noqa: E402

DB = ROOT / "data" / "jobs_history.db"
OUT_DIR = ROOT / "data" / "enriched"
T22_CACHE = ROOT / "download" / "verified" / "2026-10-26" / "task22_linkcheck.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.6"}
TIMEOUT = 25
TODAY = datetime.now(timezone.utc).date()

# ------------------------------------------------------------------ registry
# WHAT TIME PERIOD WAS USED AS FILTER — mirrors pipeline/sources/*.py params
TIME_FILTERS = {
    "BA":       "BA-API param veroeffentlichtseit=14 (Veröffentlichung der letzten 14 Tage)",
    "BA+XING":  "BA-API param veroeffentlichtseit=14 (via BA; cross-listed on XING)",
    "Indeed":   "jobspy hours_old=336 (14 Tage Fenster)",
    "LinkedIn": "jobspy hours_old=336 (14 Tage Fenster)",
    "XING":     "jobspy hours_old=336 (14 Tage Fenster)",
    "EURES":    "EURES param max_days_old=14",
    "Kimeta":   "live SERP, kein Quellfilter — Konvention: date_posted = first_seen (Cards tragen kein Datum)",
    "Talent.com": "kein Quellfilter; Pipeline-Cutoff verwirft parsebare Daten > 14 Tage",
    "Get-in-IT":  "kein Quellfilter; Pipeline-Cutoff verwirft parsebare Daten > 14 Tage",
    "InFranken":  "kein Quellfilter; Pipeline-Cutoff verwirft parsebare Daten > 14 Tage",
    "Talent.com+XING": "kein Quellfilter (Talent); Pipeline-Cutoff verwirft parsebare Daten > 14 Tage",
}
DEFAULT_TF = "Pipeline-Cutoff: parsebare date_posted > 14 Tage verworfen (Slug '-14d')"

PORTAL_DOMAINS = (
    "kimeta.de", "arbeitsagentur.de", "talent.com", "get-in-it.de",
    "indeed.com", "linkedin.com", "infranken.de", "xing.com",
    "eures.europa.eu", "stepstone.de", "jobvector.de", "connecticum.de",
    "berufsstart.de", "yourfirm.de", "jobware.de", "stellenanzeigen.de",
    "germantechjobs.de", "absolventa.de", "jobs.de", "meinestadt.de",
    "kimeta.com", "hokify.de", "jobrapido.com", "neuvoo", "adzuna",
)

# ------------------------------------------------------------- mediator cues
AGENCY_MARKERS = [
    "zeitarbeit", "zeitarbeitsfirma", "arbeitsvermittlung", "personalvermittlung",
    "personalvermittler", "personalberatung", "personaldienstleistung",
    "personaldienstleister", "arbeitnehmerüberlassung", "arbeitnehmerueberlassung",
    "leiharbeit", "staffing", "recruiting-agentur", "personalagentur",
    "temporärbüro", "personalservice", "personaldienstleistungen",
    "personalberater", "vermittlung und personalberatung",
]
AGENCY_BRANDS = [
    "randstad", "adecco", "hays", "manpower", "trenkwalder", "dis ag",
    "auviva", "hofmann personal", "amadeus fire", "atris personal",
    "avance personal", "epunkt", "solcom", "teampoint", "personal total",
    "hays recruiting", "wtd personal", "orizon gmbh", "tmg personal",
    "zeitdienst", "expertum", "synergie", "unique personal",
    "personal 2000", "profil personal", "persy gmbh",
]
DIRECT_CUES = [
    "direkt beim arbeitgeber", "unser standort", "bei uns", "wir sind",
    "unser unternehmen", "unser kunde sucht", "eigene jobsuche",
]


# precompiled word-boundary patterns — substring matching gave false hits
# (e.g. 'atris' inside unrelated words)
_AGENCY_RE = re.compile(
    "|".join(r"\b" + re.escape(t) + r"\b" for t in AGENCY_MARKERS), re.I)
_BRAND_RE = re.compile(
    "|".join(r"\b" + re.escape(t) + r"\b" for t in AGENCY_BRANDS), re.I)


class DeadLink(RuntimeError):
    def __init__(self, status, via):
        super().__init__(f"dead link HTTP {status} ({via})")
        self.status = status


# ------------------------------------------------------------------- fetch
def _get(url: str, *, proxies: dict | None = None, timeout: int = TIMEOUT):
    return requests.get(url, headers=HDRS, proxies=proxies, timeout=timeout,
                        allow_redirects=True)


def _via_proxy(url: str, target: str) -> str:
    last, last_status = None, 0
    for _ in range(4):
        entry = pick(target)
        if entry is None:
            break
        try:
            r = _get(url, proxies=entry["proxies"])
            last_status = r.status_code
            if r.status_code == 200 and len(r.text) > 800:
                return r.text
            if r.status_code in (404, 410):
                raise DeadLink(r.status_code, "proxy")
            last = f"HTTP {r.status_code} via {entry['host']}"
        except DeadLink:
            raise
        except Exception as e:
            last = f"{type(e).__name__} via {entry.get('host')}"
            mark_dead(entry)
        time.sleep(0.4)
    if last_status in (404, 410):
        raise DeadLink(last_status, "proxy")
    raise RuntimeError(last or "no proxy left in pool")


def soup_text(html: str, limit: int = 30000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript",
                     "svg", "form", "iframe"]):
        tag.decompose()
    txt = soup.get_text("\n")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{2,}", "\n", txt)
    return txt[:limit]


def fetch_ba(row: dict) -> tuple[dict | None, str]:
    """BA detail API returns the FULL JSON — goldmine for WHEN+WHO+CONTACT."""
    api_json = None
    m = re.search(r"/jobdetail/([0-9A-Za-z\-]+)", row["url"])
    if m:
        b64 = base64.urlsafe_b64encode(m.group(1).encode()).decode()
        try:
            r = _get("https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/"
                     f"pc/v4/jobdetails/{b64}",
                     headers={"X-API-Key": "jobboerse-jobsuche",
                              "User-Agent": UA}, timeout=20)
            if r.ok:
                api_json = r.json()
            elif r.status_code in (404, 410):
                raise DeadLink(r.status_code, "BA API")
        except DeadLink:
            raise
        except Exception:
            api_json = None
    html = ""
    if api_json is None:
        try:
            r = _get(row["url"])
            if r.ok:
                html = r.text
            elif r.status_code in (404, 410):
                raise DeadLink(r.status_code, "BA page")
        except DeadLink:
            raise
        except Exception:
            pass
    desc = (api_json or {}).get("stellenangebotsBeschreibung") or ""
    if not html and len(desc) < 60 and api_json is None:
        raise RuntimeError("BA: neither API nor page yielded content")
    return api_json, desc if desc else soup_text(html)


def fetch_kimeta(row: dict) -> tuple[None, str]:
    return None, soup_text(_via_proxy(row["url"], "kimeta"))


def fetch_generic(row: dict) -> tuple[None, str | dict]:
    """direct first (raw html kept for JSON-LD), then proxy fallback."""
    try:
        r = _get(row["url"])
        if r.ok and len(r.text) > 800 and "captcha" not in r.text[:3000].lower():
            return None, r.text  # RAW html
        if r.status_code in (404, 410):
            raise DeadLink(r.status_code, "direct")
    except DeadLink:
        raise
    except Exception:
        pass
    return None, _via_proxy(row["url"], "any")  # RAW html via proxy


def fetch_row(row: dict) -> tuple[dict | None, str, str, str]:
    """returns (api_json, raw_or_text, fetch_note, fetched_via)"""
    src = row.get("source", "")
    try:
        if src in ("BA", "BA+XING"):
            api_json, content = fetch_ba(row)
            note = "ba_api" if api_json else "ba_page"
            return api_json, content, note, "direct"
        if src == "Kimeta":
            _, content = fetch_kimeta(row)
            return None, content, "ok", "proxy-pool"
        _, content = fetch_generic(row)
        return None, content, "ok", "direct-or-proxy"
    except DeadLink as e:
        return None, "", f"dead:{e.status}", "-"
    except Exception as e:
        return None, "", f"fetch_failed:{type(e).__name__}:{str(e)[:90]}", "-"


# ---------------------------------------------------------------- extraction
def extract_jsonld(raw: str) -> dict | None:
    """First JSON-LD block of type JobPosting."""
    if not raw or raw.lstrip()[:1] not in ("{", "<", "\n"):
        if not raw:
            return None
    if "<" not in raw[:200] and "jobPosting" not in raw[:20000]:
        return None
    try:
        soup = BeautifulSoup(raw, "html.parser")
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s.string or "")
            except Exception:
                continue
            blocks = data if isinstance(data, list) else [data]
            for b in blocks:
                if isinstance(b, dict):
                    if b.get("@type") in ("JobPosting", ["JobPosting"]):
                        return b
                    g = b.get("@graph") or []
                    if isinstance(g, list):
                        for x in g:
                            if isinstance(x, dict) and \
                               x.get("@type") in ("JobPosting", ["JobPosting"]):
                                return x
    except Exception:
        return None
    return None


DATE_META_KEYS = [
    ("meta", {"property": "article:published_time"}),
    ("meta", {"name": "date"}),
    ("meta", {"name": "datePublished"}),
    ("meta", {"itemprop": "datePosted"}),
    ("meta", {"property": "og:article:published_time"}),
]


def _iso(datestr: str) -> str | None:
    datestr = (datestr or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", datestr)
    if m:
        return m.group(1)
    m = re.match(r"([0-3]?\d)\.\s?([0-1]?\d)\.(\d{4})", datestr)
    if m:
        d_, mo, y = m.groups()
        try:
            return datetime(int(y), int(mo), int(d_)).date().isoformat()
        except ValueError:
            return None
    m = re.match(r"([0-3]?\d)\.\s?([A-Za-zäöü]+)\s+(\d{4})", datestr)
    if m:
        months = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
                  "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
                  "oktober": 10, "november": 11, "dezember": 12,
                  "january": 1, "february": 2, "march": 3, "april": 4,
                  "may": 5, "june": 6, "july": 7, "august": 8,
                  "october": 10, "december": 12}
        d_, mn, y = m.groups()
        mo = months.get(mn.lower())
        if mo:
            try:
                return datetime(int(y), mo, int(d_)).date().isoformat()
            except ValueError:
                return None
    return None


def rel_to_iso(text: str) -> tuple[str | None, str]:
    """German relative dates -> ISO. Returns (iso, note)."""
    t = text[:2500].lower()
    if re.search(r"\bheute\b", t):
        return TODAY.isoformat(), "text: 'heute'"
    if re.search(r"\bgestern\b", t):
        return (TODAY - timedelta(days=1)).isoformat(), "text: 'gestern'"
    m = re.search(r"vor\s+(\d+)\s+(stunden?|tagen?|wochen?)", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = n if unit.startswith("tag") else (n * 7 if unit.startswith("woch") else 0)
        if days <= 60:
            note = f"text: 'vor {n} {unit}'"
            return (TODAY - timedelta(days=days)).isoformat(), note
    return None, ""


def extract_date(raw: str, text: str, jsonld: dict | None,
                 ba: dict | None) -> tuple[str, str]:
    """Multi-tier posting-date extraction. Returns (iso_date, evidence)."""
    def clamp(iso: str, ev: str) -> tuple[str, str]:
        # reject absurd ages (copyright dates, 'seit 2020', milestones)
        try:
            age = (TODAY - datetime.fromisoformat(iso).date()).days
        except (ValueError, TypeError):
            return "", ""
        if age < 0:
            return "", f"rejected(future): {ev}"
        if age > 120:
            return "", f"rejected(too old {age}d): {ev}"
        return iso, ev

    if ba:
        for k in ("veroeffentlichtAm", "veroeffentlichungsdatum",
                  "publikationsdatum"):
            v = ba.get(k)
            if v:
                iso = _iso(str(v))
                if iso:
                    iso, ev = clamp(iso, f"ba_api.{k}")
                    if iso:
                        return iso, ev
    if jsonld:
        v = jsonld.get("datePosted")
        if v:
            iso = _iso(str(v))
            if iso:
                iso, ev = clamp(iso, "jsonld.datePosted")
                if iso:
                    return iso, ev
    if raw and raw.lstrip().startswith("<"):
        try:
            soup = BeautifulSoup(raw[:200000], "html.parser")
            for tag_name, attrs in DATE_META_KEYS:
                el = soup.find(tag_name, attrs=attrs)
                if el and el.get("content"):
                    iso = _iso(el["content"])
                    if iso:
                        iso, ev = clamp(iso, f"meta[{attrs.get('property') or attrs.get('name')}]")
                        if iso:
                            return iso, ev
            t = soup.find("time")
            if t and (t.get("datetime") or t.get("title")):
                iso = _iso(t.get("datetime") or t.get("title"))
                if iso:
                    iso, ev = clamp(iso, "time[datetime]")
                    if iso:
                        return iso, ev
        except Exception:
            pass
    m = re.search(r"(?:veröffentlicht|veroeffentlicht|publiziert)\s*"
                  r"(?:am|seit|:)\s*:?\s*([0-3]?\d\.[0-1]?\d\.\d{4})", text, re.I)
    if m:
        iso = _iso(m.group(1))
        if iso:
            iso, ev = clamp(iso, f"text: 'Veröffentlicht am {m.group(1)}'")
            if iso:
                return iso, ev
    m = re.search(r"\b(?:am|vom)\s+([0-3]?\d\.\s?[0-1]?\d\.\s?\d{4})\b", text[:3000])
    if m:
        iso = _iso(m.group(1))
        if iso and 0 <= (TODAY - datetime.fromisoformat(iso).date()).days <= 90:
            return iso, f"text: 'am {m.group(1)}'"
    iso, note = rel_to_iso(text)
    if iso:
        return iso, note
    return "", ""


PHONE_RE = re.compile(r"(?:\+49|0049|\b0)[\d\s\-()/\.]{6,20}\d")
DATELIKE_RE = re.compile(r"\d{1,2}\.\d{1,2}\.\d{2,4}")  # e.g. 04.11.2026
SALARYLIKE_RE = re.compile(r"\d{1,3}\.000\b")  # German thousands: 40.000 - 55.000 €/Jahr
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
BAD_EMAIL_TLDS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "js", "css",
                  "woff", "woff2", "ico"}
BAD_EMAIL_PAT = re.compile(r"(noreply|no-reply|sentry|wixpress|example\.|"
                           r"\.(png|jpg|gif|webp|svg|js|css))", re.I)


def extract_contacts(raw: str, text: str, ba: dict | None) -> tuple[str, str, str]:
    """(phone, email, contact_source) — tel:/mailto: first, then regex."""
    raw = raw or ""
    phones, emails = [], []
    src_note = ""
    if "tel:" in raw or "mailto:" in raw:
        for m in re.finditer(r'href=["\']tel:([^"\']{6,25})', raw):
            phones.append(re.sub(r"[^+\d]", "", m.group(1)))
        for m in re.finditer(r'href=["\']mailto:([^"\'?]+)', raw):
            emails.append(m.group(1).strip())
        if phones or emails:
            src_note = "tel:/mailto: links"
    if ba:
        k = ba.get("kontakt") or {}
        if isinstance(k, dict):
            if k.get("telefon"):
                phones.append(re.sub(r"[^+\d]", "", str(k["telefon"])))
            if k.get("email"):
                emails.append(str(k["email"]).strip())
            if k.get("url"):
                src_note = (src_note + ";" if src_note else "") + "ba_api.kontakt"
    for m in PHONE_RE.finditer(text[:15000]):
        p = m.group(0).strip()
        if DATELIKE_RE.search(p):  # posting deadlines are NOT phone numbers
            continue
        if SALARYLIKE_RE.search(p):  # salary ranges (40.000 - 55.000) are NOT phones
            continue
        digits = re.sub(r"\D", "", p)
        if 7 <= len(digits) <= 15:
            phones.append(p)
    for m in EMAIL_RE.finditer(text[:15000]):
        e = m.group(0)
        if e.split(".")[-1].lower() not in BAD_EMAIL_TLDS \
                and not BAD_EMAIL_PAT.search(e):
            emails.append(e)

    def clean(lst, is_phone):
        out = []
        for x in lst:
            x = x.strip().rstrip(".,;")
            if is_phone:
                d = re.sub(r"\D", "", x)
                if not (7 <= len(d) <= 15):
                    continue
            if x.lower() not in [y.lower() for y in out]:
                out.append(x)
        return out[:3]

    phones, emails = clean(phones, True), clean(emails, False)
    if not src_note:
        src_note = "text regex" if (phones or emails) else ""
    return phones[0] if phones else "", emails[0] if emails else "", src_note


def extract_original_url(raw: str, jsonld: dict | None, ba: dict | None,
                         url: str, source: str) -> str:
    """The ORIGINAL posting at the employer's site — not the portal wrapper."""
    if ba:
        for k in ("externeDarstellung",):
            ed = ba.get(k)
            if isinstance(ed, dict) and ed.get("darstellungUrl"):
                u = ed["darstellungUrl"]
                dom = re.sub(r"^https?://([^/]+).*", r"\1", str(u))
                if not any(p in dom for p in ("arbeitsagentur", "jobboerse")):
                    return str(u)
        if ba.get("arbeitgeberdarstellung"):
            return str(ba["arbeitgeberdarstellung"])
    if jsonld:
        for k in ("url", "@id", "sameAs"):
            v = jsonld.get(k)
            if isinstance(v, str) and v.startswith("http"):
                dom = re.sub(r"^https?://([^/]+).*", r"\1", v)
                if not any(p in dom for p in PORTAL_DOMAINS):
                    return v
                if k == "url" and v != url:
                    return v
    cand = ""
    if raw and raw.lstrip().startswith("<"):
        try:
            soup = BeautifulSoup(raw[:300000], "html.parser")
            can = soup.find("link", rel=lambda x: x and "canonical" in x)
            if can and can.get("href"):
                cand = can["href"]
            base = re.sub(r"^https?://([^/]+).*", r"\1", url)
            for a in soup.find_all("a", href=True):
                h = a["href"]
                if not h.startswith("http"):
                    continue
                dom = re.sub(r"^https?://([^/]+).*", r"\1", h)
                if base in dom or any(p in dom for p in PORTAL_DOMAINS):
                    continue
                if re.search(r"bewerb|apply|job|karriere|stellen|vacanc|offene",
                             h, re.I) and re.search(
                             r"original|direkt|redirect|weiterleit|extern|apply|"
                             r"bewerb", (a.get_text("") + " " + h).lower()):
                    return h
            if cand and not any(p in cand for p in PORTAL_DOMAINS):
                return cand
        except Exception:
            pass
    return ""


def extract_website(raw: str, jsonld: dict | None, ba: dict | None,
                    original_url: str, company: str) -> str:
    if ba:
        k = ba.get("kontakt") or {}
        if isinstance(k, dict) and k.get("url"):
            return str(k["url"])
        ed = ba.get("externeDarstellung") or {}
        if isinstance(ed, dict) and ed.get("darstellungUrl"):
            return str(ed["darstellungUrl"])
    if jsonld:
        org = jsonld.get("hiringOrganization") or {}
        if isinstance(org, dict):
            for k in ("url", "sameAs"):
                v = org.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    return v
    if original_url:
        return re.match(r"(https?://[^/]+)", original_url).group(1)
    if raw and raw.lstrip().startswith("<"):
        for m in re.finditer(r'https?://(www\.)?([a-z0-9\-]+\.[a-z]{2,6})',
                             raw[:60000], re.I):
            dom = m.group(2).lower()
            if not any(p in dom for p in PORTAL_DOMAINS) and \
                    len(company) > 3 and company.lower().split()[0][:5] in dom:
                return f"https://{dom}"
    return ""


def classify_employer(company: str, text: str) -> tuple[str, str]:
    """(employer_type, evidence) — direct | mediator | unknown."""
    hay = (company + " " + text[:12000])
    hits = []
    for m in _BRAND_RE.finditer(hay):
        hits.append(f"brand:{m.group(0).lower()}")
    for m in _AGENCY_RE.finditer(hay):
        hits.append(f"marker:{m.group(0).lower()}")
    if hits:
        return "mediator", "; ".join(sorted(set(hits))[:4])
    return "unknown", "no agency cues found"


def impressum_contacts(raw: str, base_url: str) -> tuple[str, str, str]:
    """Follow Impressum link (1 hop) — German law mandates full contact data."""
    if not raw or not raw.lstrip().startswith("<"):
        return "", "", ""
    try:
        soup = BeautifulSoup(raw[:300000], "html.parser")
        link = None
        for a in soup.find_all("a", href=True):
            if re.search(r"impressum|kontakt|imprint", a["href"], re.I) or \
               re.search(r"impressum|imprint", a.get_text("").lower()):
                link = a["href"]
                break
        if not link:
            return "", "", ""
        if link.startswith("/"):
            link = re.match(r"(https?://[^/]+)", base_url).group(1) + link
        if not link.startswith("http"):
            return "", "", ""
        # NEVER follow the posting-portal's own impressum (it's the mediator's
        # contact, not the employer's) — only external/company domains count
        p_dom = re.sub(r"^https?://(?:www\.)?([^/]+).*$", r"\1", base_url)
        l_dom = re.sub(r"^https?://(?:www\.)?([^/]+).*$", r"\1", link)
        if p_dom == l_dom or p_dom in l_dom or l_dom in p_dom:
            return "", "", ""
        r = _get(link, timeout=15)
        if not r.ok:
            return "", "", ""
        itxt = soup_text(r.text, 8000)
        ph, em, _ = extract_contacts(r.text, itxt, None)
        return ph, em, f"impressum:{link[:80]}"
    except Exception:
        return "", "", ""


# -------------------------------------------------------------------- main
def enrich_one(row: dict, t22: dict) -> dict:
    t0 = time.time()
    src = row.get("source", "")
    out = {
        "url_key": row.get("url_key", ""), "title": row.get("title", ""),
        "company_db": row.get("company", ""), "city": row.get("city", ""),
        "source": src, "url": row.get("url", ""),
        "first_seen": (row.get("first_seen") or "")[:10],
        "experience_class_t22": t22.get("classification", ""),
        "date_posted": "", "date_evidence": "",
        "time_filter_used": TIME_FILTERS.get(src, DEFAULT_TF),
        "employer_direct": "", "employer_type": "unknown",
        "employer_evidence": "", "recruiter_phone": "", "recruiter_email": "",
        "employer_website": "", "original_url": "", "contact_source": "",
        "fetch": "", "secs": 0.0,
    }
    api_json, raw, note, via = fetch_row(row)
    out["fetch"], out["secs"] = note, round(time.time() - t0, 1)
    if not raw and not api_json:
        out["date_evidence"] = f"NOT FETCHED ({note}) — filter: {out['time_filter_used']}"
        return out

    jsonld = extract_jsonld(raw) if raw else None
    text = soup_text(raw, 20000) if (raw and raw.lstrip().startswith("<")) else raw

    # employer name — most authoritative first
    employer = ""
    if api_json and api_json.get("arbeitgeber"):
        employer = str(api_json["arbeitgeber"]).strip()
    if not employer and jsonld:
        org = jsonld.get("hiringOrganization") or {}
        if isinstance(org, dict) and org.get("name"):
            employer = str(org["name"]).strip()
    if not employer:
        employer = row.get("company", "")
    out["employer_direct"] = employer

    # WHEN
    iso, ev = extract_date(raw if (raw and raw.lstrip().startswith("<")) else "",
                           text, jsonld, api_json)
    if not iso and row.get("date_posted"):
        iso, ev = str(row["date_posted"])[:10], "db.date_posted"
    if iso:
        out["date_posted"], out["date_evidence"] = iso, ev
    else:
        out["date_posted"] = out["first_seen"]
        out["date_evidence"] = (f"NO POSTING DATE ON PAGE — first_seen (crawl) "
                                f"used; filter: {out['time_filter_used']}")

    # WHO — mediator or direct
    etype, eevid = classify_employer(employer, text or "")
    if etype == "unknown" and employer:
        # a real company name + own careers/impressum URL hints direct
        if "www." in (text or "")[:2000].lower() or employer[0].isupper():
            etype = "direct"
            eevid = "no agency markers; company named as employer"
    out["employer_type"], out["employer_evidence"] = etype, eevid

    # CONTACT
    ph, em, csrc = extract_contacts(raw, text or "", api_json)
    if (not ph or not em) and etype != "mediator" and \
            raw and raw.lstrip().startswith("<"):
        ph2, em2, c2 = impressum_contacts(raw, row["url"])
        if ph2 and not ph:
            ph, csrc = ph2, c2
        if em2 and not em:
            em, csrc = em2, (csrc + "|" + c2 if csrc else c2)
    out["recruiter_phone"], out["recruiter_email"] = ph, em
    out["contact_source"] = csrc

    # original URL + website
    out["original_url"] = extract_original_url(raw, jsonld, api_json,
                                               row["url"], src)
    out["employer_website"] = extract_website(raw, jsonld, api_json,
                                              out["original_url"], employer)
    return out


CSV_COLS = ["url_key", "title", "company_db", "city", "source", "url",
            "date_posted", "date_evidence", "time_filter_used", "first_seen",
            "employer_direct", "employer_type", "employer_evidence",
            "recruiter_phone", "recruiter_email", "employer_website",
            "original_url", "contact_source", "experience_class_t22",
            "fetch", "secs"]


def main() -> None:
    limit = 0
    resume_path = None
    args = sys.argv[1:]
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--resume" in args:
        resume_path = Path(args[args.index("--resume") + 1])
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM postings ORDER BY pk")]  # oldest first = most stale
    if limit:
        rows = rows[:limit]
    t22map = {}
    if T22_CACHE.exists():
        try:
            for rec in json.loads(T22_CACHE.read_text()):
                t22map[rec.get("url", "")] = rec
        except Exception:
            pass

    done_map = {}
    if resume_path and resume_path.exists():
        try:
            for rec in json.loads(resume_path.read_text()):
                if rec.get("fetch") and not rec["fetch"].startswith("crash"):
                    done_map[rec.get("url", "")] = rec
            print(f"[enrich] resume: {len(done_map)} already enriched — skipped")
        except Exception:
            pass
    todo = [r for r in rows if r["url"] not in done_map]
    print(f"[enrich] {len(rows)} postings to enrich "
          f"({len(todo)} to fetch, t22 cache: {len(t22map)} merged)")

    results = list(done_map.values())
    kimeta_rows = [r for r in todo if r.get("source") == "Kimeta"]
    other_rows = [r for r in todo if r.get("source") != "Kimeta"]

    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(enrich_one, r, t22map.get(r["url"], {})): r
                for r in other_rows}
        for f in as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:
                r = futs[f]
                results.append({**r, "fetch": f"crash:{type(e).__name__}",
                                "date_evidence": "crash", "secs": 0})
            done += 1
            if done % 5 == 0:
                print(f"[enrich] {done}/{len(other_rows)} non-kimeta done")

    for r in kimeta_rows:  # sequential — pool rotation is rate-picky
        print(f"[enrich] kimeta: {r['title'][:50]}...")
        try:
            results.append(enrich_one(r, t22map.get(r["url"], {})))
        except Exception as e:
            results.append({**r, "fetch": f"crash:{type(e).__name__}",
                            "date_evidence": "crash", "secs": 0})

    results.sort(key=lambda x: (x.get("source", ""), x.get("url_key", "")))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if resume_path:  # checkpoint for resume after sandbox kills
        resume_path.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")

    jpath = OUT_DIR / f"jobs_enriched_{ts}.json"
    cpath = OUT_DIR / f"jobs_enriched_{ts}.csv"
    dpath = OUT_DIR / f"direct_employers_{ts}.csv"
    jpath.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    with open(cpath, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    gold = [r for r in results if r.get("employer_type") == "direct"
            and (r.get("recruiter_phone") or r.get("recruiter_email"))]
    with open(dpath, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(gold)

    # ---- summary stats
    n = len(results)
    dated = sum(1 for r in results if r.get("date_evidence", "")
                and "first_seen" not in r.get("date_evidence", "")
                and "NOT FETCHED" not in r.get("date_evidence", ""))
    med = sum(1 for r in results if r.get("employer_type") == "mediator")
    direct = sum(1 for r in results if r.get("employer_type") == "direct")
    ph = sum(1 for r in results if r.get("recruiter_phone"))
    em = sum(1 for r in results if r.get("recruiter_email"))
    web = sum(1 for r in results if r.get("employer_website"))
    ourl = sum(1 for r in results if r.get("original_url"))
    ok = sum(1 for r in results if r.get("fetch", "").startswith(
        ("ok", "ba_api", "ba_page")))
    print("\n===== ENRICH SUMMARY =====")
    print(f"rows={n} fetched_ok={ok} failed={n - ok}")
    print(f"WHEN: posting date extracted={dated}/{n} "
          f"(rest: first_seen + time-filter documented)")
    src_counts = {}
    for r in results:
        src_counts[r["source"]] = src_counts.get(r["source"], 0) + 1
    print(f"WHERE: {dict(sorted(src_counts.items()))}")
    print(f"WHO: direct={direct} mediator={med} unknown={n - med - direct}")
    print(f"CONTACTS: phone={ph} email={em} website={web} original_url={ourl}")
    print(f"files: {jpath.name} {cpath.name} {dpath.name} ({len(gold)} gold rows)")


if __name__ == "__main__":
    main()
