#!/usr/bin/env python3
"""Task 22 — visit EVERY job link from the latest pull, read the full
description, and classify experience requirements for a FRESH
Fachinformatiker für Systemintegration applicant.

Classes:
  entry_ok          no experience requirement found (or explicit entry signals)
  needs_experience  hard cue: mehrjährige/„X Jahre"/langjährige/fundierte
                    Berufserfahrung, senior titles, ...
  needs_review      ambiguous mention ("Berufserfahrung" without years,
                    "erfahrene Fachkraft") — kept out of the clean list,
                    evidence shown for human decision
  unverifiable      fetch failed (page blocked/dead) — filtered out honestly

Fetch strategy per source:
  BA/BA+XING      BA Jobsuche detail API (X-API-Key: jobboerse-jobsuche),
                  full HTML page as fallback
  Kimeta          GET via pipeline proxy pool (pick("kimeta") + rotate)
  Talent.com,
  Get-in-IT,
  InFranken       direct browser-UA GET; on 403/blocked → any alive proxy
  Indeed          direct then proxy; usually bot-walled → unverifiable

Outputs (download/verified/<ts>/):
  task22_linkcheck.json      full per-job record incl. evidence
  task22_entry_ok.csv        the clean fresh-FISI list
  task22_filtered_out.csv    rejected with evidence
  task22_needs_review.csv    borderline with evidence
  task22_summary.txt         human-readable summary
"""
from __future__ import annotations

import base64
import concurrent.futures as cf
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, "/home/z/my-project")
from pipeline.proxy_pool import pick, mark_dead  # noqa: E402

ROOT = Path("/home/z/my-project")
CSV_IN = ROOT / "download" / "jobs_latest.csv"
OUT_DIR = ROOT / "download" / "verified" / datetime.now().strftime("%Y-%m-%d")

UA = ("Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0")
HDRS = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.7"}
TIMEOUT = 20


class DeadLink(RuntimeError):
    """Posting is offline/expired (HTTP 404/410) — not a bot wall."""
    def __init__(self, status: int, where: str = ""):
        super().__init__(f"posting offline (HTTP {status}) {where}".strip())
        self.status = status

# ---------------------------------------------------------------- classifier
HARD_PATTERNS = [
    ("mehrjährige Berufserfahrung/Praxis",
     r"mehrjähr\w*\s+(?:Berufs-?\s?|Praxis-?\s?|ausgeübter\s+)?(?:erfahrung|erfahrungen|berufspraxis|praxis)"),
    ("langjährige Erfahrung",
     r"langjähr\w*\s+(?:Berufs-?\s?|Praxis-?\s?)?(?:erfahrung|erfahrungen|berufspraxis)"),
    ("X Jahre Berufserfahrung (Zahl vor Nomen)",
     r"\d+\s*(?:[-–bis\w]*\s*)?Jahre[sn]?\s+(?:Berufs-?\s?|Praxis-?\s?|relevanten?\s+)?erfahrung"),
    ("mindestens/min X Jahre Erfahrung",
     r"(?:mindestens|min\.?|mehr als|über)\s+\d+\s*(?:[-–]\s*\d+\s*)?Jahre[sn]?\s+(?:Berufs-?\s?|Praxis-?\s?)?(?:erfahrung|berufspraxis)"),
    ("X-jaehrige(r) Berufserfahrung",
     r"\d+\s*(?:-|–)?\s*jährig\w*\s+(?:Berufs-?\s?|berufliche[rn]?|praktische[rn]?)?\s*(?:erfahrung|berufspraxis)"),
    ("fundierte/umfangreiche Berufserfahrung",
     r"(?:fundierte|umfangreiche|vertiefte|ausgeprägte|sehr gute|einschlägige)\s+(?:Berufs-?\s?|Praxis-?\s?)?(?:erfahrung|berufspraxis)"),
    ("Berufserfahrung von X Jahren",
     r"erfahrung\s+(?:von|ab)\s+(?:mindestens\s+)?\d+\s*(?:bis\s*\d+\s*)?Jahre[ns]?"),
    ("nur fuer Erfahrene / keine Einsteiger",
     r"keine\s+(?:Berufs-?)?einsteiger|nur\s+für\s+erfahrene"),
]
TITLE_REJECT = re.compile(
    r"\b(?:senior|expert(?:e|en|in)?|erfahrene[rn]?\s+(?:fachkraft|mitarbeiter|kolleg|fachinformatiker|it-)|spezialist\s+mit\s+erfahrung)\b",
    re.I)
