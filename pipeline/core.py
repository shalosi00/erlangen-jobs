"""Core: Job model, hard filters, dedupe, output writers, per-source error capture.

Hard filters (user requirement, always ON unless --no-filters):
  1. no Ausbildung / apprenticeship offers
  2. no part-time / minijob
  3. no job that asks for prior experience
  4. full-time only
Anything ambiguous is KEPT but flagged (ft_unknown) so the CSV stays filterable
instead of silently dropping rows that lack a description.
"""
from __future__ import annotations
import csv, html, json, re, time, unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- models ----

@dataclass
class FetchCtx:
    query: str
    city: str = "Erlangen"
    radius: int = 50
    days: int = 14
    timeout: int = 25
    sleep: float = 1.2
    deep: bool = True          # BA: fetch per-job descriptions
    max_pages: int = 2
    max_per_source: int = 200
    keys: dict = field(default_factory=dict)   # API keys from env
    near_re: "re.Pattern" = None               # 50-km whitelist (compiled)
    cutoff: str = ""                            # ISO date cutoff

@dataclass
class Job:
    source: str
    title: str
    company: str
    city: str = ""
    plz: str = ""
    location_raw: str = ""
    date_posted: str = ""
    url: str = ""
    description: str = ""
    employment_raw: str = ""
    is_remote: bool = False
    salary_min: float = None
    salary_max: float = None
    currency: str = ""
    external_id: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    ft_unknown: bool = False
    junior_signal: str = ""
    transit: str = ""          # F1: 0-xfer (NNmin) | limited | borderline | 1-xfer | none | >60min
    notes: str = ""

@dataclass
class SourceResult:
    name: str
    status: str = "OK"            # OK | EMPTY | ERROR | SKIP
    count_raw: int = 0
    count_kept: int = 0
    count_rejected: int = 0
    duration_s: float = 0.0
    http_status: int = None
    error: str = ""
    detail: str = ""              # pinpoint info: URL / snippet / hint

class SourceError(Exception):
    """Raised by sources with precise failure info."""
    def __init__(self, kind: str, message: str, http_status=None, url="", detail=""):
        super().__init__(f"[{kind}] {message}")
        self.kind = kind            # auth|waf|http|parse|shape|timeout|net
        self.http_status = http_status
        self.url = url
        self.detail = detail

# --------------------------------------------------------------- helpers ----

def strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def norm_txt(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"\(m/w/d\)|\(m/w/x\)|\(d/m/w\)|\(w/m/d\)|\(m/w\)", " ", s, flags=re.I)
    s = re.sub(r"[^a-z0-9äöüß ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()

# internal posting reference numbers agencies re-print in titles ("... ID 7285",
# "... ID SW72", "Ref-Nr: ABC123") -> stripped for dedupe comparison only
_REF_RX = re.compile(r"\b(id|ref\.?(?:-?nr)?|job-?id|referenz)\b\s*[:#]?\s*[\w-]+", re.I)

def title_key(title: str) -> str:
    """Normalized title WITHOUT agency reference IDs (dedupe-only key)."""
    return norm_txt(_REF_RX.sub(" ", title or ""))

def parse_date(v) -> str:
    """Return ISO date string or ''."""
    if v in (None, "", "NaN"):
        return ""
    if isinstance(v, (int, float)):
        ts = float(v)
        if abs(ts) > 1e11:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
        except Exception:
            return ""
    s = str(v)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date().isoformat()
        except ValueError:
            return ""
    return ""

def date_from_text(text: str) -> str:
    """Best-effort relative/absolute date from card context text."""
    if not text:
        return ""
    t = text.lower()
    now = datetime.now(timezone.utc).date()
    if re.search(r"\bheute\b|today", t):
        return now.isoformat()
    if re.search(r"gestern|yesterday", t):
        return (now - timedelta(days=1)).isoformat()
    m = re.search(r"vor (\d+) tagen?|(\d+) days? ago", t)
    if m:
        return (now - timedelta(days=int(m.group(1) or m.group(2)))).isoformat()
    m = re.search(r"vor (\d+) wochen?|(\d+) weeks? ago", t)
    if m:
        return (now - timedelta(weeks=int(m.group(1) or m.group(2)))).isoformat()
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date().isoformat()
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    return m.group(0) if m else ""

# ----------------------------------------------------------- hard filters ----

AUSBILDUNG_RX = re.compile(
    r"(?i)\bausbildung\b|auszubild|\bazubi\b|azubine|duales studium|dual(e|es)? studium|"
    r"apprentice(ship)?\b|lehrstelle|ausbildungsplatz|praktikum|praktikant|werkstudent|"
    r"working student|abschlussarbeit|\bthesis\b|traineeprogramm")
# F4: description hits only reject when the ROLE itself is the apprenticeship;
# generic "Ausbildung" mentions are employer boilerplate ("Wir engagieren uns in
# Ausbildung und Weiterbildung...") and must NOT silently drop real jobs.
AUSBILDUNG_ROLE_RX = re.compile(
    r"(?i)ausbildung\s+(?:als|zum|zur)\b|ausbildungsplatz|auszubildend\w*|"
    r"azubine|\bazubis?\b|lehrstelle|dual(e|es)?\s+studium")
# F2: bare "450" matched headcounts ("über 450 Mitarbeitern") and salaries;
# require a currency marker or the "auf 450" idiom.
PARTTIME_RX = re.compile(r"(?i)teilzeit|part[- ]?time|minijob|mini-?job|geringf(ü|ue)gig|"
                         r"auf\s+450\b|\b450\s*[-–]?\s*(?:€|eur\b|euros?\b)")
FULLTIME_RX = re.compile(r"(?i)vollzeit|full[- ]?time")
EXPERIENCE_TITLE_RX = re.compile(
    r"(?i)\bsenior\b|\bexpert(e)?\b|\blead\b|principal|head of|teamleiter(in)?|gruppenleiter(in)?|"
    r"bereichsleiter(in)?|\bmedior\b|erfahrener?\s|\barchitekt(in)?\b|\barchitect\b|\bdirector\b")
EXPERIENCE_BODY_RX = re.compile(
    r"(?i)(\d+\s*(?:\+|-|bis\s*\d+\s*)?jahre?s?\s*(?:berufs)?erfahrung|jahre(?:s)?\s+erfahrung|"
    r"erfahrung\s+(?:ist\s+|wird\s+)?(?:erforderlich|vorausgesetzt|zwingend|notwendig)|"
    r"mindestens\s+\d+\s+jahr|"
    r"\d+\+?\s*years?\s+(?:of\s+)?(?:professional\s+|relevant\s+|work(?:ing)?\s+)?experience|"
    r"experience\s+(?:is\s+)?(?:required|necessary|mandatory|essential))")
# F3: negation window around experience hits — "...erwartet wir nicht" is a
# junior-friendly posting, not a rejection.
EXPERIENCE_NEG_RX = re.compile(
    r"(?i)nicht|keine|ohne|egal|not\s+required|no\s+need|must\s+not|"
    r"don'?t\s+need|doesn'?t\s+need|no\s+longer|wird\s+nicht|ist\s+nicht|"
    r"sind\s+nicht|nice\s+to\s+have|w(ü|ue)nschenswert|vorteilhaft|willkommen")
EXPERIENCE_WINDOW = 90
JUNIOR_RX = re.compile(
    r"(?i)\bjunior\b|berufseinsteiger|einstiegs?position|einstiegs?level|\beinstieg\b|entry.?level|"
    r"erfahrung nicht erforderlich|first.?level|1st.?level|it.?supporter|anwendungsbetreuung|"
    r"anwenderbetreuung|\bsupporter\b|helpdesk|servicedesk|absolvent")
# relevance: keep only IT/FISI-adjacent titles (proven regex from production pull #1)
RELEVANT_RX = re.compile(
    r"(?i)fachinformatiker|systemintegration|system ?integrat|systemadministrator|"
    r"system ?administrator|it-?(support|admin|servic|techniker|mitarbeiter|spezialist|"
    r"referent|berater|allrounder)|\bit ?support|\bit ?admin|informatiker|first ?level|"
    r"1st ?level|anwenderbetreuung|anwendungsbetreuung|client ?manager|edv|\bit ?manager|"
    r"\bit ?team|server ?admin|it-?infrastruktur|telematikinfrastruktur|rechenzentrum|"
    r"client ?management|\bit ?techniker|\bit ?berater|\bit-?system|\bhelpdesk|\bservicedesk|"
    r"\bdevops\b|\bnetzwerk\b|network engineer|\bwindows ?server|\blinux\b|\bsysadmin\b|"
    r"systembetreuer|anwendungsadministrator|\bit ?technik|\bit ?administration")

def classify_job(j: Job) -> tuple[bool, str]:
    """Return (keep, reason_if_rejected). Sets j.ft_unknown / j.junior_signal."""
    text_title = f"{j.title} {j.employment_raw}"
    desc = j.description or ""
    low_desc = desc.lower()

    # 0) relevance: IT/FISI-adjacent title required
    if not RELEVANT_RX.search(j.title or ""):
        return False, "relevance"
    # 1) Ausbildung / student positions -> out (user: first job AFTER Ausbildung)
    #    F4: title hits are hard rejects (short field, always role-referential);
    #    description hits only reject on role-shaped patterns, boilerplate gets a note.
    if AUSBILDUNG_RX.search(text_title):
        return False, "ausbildung(title)"
    if AUSBILDUNG_ROLE_RX.search(low_desc):
        return False, "ausbildung(desc)"
    if AUSBILDUNG_RX.search(low_desc):
        j.notes = (j.notes + " mentions-ausbildung").strip()
    # 2) part-time -> out
    if PARTTIME_RX.search(text_title):
        return False, "parttime(title)"
    has_tz_desc = bool(PARTTIME_RX.search(low_desc))
    has_vz_desc = bool(FULLTIME_RX.search(low_desc))
    if has_tz_desc and not has_vz_desc:
        return False, "parttime(desc)"
    if j.employment_raw and re.search(r"(?i)teilzeit|part", j.employment_raw) \
            and not re.search(r"(?i)vollzeit|full", j.employment_raw):
        return False, "parttime(structured)"
    # 3) asks for experience -> out (F3: skip when negated within ±90 chars)
    if EXPERIENCE_TITLE_RX.search(j.title or ""):
        return False, "experience(title)"
    if desc:
        m = EXPERIENCE_BODY_RX.search(low_desc)
        if m:
            window = low_desc[max(0, m.start() - EXPERIENCE_WINDOW):m.end() + EXPERIENCE_WINDOW]
            if EXPERIENCE_NEG_RX.search(window):
                j.notes = (j.notes + " negated-experience").strip()
            else:
                return False, "experience(desc)"
    # 4) full-time only: confirm via structured field or description
    if re.search(r"(?i)vollzeit|full", j.employment_raw or ""):
        pass
    elif has_vz_desc:
        pass
    elif has_tz_desc and has_vz_desc:
        pass  # offers both; FT available
    else:
        j.ft_unknown = True   # kept, flagged; filterable in CSV
    if JUNIOR_RX.search(j.title or ""):
        j.junior_signal = "yes"
    return True, ""

# ---------------------------------------------------------------- dedupe ----

def _tok(s: str) -> set:
    """Company/title tokens for overlap checks; legal forms (GmbH, AG, ...)
    filtered — 'Brunel GmbH' vs 'FERCHAU GmbH' must NOT count as same company."""
    stop = {"gmbh", "mbh", "ag", "kg", "kgaa", "ohg", "ug", "se", "gbr",
            "niederlassung", "personaldienstleistung", "personalberatung",
            "germany", "deutschland", "group", "international"}
    return {t for t in re.findall(r"[a-z0-9]{2,}", norm_txt(s)) if t not in stop}

def canon_url(u: str) -> str:
    """Canonical form for same-posting detection: agencies re-title postings
    but the detail URL (e.g. .../jobdetail/12634-BB-64) is stable."""
    if not u:
        return ""
    u = u.strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")

def _merge(old: Job, new: Job):
    srcs = set(old.source.split("+")) | set(new.source.split("+"))
    old.source = "+".join(sorted(srcs))
    if not old.date_posted or (new.date_posted and new.date_posted > old.date_posted):
        old.date_posted = new.date_posted
    if not old.url and new.url:
        old.url = new.url
    if not old.description and new.description:
        old.description = new.description
    if not old.employment_raw and new.employment_raw:
        old.employment_raw = new.employment_raw
    if new.salary_min and not old.salary_min:
        old.salary_min, old.salary_max, old.currency = new.salary_min, new.salary_max, new.currency
    if new.junior_signal:
        old.junior_signal = "yes"
    if new.ft_unknown is False:
        old.ft_unknown = False
    if not old.city and new.city:
        old.city = new.city
    if not old.plz and new.plz:
        old.plz = new.plz

def _jac(a: str, b: str) -> float:
    """Token Jaccard similarity of two title keys (German stopwords + stray
    single letters from m/w/d and NFKD-split umlauts ignored)."""
    stop = {"fur", "für", "fuer", "fu",  # 'fu' = NFKD-split artifact of "für"
            "der", "die", "das", "den", "dem", "ein", "eine",
            "in", "im", "zum", "zur", "und", "oder", "als", "auf", "bei", "mit",
            "pro", "von", "aus", "am", "an"}
    ta = {t for t in a.split() if len(t) > 1 and t not in stop}
    tb = {t for t in b.split() if len(t) > 1 and t not in stop}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

# optional C++ fuzzy matcher (rapidfuzz) — pipeline degrades gracefully without it
try:
    from rapidfuzz import fuzz as _fuzz
except ImportError:
    _fuzz = None

def dedupe(jobs: list[Job]) -> list[Job]:
    """Three-layer dedupe:
      1. exact (title,company,city) key merge
      2. exact canonical-URL merge — catches agency re-titling (same BA jobdetail
         URL under two different titles; proven on production data 12634-BB-64)
      3. near-dupe merge: Jaccard>=0.6 + same city + company overlap
    Afterwards pairs scoring >=90 on rapidfuzz token-set similarity (same city,
    overlapping company) are FLAGGED in notes — never auto-merged ( Brunel vs
    FERCHAU 'IT-Spezialist' showed >=90 can still be two distinct employers)."""
    out: list[Job] = []
    exact: dict = {}
    urls: dict = {}
    for j in jobs:
        key = (title_key(j.title)[:70], norm_txt(j.company)[:40], norm_txt(j.city)[:20])
        cu = canon_url(j.url)
        if key in exact:
            _merge(exact[key], j)
            if cu and cu not in urls:
                urls[cu] = exact[key]
            continue
        if cu and cu in urls:
            _merge(urls[cu], j)
            continue
        exact[key] = j
        if cu:
            urls[cu] = j
        out.append(j)
    near: list[Job] = []
    near_keys: list[str] = []
    for j in out:
        hit = None
        jk = title_key(j.title)
        for o, ok_ in zip(near, near_keys):
            # merge when titles are near-identical (>=0.6 Jaccard, catches
            # "...für..." inserts and ID variants), same city, company overlap
            if _jac(ok_, jk) >= 0.6 and norm_txt(o.city) == norm_txt(j.city) \
                    and _tok(o.company) & _tok(j.company):
                hit = o
                break
        if hit:
            _merge(hit, j)
        else:
            near.append(j)
            near_keys.append(jk)
    # flag (not merge) suspiciously similar pairs for human review.
    # Gate = same city + token-set ratio >=95, deliberately WITHOUT a company
    # check: staffing agencies re-post the same end-client job under different
    # names (Brunel vs FERCHAU 'IT-Spezialist'), and those are exactly the
    # pairs worth one glance. 4 flags on 43 production rows = low noise.
    if _fuzz is not None and len(near) > 1:
        for i in range(len(near)):
            for k in range(i + 1, len(near)):
                a, b = near[i], near[k]
                if a.url and a.url == b.url:
                    continue  # same URL would already be merged above
                if norm_txt(a.city) == norm_txt(b.city) \
                        and _fuzz.token_set_ratio(title_key(a.title),
                                                  title_key(b.title)) >= 95:
                    a.notes = (a.notes + " near-dupe-candidate").strip()
                    b.notes = (b.notes + " near-dupe-candidate").strip()
    return near

# ---------------------------------------------------------------- output ----

CSV_COLS = ["date_posted", "title", "company", "city", "plz", "source", "employment_raw",
            "ft_unknown", "junior_signal", "transit", "is_remote", "salary_min", "salary_max",
            "currency", "days_old", "url", "external_id", "fetched_at", "notes", "snippet"]

def days_old(j: Job) -> str:
    if not j.date_posted:
        return ""
    try:
        d = datetime.fromisoformat(j.date_posted).date()
        return str((datetime.now(timezone.utc).date() - d).days)
    except Exception:
        return ""

def write_outputs(kept: list[Job], rejected: list, out_dir: str, slug: str, quiet=False):
    import os, shutil
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    base = f"{out_dir}/jobs_{slug}_{ts}"
    kept = sorted(kept, key=lambda j: (j.date_posted or "0000", not j.ft_unknown), reverse=True)
    csv_path = base + ".csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        for j in kept:
            snippet = re.sub(r"\s+", " ", (j.description or ""))[:200]
            w.writerow([j.date_posted, j.title, j.company, j.city, j.plz, j.source,
                        j.employment_raw, "TRUE" if j.ft_unknown else "", j.junior_signal,
                        j.transit, "yes" if j.is_remote else "", j.salary_min or "", j.salary_max or "",
                        j.currency, days_old(j), j.url, j.external_id, j.fetched_at, j.notes,
                        snippet])
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        rows = []
        for j in kept:
            d = asdict(j)
            d["days_old"] = days_old(j)
            d["description"] = (j.description or "")[:4000]
            rows.append(d)
        json.dump(rows, f, ensure_ascii=False, indent=1)
    shutil.copyfile(csv_path, f"{out_dir}/jobs_latest.csv")
    shutil.copyfile(json_path, f"{out_dir}/jobs_latest.json")
    rej_path = base + "_rejected.csv"
    with open(rej_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["filter_reason", "source", "title", "company", "city", "url"])
        for j, reason in rejected:
            w.writerow([reason, j.source, j.title, j.company, j.city, j.url])
    if not quiet:
        print(f"written: {csv_path}")
        print(f"written: {json_path}")
        print(f"written: {rej_path} (audit)")
    return csv_path, json_path, rej_path
