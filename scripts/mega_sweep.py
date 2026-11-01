#!/usr/bin/env python3
"""MEGA SWEEP — insanely large job search, then filter to junior.

Stages (run one per invocation, resumable via data/mega_sweep/):
  ba       — BA Jobsuche v6 bulk: 14 IT queries x 2 geo-tiers (Erlangen 50km,
             Nuernberg 100km) x last 90 days, 100/page until exhausted.
  enrich   — BA v4 jobdetails for junior-candidate rows (title not excluded,
             not yet title-junior) to capture description-level entry signals.
  portals  — subprocess `python -m pipeline fetch` across the wide source list,
             30-day window, wide radius; output to data/mega_sweep/portals/.
  merge    — merge BA bulk + portal output + today's daily CSV, dedupe
             (URL-canonical + fuzzy title/company/city), classify junior
             (strong/medium/weak/excluded) with the proven pull_fisi_junior
             regexes, write master dataset + junior shortlist + summary,
             absorb into data/jobs_history.db via pipeline.history.update.

Junior classes: strong = title-level signal; medium = description-level
signal (needs enrich/portal description); weak = vague 'Einstieg' mention;
none; excluded = senior/ausbildung/praktikum/werkstudent/manager pattern.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/my-project")
BASE = "/home/z/my-project"
DATA = f"{BASE}/data/mega_sweep"
PORTALS_DIR = f"{DATA}/portals"
TS = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
os.makedirs(DATA, exist_ok=True)
os.makedirs(PORTALS_DIR, exist_ok=True)

BA_H = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "asha-jobtoolkit/1.0"}
BA_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
QUERIES = [
    "Fachinformatiker Systemintegration", "Systemadministrator",
    "IT-Systemadministrator", "IT-Support", "IT-Techniker", "IT-Administrator",
    "IT-Servicetechniker", "IT-Betreuer", "Anwendungsbetreuer", "IT-Mitarbeiter",
    "EDV", "IT-Service", "IT-Helpdesk", "IT-Infrastruktur",
]
TIERS = [("Erlangen", 50), ("Nürnberg", 100)]
DAYS = 90
MAX_PAGES = 25

# ------------------------------------------------ junior machinery (proven set)
def norm_txt(s):
    if not s: return ""
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"\(m/w/d\)|\(m/w/x\)|\(d/m/w\)|\(w/m/d\)", " ", s, flags=re.I)
    s = re.sub(r"[^a-z0-9äöüß ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()

EXCLUDE_RE = re.compile(
    r"(?i)\bausbildung\b|\bazubi\b|auszubild|dual(e|es)? studium|\bpraktik|werkstudent|"
    r"working student|abschlussarbeit|\bthesis\b|apprentice|ausbildungszweck|\bsenior\b|\blead\b|teamleiter|gruppenleiter|"
    r"\bprincipal\b|head of|\barchitekt\b|\barchitect\b|direktor|\bdirector\b|chef[^a-z]|"
    r"\bmanager\b|\bmanagerin\b|leitung|bereichsleiter|niederlassungsleiter")
JUNIOR_RE = re.compile(
    r"(?i)\bjunior\b|junior |berufseinsteiger|einstiegs?position|einstiegs?level|\beinstieg\b|"
    r"entry.?level|erfahrung nicht erforderlich|first.?level|1st.?level|it.?supporter|"
    r"anwendungsbetreuung|anwenderbetreuung|\bsupporter\b|client.?admin|user.?help.?desk|helpdesk|servicedesk")
STRONG_TITLE_RE = re.compile(
    r"(?i)\bjunior\b|berufseinsteiger|einstiegs?position|einstiegs?level|entry.?level|"
    r"erfahrung nicht erforderlich|keine erfahrung|first.?level|1st.?level")
DESC_SIGNAL_RE = re.compile(
    r"(?i)\bjunior\b|berufseinsteiger|berufseinstieg|\beinstieg\b|einstiegsposition|"
    r"erfahrung nicht erforderlich|keine (?:berufs)?erfahrung|erste erfahrung|"
    r"erste berufserfahrung|0?[-–]2 jahre|wenige jahre|einsteiger|quereinsteiger|entry.?level")
RELEVANT_RE = re.compile(
    r"(?i)fachinformatiker|systemintegration|system ?integrat|system ?administrator|"
    r"systemadministrator|it-?(support|admin|servic|techniker|mitarbeiter|spezialist|referent|"
    r"berater|allrounder)|\bit ?support|\bit ?admin|informatiker|first ?level|1st ?level|"
    r"anwenderbetreuung|anwendungsbetreuung|client ?manager|edv|\bit ?manager|\bit ?team|"
    r"server ?admin|it-?infrastruktur|telematikinfrastruktur|rechenzentrum|client ?management|"
    r"\bit ?techniker|\bit ?berater|helpdesk|servicedesk")

def is_excluded(title):
    t = title or ""
    if re.search(r"(?i)\bjunior\b|\bberufseinsteiger", t) and not re.search(
            r"(?i)ausbildung|azubi|praktik|werkstudent", t):
        return False
    if re.search(r"(?i)\breferent", t) and not re.search(r"(?i)it[- ]?referent", t):
        return True
    if re.search(r"(?i)\bexpert", t):
        return True
    return bool(EXCLUDE_RE.search(t))


def classify(row):
    """row needs: title, description (may be ''), source. Returns class string."""
    title = row.get("title") or ""
    desc = row.get("description") or ""
    if is_excluded(title):
        return "excluded"
    if STRONG_TITLE_RE.search(title):
        return "strong"
    blob = f"{title} {desc}"
    if STRONG_TITLE_RE.search(desc) or DESC_SIGNAL_RE.search(desc):
        return "medium"
    if JUNIOR_RE.search(blob):
        return "weak"
    return "none"


# ---------------------------------------------------------------- stage: ba
def stage_ba():
    import requests
    jobs, seen = [], set()
    hits = 0
    for q in QUERIES:
        for city, radius in TIERS:
            for page in range(1, MAX_PAGES + 1):
                url = (f"{BA_BASE}/pc/v6/jobs?was={q}&wo={city}&umkreis={radius}"
                       f"&veroeffentlichtseit={DAYS}&angebotsart=1&pav=false&size=100&page={page}")
                try:
                    r = requests.get(url, headers=BA_H, timeout=30)
                except Exception as e:
                    print(f"  net error {q}|{city}|p{page}: {str(e)[:80]}")
                    break
                if r.status_code != 200:
                    print(f"  HTTP {r.status_code} {q}|{city}|p{page}")
                    break
                sts = (r.json() or {}).get("ergebnisliste") or []
                new = 0
                for s in sts:
                    refnr = s.get("referenznummer")
                    if not refnr or refnr in seen:
                        continue
                    seen.add(refnr)
                    loc = (s.get("stellenlokationen") or [{}])[0].get("adresse") or {}
                    jobs.append({
                        "source": "BA",
                        "title": (s.get("stellenangebotsTitel") or "").strip(),
                        "company": (s.get("firma") or "").strip(),
                        "city": (loc.get("ort") or "").strip(),
                        "plz": str(loc.get("plz") or ""),
                        "date_posted": (s.get("datumErsteVeroeffentlichung")
                                        or (s.get("veroeffentlichungszeitraum") or {}).get("von") or "")[:10],
                        "url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/" + refnr,
                        "employment_raw": ("Vollzeit" if s.get("arbeitszeitVollzeit")
                                           else "Teilzeit" if s.get("arbeitszeitTeilzeit") else ""),
                        "external_id": refnr,
                        "description": "",
                        "geo_tier": f"{city}-{radius}km",
                        "query": q,
                    })
                    new += 1
                hits += len(sts)
                if page % 5 == 0:
                    print(f"  {q} | {city}-{radius}km p{page}: cumulative unique={len(jobs)}")
                if len(sts) < 100:
                    break
                time.sleep(0.35)
        json.dump(jobs, open(f"{DATA}/ba_bulk.json", "w", encoding="utf-8"),
                  ensure_ascii=False)
        print(f"[after '{q}'] unique={len(jobs)} (raw hits={hits})")
    print(f"BA BULK DONE: {len(jobs)} unique postings (raw list hits={hits})")


# ---------------------------------------------------------------- stage: enrich
def stage_enrich():
    import requests
    import base64
    jobs = json.load(open(f"{DATA}/ba_bulk.json", encoding="utf-8"))
    todo = [j for j in jobs
            if not j["description"] and not is_excluded(j["title"])]
    print(f"detail fetch for {len(todo)} candidate rows (excluded titles skipped)")
    ok = fail = 0
    for i, j in enumerate(todo):
        url = f"{BA_BASE}/pc/v4/jobdetails/{base64.b64encode(j['external_id'].encode()).decode()}"
        try:
            r = requests.get(url, headers=BA_H, timeout=25)
            if r.status_code == 200:
                d = r.json()
                txt = d.get("stellenangebotsBeschreibung") or ""
                j["description"] = txt[:6000]
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(todo)} ok={ok} fail={fail}")
            json.dump(jobs, open(f"{DATA}/ba_bulk.json", "w", encoding="utf-8"),
                      ensure_ascii=False)
        time.sleep(0.08)
    json.dump(jobs, open(f"{DATA}/ba_bulk.json", "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"ENRICH DONE: ok={ok} fail={fail}")


# ---------------------------------------------------------------- stage: portals
def stage_portals():
    cmd = ["/home/z/.venv/bin/python", "-m", "pipeline", "fetch",
           "--query", "Fachinformatiker Systemintegration",
           "--city", "Nürnberg", "--radius", "100", "--days", "30",
           "--max-per-source", "300", "--max-pages", "4", "--polite", "0.9",
           "--parallel", "4", "--out", PORTALS_DIR,
           "--sources", "kimeta,talent,getinit,infranken,stellenanzeigen,xing,"
                        "eures,whatjobs,careerjet,jooble,adzuna,indeed,linkedin,"
                        "arbeitnow,wwr,himalayas,connecticum,berufsstart,remotive,jobicy"]
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, timeout=560)
    tail = (r.stdout or "").splitlines()[-25:]
    print("\n".join(tail))
    if r.returncode != 0:
        print("STDERR tail:", (r.stderr or "")[-800:])
    json.dump({"rc": r.returncode}, open(f"{DATA}/portals_rc.json", "w"))


# ---------------------------------------------------------------- stage: merge
def load_portal_rows():
    rows = []
    for fn in sorted(os.listdir(PORTALS_DIR)):
        p = f"{PORTALS_DIR}/{fn}"
        if fn.endswith(".json"):
            try:
                data = json.load(open(p, encoding="utf-8"))
                if isinstance(data, list):
                    for j in data:
                        rows.append({
                            "source": j.get("source") or fn.split("_")[0],
                            "title": j.get("title") or "",
                            "company": j.get("company") or "",
                            "city": j.get("city") or "",
                            "plz": str(j.get("plz") or ""),
                            "date_posted": (j.get("date_posted") or "")[:10],
                            "url": j.get("url") or "",
                            "employment_raw": j.get("employment_raw") or "",
                            "external_id": j.get("external_id") or "",
                            "description": (j.get("description") or "")[:6000],
                            "geo_tier": "portal",
                            "query": "",
                        })
            except Exception as e:
                print(f"  skip {fn}: {e}")
        elif fn.endswith("_rejected.csv"):
            try:
                for r in csv.DictReader(open(p, encoding="utf-8-sig")):
                    rows.append({
                        "source": r.get("source") or "portal-rejected",
                        "title": r.get("title") or "",
                        "company": r.get("company") or "",
                        "city": r.get("city") or "",
                        "plz": "",
                        "date_posted": "",
                        "url": r.get("url") or "",
                        "employment_raw": "",
                        "external_id": "",
                        "description": "",
                        "geo_tier": f"portal-rejected:{r.get('filter_reason', '')}",
                        "query": "",
                    })
            except Exception as e:
                print(f"  skip {fn}: {e}")
        elif fn.endswith(".csv"):
            try:
                for r in csv.DictReader(open(p, encoding="utf-8-sig")):
                    rows.append({
                        "source": r.get("source") or fn.split("_")[0],
                        "title": r.get("title") or "",
                        "company": r.get("company") or "",
                        "city": r.get("city") or "",
                        "plz": str(r.get("plz") or ""),
                        "date_posted": (r.get("date_posted") or "")[:10],
                        "url": r.get("url") or "",
                        "employment_raw": r.get("employment_raw") or r.get("contract_type") or "",
                        "external_id": r.get("refnr") or r.get("external_id") or "",
                        "description": (r.get("description") or r.get("snippet") or "")[:6000],
                        "geo_tier": "portal",
                        "query": "",
                    })
            except Exception as e:
                print(f"  skip {fn}: {e}")
    # today's daily CSV (14d pull already ran this morning)
    daily = (f"{BASE}/download/daily/2026-10-30/"
             "jobs_fachinformatiker-systemintegration-erlangen-50km-14d_20261030-0706.csv")
    if os.path.exists(daily):
        for r in csv.DictReader(open(daily, encoding="utf-8-sig")):
            rows.append({
                "source": r.get("source") or "daily",
                "title": r.get("title") or "", "company": r.get("company") or "",
                "city": r.get("city") or "", "plz": str(r.get("plz") or ""),
                "date_posted": (r.get("date_posted") or "")[:10],
                "url": r.get("url") or "",
                "employment_raw": r.get("employment_raw") or "",
                "external_id": r.get("refnr") or "",
                "description": (r.get("snippet") or "")[:6000],
                "geo_tier": "daily-14d", "query": "",
            })
    return rows


def url_key(u):
    u = (u or "").split("?")[0].rstrip("/")
    u = re.sub(r"-\d{6,}$", "", u)          # jobspy trailing ids
    return u.lower()


def comp_norm(c):
    c = norm_txt(c)
    for suffix in (" gmbh", " co kg", " kg", " ag", " se", " ug", " mbh"):
        c = c.replace(suffix, " ")
    return re.sub(r"\s+", " ", c).strip()


def stage_merge():
    ba = json.load(open(f"{DATA}/ba_bulk.json", encoding="utf-8"))
    portals = load_portal_rows()
    print(f"BA bulk={len(ba)}  portal+daily rows={len(portals)}")
    rows = ba + portals

    # ---- dedupe: URL key first, then fuzzy (norm title + comp_norm + city)
    seen_url, seen_fuzzy, final = set(), set(), []
    for r in rows:
        if not r["title"]:
            continue
        uk = url_key(r["url"])
        fk = (norm_txt(r["title"])[:60], comp_norm(r["company"]), norm_txt(r["city"]))
        if uk and uk in seen_url:
            continue
        if uk:
            seen_url.add(uk)
        if fk in seen_fuzzy:
            continue
        seen_fuzzy.add(fk)
        r["relevant"] = bool(RELEVANT_RE.search(r["title"]))
        r["junior_class"] = classify(r)
        final.append(r)

    from collections import Counter
    print(f"MASTER unique={len(final)}")
    print("by source:", dict(Counter(r["source"] for r in final).most_common()))
    print("junior classes:", dict(Counter(r["junior_class"] for r in final)))
    print("relevant:", sum(1 for r in final if r["relevant"]))

    # freshness bucket (date_posted = FIRST publication on BA; old first-pub
    # rows are still live long-running postings, typical for junior roles)
    def fresh(d):
        if not d:
            return "unknown"
        if d >= "2026-10-01": return "0-30d"
        if d >= "2026-08-01": return "31-90d"
        return "90d+ (long-running, live)"
    for r in final:
        r["freshness"] = fresh(r["date_posted"])

    # ---- outputs
    outdir = f"{BASE}/download/mega_sweep_2026-10-30"
    os.makedirs(outdir, exist_ok=True)
    cols = ["source", "geo_tier", "junior_class", "relevant", "freshness",
            "date_posted", "title", "company", "city", "plz", "employment_raw", "url", "query"]
    master_csv = f"{outdir}/master_ALL_{TS}.csv"
    with open(master_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        rows_sorted = sorted(final, key=lambda x: x["date_posted"] or "", reverse=True)
        rows_sorted.sort(key=lambda x: (x["junior_class"] not in ("strong", "medium"),
                                        x["relevant"] is False))
        for r in rows_sorted:
            w.writerow(r)
    json.dump(final, open(f"{outdir}/master_ALL_{TS}.json", "w", encoding="utf-8"),
              ensure_ascii=False)

    junior = [r for r in final if r["relevant"] and r["junior_class"] in ("strong", "medium")]
    junior.sort(key=lambda x: x["date_posted"] or "", reverse=True)   # newest first
    junior.sort(key=lambda x: 0 if x["junior_class"] == "strong" else 1)  # stable: strong first
    jcols = ["junior_class", "freshness", "date_posted", "title", "company", "city", "plz",
             "source", "employment_raw", "url"]
    short_csv = f"{outdir}/junior_shortlist_{TS}.csv"
    with open(short_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=jcols, extrasaction="ignore")
        w.writeheader()
        w.writerows(junior)

    # ---- absorb into job memory
    try:
        from pipeline.core import Job
        from pipeline import history
        jobs = [Job(source=r["source"], title=r["title"], company=r["company"],
                    city=r["city"], plz=str(r.get("plz") or ""), date_posted=r["date_posted"],
                    url=r["url"], employment_raw=r.get("employment_raw") or "",
                    external_id=r.get("external_id") or "") for r in final]
        hist = history.update(jobs)
        print("history update:", {k: hist[k] for k in list(hist)[:6]})
    except Exception as e:
        print("history update skipped:", e)

    # ---- summary md
    total = len(final)
    strong = sum(1 for r in final if r["junior_class"] == "strong")
    medium = sum(1 for r in final if r["junior_class"] == "medium")
    weak = sum(1 for r in final if r["junior_class"] == "weak")
    excl = sum(1 for r in final if r["junior_class"] == "excluded")
    rel = sum(1 for r in final if r["relevant"])
    by_src = Counter(r["source"] for r in final)
    jr_rel = Counter(r["source"] for r in junior)
    md = f"""# Mega Sweep - insanely large job search, junior-filtered ({TS[:8]})