ENTRY_SIGNALS = [
    ("Berufseinsteiger", r"berufseinsteiger"),
    ("Einstiegsposition/-level/-chance", r"einstiegs(?:position|level|chance|rolle)"),
    ("Junior", r"\bjunior\w*\b"),
    ("Absolvent", r"absolvent\w*\b"),
    ("Quereinsteiger willkommen", r"quereinsteiger"),
    ("erste Erfahrung / erste Berufserfahrung", r"erste\s+(?:berufs)?erfahrung"),
    ("keine Berufserfahrung nötig", r"keine\s+(?:berufs)?erfahrung"),
    ("Ausbildung (abgeschlossen)", r"abgeschlossene?\w*\s+(?:Berufs)?ausbildung"),
    ("Fachinformatiker gesucht", r"fachinformatiker"),
]
REVIEW_PATTERNS = [
    ("Berufserfahrung erwaehnt (ohne Jahreszahl)", r"berufserfahrung|berufspraxis"),
    ("erfahrene(r/s) Fachkraft ...", r"erfahrene[rns]?\s+(?:fachkraft|mitarbeiter|kolleg\w*|kollegen|fachinformatiker|it-)"),
]

def _compile(pairs):
    return [(name, re.compile(rx, re.I | re.S)) for name, rx in pairs]


HARD = _compile(HARD_PATTERNS)
ENTRY = _compile(ENTRY_SIGNALS)
REVIEW = _compile(REVIEW_PATTERNS)


# a HARD hit is INVALID (company self-praise, not a candidate requirement)
# when the text right before it is a possessive/marketing frame:
#   "Profitieren Sie von unserer langjährigen Erfahrung",
#   "dank unserer langjährigen Erfahrung", "von unsrer langjährigen Praxis"
COMPANY_GUARD = re.compile(
    r"(?:von\s+|dank\s+|aufgrund\s+|wegen\s+)?unsere?[rmn]?\s*$|"
    r"\b(?:umfassen|umfasst)\s+(?:über\s+|mehr\s+als\s+)?$|\bblicken\s+wir\s+auf\s*$|"
    r"profitier(?:en\s+Sie|e\s+ich|st\s+du)\s+von[\s\w]{0,20}$", re.I)
SOFT_RX = re.compile(r"w\u00fcnschenswert|von\s+Vorteil|nice\s+to\s+have", re.I)


def classify(text: str, title: str) -> tuple[str, list[str]]:
    text = text or ""
    hits_hard, hits_entry, hits_review = [], [], []
    # header zone of the fetched page often carries the REAL title
    # (CSV titles may be truncated — a XING "IT-Administrator" was truly
    #  "Senior IT Systemadministrator")
    mt = TITLE_REJECT.search(text[:600])
    if mt:
        zone = text[:600][max(0, mt.start() - 40):mt.end() + 40].replace("\n", " ")
        return "needs_experience", [f"[title-zone] ...{zone}..."]
    for name, rx in HARD:
        m = rx.search(text)
        if not m:
            continue
        pre = text[max(0, m.start() - 60):m.start()]
        if COMPANY_GUARD.search(pre):
            continue  # company's own experience — not a requirement
        s = max(0, m.start() - 60)
        ev = f"[{name}] …{text[s:m.end() + 60]}…".replace("\n", " ")
        if SOFT_RX.search(text[m.start():m.end() + 60]):
            hits_review.append("[soft: wünschenswert/von Vorteil] " + ev)
        else:
            hits_hard.append(ev)
    if hits_hard:
        return "needs_experience", hits_hard[:3]
    if title and TITLE_REJECT.search(title):
        return "needs_experience", [f"[title] {title}"]
    # review beats entry: an ambiguous experience mention outweighs a
    # positive entry signal (a "Fachinformatiker gesucht" ad that ALSO says
    # "Mehrjährige Erfahrung wünschenswert" must NOT be entry_ok)
    if hits_review:
        return "needs_review", hits_review[:3]
    for name, rx in ENTRY:
        m = rx.search(text)
        if m:
            hits_entry.append(name)
    if hits_entry:
        return "entry_ok", hits_entry[:4]
    for name, rx in REVIEW:
        m = rx.search(text)
        if m:
            s = max(0, m.start() - 60)
            hits_review.append(f"[{name}] …{text[s:m.end() + 60]}…".replace("\n", " "))
    if hits_review:
        return "needs_review", hits_review[:3]
    return "entry_ok", ["keine Erfahrungsvoraussetzung im Text gefunden"]


# ---------------------------------------------------------------- fetchers
def _soup_text(html: str, limit: int = 30000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript",
                     "svg", "form", "iframe"]):
        tag.decompose()
    txt = soup.get_text("\n")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{2,}", "\n", txt)
    return txt[:limit]


def _get(url: str, *, proxies: dict | None = None) -> requests.Response:
    return requests.get(url, headers=HDRS, proxies=proxies, timeout=TIMEOUT)


def _via_proxy(url: str, target: str) -> str:
    last = None
    last_status = 0
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
                raise DeadLink(r.status_code, "via proxy")
            last = f"HTTP {r.status_code} via proxy {entry['host']}"
        except DeadLink:
            raise
        except Exception as e:
            last = f"{type(e).__name__} via proxy {entry.get('host')}"
            mark_dead(entry)
    if last_status in (404, 410):
        raise DeadLink(last_status, "via proxy")
    raise RuntimeError(last or "no proxy left in pool")


def fetch_ba(row: dict) -> str:
    m = re.search(r"/jobdetail/([0-9A-Za-z\-]+)", row["url"])
    if m:
        b64 = base64.urlsafe_b64encode(m.group(1).encode()).decode()
        try:
            r = _get("https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/"
                     f"pc/v4/jobdetails/{b64}",
                     headers={"X-API-Key": "jobboerse-jobsuche", "User-Agent": UA})
            if r.ok:
                d = r.json()
                desc = d.get("stellenangebotsBeschreibung") or ""
                if len(desc) > 100:
                    return desc
            elif r.status_code in (404, 410):
                raise DeadLink(r.status_code, "BA detail API")
        except DeadLink:
            raise
        except Exception:
            pass
    r = _get(row["url"])
    if r.ok:
        return _soup_text(r.text)
    if r.status_code in (404, 410):
        raise DeadLink(r.status_code, "BA page")
    raise RuntimeError(f"BA fetch HTTP {r.status_code}")


def fetch_kimeta(row: dict) -> str:
    return _soup_text(_via_proxy(row["url"], "kimeta"))


def fetch_generic(row: dict) -> str:
    try:
        r = _get(row["url"])
        if r.ok and len(r.text) > 800 and "captcha" not in r.text[:3000].lower():
            return _soup_text(r.text)
        if r.status_code in (404, 410):
            raise DeadLink(r.status_code, "direct")
    except DeadLink:
        raise
    except Exception:
        pass
    return _soup_text(_via_proxy(row["url"], "any"))  # any alive proxy


FETCHERS = {
    "BA": fetch_ba, "BA+XING": fetch_ba,
    "Kimeta": fetch_kimeta,
}


def fetch_row(row: dict) -> tuple[str, str]:  # (text, fetch_note)
    src = row.get("source", "")
    fn = FETCHERS.get(src, fetch_generic)
    try:
        t = fn(row)
        return t, "ok"
    except DeadLink:
        raise
    except Exception as e:
        return "", f"fetch_failed: {type(e).__name__}: {str(e)[:120]}"