## Funnel
| Stage | n |
|---|---|
| Raw rows fetched (BA bulk + portals + daily) | {len(rows)} |
| **Master unique postings** | **{total}** |
| FISI-relevant titles | {rel} |
| Junior strong (title-level) | {strong} |
| Junior medium (description-level) | {medium} |
| Junior weak (vague 'Einstieg') | {weak} |
| Excluded (senior/ausbildung/praktikum/manager) | {excl} |
| **Junior shortlist (relevant AND strong/medium)** | **{len(junior)}** |

## Sources (master)
{chr(10).join(f'- {s}: {n}' for s, n in by_src.most_common())}

## Junior shortlist by source
{chr(10).join(f'- {s}: {n}' for s, n in jr_rel.most_common())}

## Freshness (master; BA date_posted = FIRST publication)
{chr(10).join(f'- {k}: {v}' for k, v in Counter(r['freshness'] for r in final).most_common())}

NOTE: postings with first publication >90 days ago are still live (BA's 90-day
filter applies to the current publication period, employers keep the same
reference number running). Long-running junior postings usually mean the
employer is genuinely struggling to fill them - prime targets.

## Files
- master_ALL_{TS}.csv / .json - every unique posting with junior_class + relevant flags
- junior_shortlist_{TS}.csv - {len(junior)} rows, ranked (strong first, newest first)

## Method
- BA Jobsuche v6 bulk: {len(QUERIES)} IT queries x 2 geo-tiers (Erlangen 50 km,
  Nuernberg 100 km), veroeffentlichtseit={DAYS} days, angebotsart=1 (no Ausbildung),
  pav=false (no agencies), 100/page until exhaustion.
- BA v4 jobdetails deep-fetch for every non-excluded candidate (description-level
  entry signals).
- Wide portal run via pipeline fetch (30-day window, Nuernberg 100 km, 20 sources).
- Dedupe: canonical URL + fuzzy (title/company/city). Classification: the proven
  pull_fisi_junior regexes + description signal scan.
"""
    open(f"{outdir}/mega_sweep_summary_{TS}.md", "w", encoding="utf-8").write(md)
    print(f"\nOUTPUTS in {outdir}: master_ALL_{TS}.csv/.json, "
          f"junior_shortlist_{TS}.csv ({len(junior)} rows), summary md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["ba", "enrich", "portals", "merge"])
    args = ap.parse_args()
    {"ba": stage_ba, "enrich": stage_enrich,
     "portals": stage_portals, "merge": stage_merge}[args.stage]()