# ---------------------------------------------------------------- main
def main() -> None:
    rows = list(csv.DictReader(CSV_IN.open(encoding="utf-8-sig")))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[t22] {len(rows)} jobs to verify -> {OUT_DIR}")

    records = []
    # kimeta through the pool is picky about rate — run those sequentially first
    kimeta_rows = [r for r in rows if r.get("source") == "Kimeta"]
    other_rows = [r for r in rows if r.get("source") != "Kimeta"]

    def handle(row: dict) -> dict:
        t0 = time.time()
        try:
            text, note = fetch_row(row)
        except DeadLink as e:
            return {"title": row.get("title"), "company": row.get("company"),
                    "city": row.get("city"), "source": row.get("source"),
                    "url": row.get("url"), "classification": "expired",
                    "evidence": [str(e)], "text_len": 0, "fetch": "dead-link",
                    "secs": round(time.time() - t0, 1), "desc_excerpt": ""}
        if text:
            cls, ev = classify(text, row.get("title", ""))
        else:
            cls, ev = "unverifiable", [note]
        rec = {
            "title": row.get("title"), "company": row.get("company"),
            "city": row.get("city"), "source": row.get("source"),
            "url": row.get("url"), "classification": cls,
            "evidence": ev, "text_len": len(text),
            "fetch": note, "secs": round(time.time() - t0, 1),
            "desc_excerpt": text[:600] if text else "",
        }
        return rec

    done = 0
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(handle, r): r for r in other_rows}
        for f in cf.as_completed(futs):
            rec = f.result()
            records.append(rec)
            done += 1
            if done % 8 == 0 or done == len(other_rows):
                print(f"[t22] {done}/{len(other_rows)} non-kimeta done "
                      f"(entry_ok={sum(1 for r in records if r['classification']=='entry_ok')}, "
                      f"reject={sum(1 for r in records if r['classification']=='needs_experience')}, "
                      f"review={sum(1 for r in records if r['classification']=='needs_review')}, "
                      f"unverif={sum(1 for r in records if r['classification']=='unverifiable')})")
    for r in kimeta_rows:            # sequential, pool-rotated
        rec = handle(r)
        records.append(rec)
        print(f"[t22] kimeta: {rec['classification']} | {rec['title'][:60]} ({rec['text_len']} B, {rec['secs']}s)")

    for rec in records:
        if rec["fetch"] == "ok" and rec["text_len"] < 400:
            rec["classification"] = rec["classification"] if rec["classification"] != "entry_ok" else "needs_review"
            rec["evidence"] = [f"text too short ({rec['text_len']} B) for reliable check"] + rec["evidence"]

    ts = datetime.now().strftime("%Y%m%d-%H%M")
    (OUT_DIR / "task22_linkcheck.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")

    def dump(name, recs):
        with (OUT_DIR / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["classification", "title", "company", "city", "source",
                        "url", "evidence"])
            for r in recs:
                w.writerow([r["classification"], r["title"], r["company"], r["city"],
                            r["source"], r["url"], " | ".join(r["evidence"])])

    entry_ok = sorted([r for r in records if r["classification"] == "entry_ok"],
                      key=lambda r: r["source"])
    dump("task22_entry_ok.csv", entry_ok)
    dump("task22_filtered_out.csv",
         [r for r in records if r["classification"] == "needs_experience"])
    dump("task22_needs_review.csv",
         [r for r in records if r["classification"] == "needs_review"])
    dump("task22_expired_or_unverifiable.csv",
         [r for r in records if r["classification"] in ("expired", "unverifiable")])

    from collections import Counter
    by = Counter(r["classification"] for r in records)
    lines = [
        f"Task 22 link check — {datetime.now(timezone.utc).isoformat()}",
        f"Input: {CSV_IN.name} ({len(rows)} jobs, Erlangen+50km, 14d window)",
        "",
        f"RESULT: {by.get('entry_ok',0)} entry_ok | {by.get('needs_experience',0)} needs_experience | "
        f"{by.get('needs_review',0)} needs_review | {by.get('expired',0)} expired | "
        f"{by.get('unverifiable',0)} unverifiable",
        "",
        "=== VERIFIED ENTRY-LEVEL (fresh FISI suitable) ===",
    ]
    for r in entry_ok:
        lines.append(f"* [{r['source']}] {r['title']} @ {r['company']} ({r['city']})")
        lines.append(f"  {r['url']}")
        lines.append(f"  evidence: {'; '.join(r['evidence'])}")
    (OUT_DIR / "task22_summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:9]))
    print(f"\n[t22] artifacts in {OUT_DIR}")


if __name__ == "__main__":
    main()
