#!/usr/bin/env python3
"""Production pull #1: FISI / junior-first-job postings, Erlangen +50 km, last 14 days.
Sources: BA Jobsuche v6 (exact radius), JobSpy->Indeed DE + LinkedIn guest, Arbeitnow.
Read-only, low volume, no credentials. Output: merged CSV sorted by date desc."""
import json, re, time, datetime, unicodedata, io, sys, csv

BASE = "/home/z/my-project"
OUT_CSV = f"{BASE}/download/fisi_junior_erlangen50km_last14d.csv"
CUTOFF = datetime.date.today() - datetime.timedelta(days=14)
DAYS = 14
RADIUS = 50

# ---------- helpers ----------
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
RELEVANT_RE = re.compile(
    r"(?i)fachinformatiker|systemintegration|system ?integrat|system ?administrator|"
    r"systemadministrator|it-?(support|admin|servic|techniker|mitarbeiter|spezialist|referent|"
    r"berater|allrounder)|\bit ?support|\bit ?admin|informatiker|first ?level|1st ?level|"
    r"anwenderbetreuung|anwendungsbetreuung|client ?manager|edv|\bit ?manager|\bit ?team|"
    r"server ?admin|it-?infrastruktur|telematikinfrastruktur|rechenzentrum|client ?management|"
    r"\bit ?techniker|\bit ?berater")

def is_excluded(title):
    t = title or ""
    if re.search(r"(?i)\bjunior\b|\bberufseinsteiger", t) and not re.search(
            r"(?i)ausbildung|azubi|praktik|werkstudent", t):
        return False  # explicit junior always kept
    if re.search(r"(?i)\breferent", t) and not re.search(r"(?i)it[- ]?referent", t):
        return True  # civil-service Referent = experienced; keep only IT-Referent
    if re.search(r"(?i)\bexpert", t):
        return True  # Experte = senior track
    return bool(EXCLUDE_RE.search(t))

CITY_ALIAS = {"nuremberg": "Nürnberg", "nuernberg": "Nürnberg", "fuerth": "Fürth",
              "nuremberg metropolitan area": "Nürnberg", "greater nuremberg metropolitan area": "Nürnberg",
              "nuremberg, bavaria, germany": "Nürnberg"}

def city_canon(city):
    if not city: return ""
    c = re.sub(r",\s*(mittelfranken|oberfranken|oberpfalz|unterfranken|schwaben|bayern|"
               r"bavaria|BY|deutschland).*$", "", city.strip(), flags=re.I)
    for k, v in CITY_ALIAS.items():
        if c.lower() == k: return v
    return c

# strict 50-km whitelist around Erlangen (VGN rail towns + suburbs, from research/2-e)
NEAR_RE = re.compile(
    r"(?i)erlangen|f(u|ü)rth|n(u|ue)?rnberg|nuremberg|herzogenaurach|baiersdorf|forchheim|"
    r"h(o|oe)chstadt|gremsdorf|adelsdorf|hemhofen|buckenhof|spardorf|uttenreuth|m(o|oe)hrendorf|"
    r"bubenreuth|dachsbach|weisendorf|grossenseebach|he(ß|ss)dorf|gerhardshofen|kalchreuth|"
    r"eckental|eschenau|gr(a|ae)fenberg|hiltpoltstein|simmelsdorf|schnaittach|neunkirchen am sand|"
    r"hersbruck|lauf( an)? der pegnitz|r(o|oe)thenbach( an)? der pegnitz|winkelhaid|schwarzenbruck|"
    r"feucht|wendelstein|altdorf( bei n(u|ue)rnberg)?|schwabach|rednitzhembach|zirndorf|\bvach\b|"
    r"oberasbach|\bstein\b|bamberg|hallstadt|biegenhof?|pretzfeld|ebermannstadt|g(o|oe)(ß|ss)weinstein|"
    r"pottenstein|neumarkt( in der oberpfalz)?")

def parse_date(v):
    if v in (None, "", "NaN"): return None
    if isinstance(v, (int, float)):
        ts = float(v)
        if abs(ts) > 1e11: ts /= 1000.0  # epoch millis (jobspy to_json)
        try: return datetime.date.fromtimestamp(ts)
        except Exception: return None
    s = str(v)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try: return datetime.date.fromisoformat(m.group(1))
        except Exception: return None
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None

jobs = {}  # dedupe key -> record

def add(src, refnr, title, company, city, plz, date, url, smin, smax, cur, remote, extra=""):
    if not title or not company: return
    if not RELEVANT_RE.search(title): return
    if is_excluded(title): return
    d = parse_date(date)
    if d and d < CUTOFF: return
    city = city_canon(city)
    key = (norm_txt(company), norm_txt(title), norm_txt(city or ""))
    rec = {"date_posted": d.isoformat() if d else "", "title": title.strip(),
           "company": company.strip(), "city": city.strip(),
           "plz": str(plz or ""), "source": src, "salary_min": smin or "",
           "salary_max": smax or "", "currency": cur or "", "remote": "yes" if remote else "",
           "url": url or "", "refnr": refnr or "", "junior_signal": "yes" if JUNIOR_RE.search(title) else "",
           "note": extra}
    if key in jobs:
        old = jobs[key]
        old["source"] = "+".join(sorted(set(old["source"].split("+")) | {src}))
        if (d or datetime.date.min) > (parse_date(old["date_posted"]) or datetime.date.min):
            old["date_posted"] = rec["date_posted"]
            old["url"] = url or old["url"]
        if rec["salary_min"]: old["salary_min"] = rec["salary_min"]
        if rec["salary_max"]: old["salary_max"] = rec["salary_max"]
        if rec["junior_signal"]: old["junior_signal"] = "yes"
    else:
        jobs[key] = rec

# ---------- 1) BA Jobsuche v6 ----------
def pull_ba():
    import requests
    H = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "jobhunt-research/1.0"}
    terms = ["Fachinformatiker", "Systemintegration", "Systemadministrator",
             "IT-Systemadministrator", "IT-Support", "IT-Referent"]
    seen_ref = set()
    for term in terms:
        for page in (1, 2):
            url = ("https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
                   f"?was={term}&wo=Erlangen&umkreis={RADIUS}&veroeffentlichtseit={DAYS}"
                   f"&angebotsart=1&pav=false&size=100&page={page}")
            try:
                r = requests.get(url, headers=H, timeout=30)
                if r.status_code != 200:
                    print(f"BA '{term}' p{page}: HTTP {r.status_code}"); break
                data = r.json()
            except Exception as e:
                print(f"BA '{term}' p{page}: ERR {e}"); break
            sts = data.get("ergebnisliste") or []
            print(f"BA '{term}' p{page}: {len(sts)} (total {data.get('maxErgebnisse')})")
            for s in sts:
                refnr = s.get("referenznummer")
                if not refnr or refnr in seen_ref: continue
                seen_ref.add(refnr)
                locs = s.get("stellenlokationen") or [{}]
                o = (locs[0].get("adresse") or {})
                dist = s.get("entfernung")
                add(src="BA", refnr=refnr, title=s.get("stellenangebotsTitel"),
                    company=s.get("firma"), city=o.get("ort"), plz=o.get("plz"),
                    date=s.get("datumErsteVeroeffentlichung")
                         or (s.get("veroeffentlichungszeitraum") or {}).get("von"),
                    url="https://www.arbeitsagentur.de/jobsuche/jobdetail/" + refnr,
                    smin=None, smax=None, cur=None, remote=False,
                    extra=f"BA {dist}km" if dist else "BA")
            if len(sts) < 100: break
            time.sleep(1.5)
        time.sleep(1.5)

# ---------- 2) JobSpy: Indeed DE + LinkedIn guest ----------
def pull_jobspy():
    vpy = f"{BASE}/.venv-jobspy/bin/python"
    import subprocess, textwrap, os
    cache = "/tmp/jobspy_pull.json"
    fresh = os.path.exists(cache) and (time.time() - os.path.getmtime(cache)) < 3600
    if not fresh:
        code = textwrap.dedent("""
        import json, sys
        from jobspy import scrape_jobs
        out = []
        def grab(tag, **kw):
            try:
                df = scrape_jobs(**kw)
                keep = ["title","company","location","date_posted","min_amount","max_amount",
                        "currency","is_remote","job_url","description"]
                df = df[[c for c in keep if c in df.columns]]
                out.append({"tag": tag, "rows": json.loads(df.to_json(orient="records"))})
                print(f"{tag}: {len(df)} rows", file=sys.stderr)
            except Exception as e:
                print(f"{tag}: FAIL {type(e).__name__}: {str(e)[:160]}", file=sys.stderr)
        for term in ["Fachinformatiker", "IT-Support", "Systemadministrator", "IT-Systemadministrator"]:
            grab(f"indeed_{term}", site_name=["indeed"], search_term=term,
                 location="Erlangen, Bayern", results_wanted=60, hours_old=336,
                 country_indeed="germany")
        grab("indeed_fisi_nbg", site_name=["indeed"], search_term="Fachinformatiker Systemintegration",
             location="Nürnberg, Bayern", results_wanted=60, hours_old=336, country_indeed="germany")
        for term in ["Systemintegration", "IT-Support"]:
            grab(f"li_{term}", site_name=["linkedin"], search_term=term,
                 location="Erlangen, Bavaria", results_wanted=40, hours_old=336)
        json.dump(out, open("/tmp/jobspy_pull.json", "w"))
    """)
        subprocess.run([vpy, "-c", code], check=False, timeout=420)
    else:
        print("jobspy: using cache <1h old")
    try:
        for block in json.load(open("/tmp/jobspy_pull.json")):
            tag = block["tag"]; src = "Indeed" if tag.startswith("indeed") else "LinkedIn"
            for row in block["rows"]:
                loc = row.get("location") or ""
                m = re.search(r"\b(\d{5})\b", loc)
                city = re.split(r",", loc)[0].strip()
                # strict 50-km whitelist (Indeed/LinkedIn default radius is wider)
                if not NEAR_RE.search(loc): continue
                add(src=src, refnr="", title=row.get("title"), company=row.get("company"),
                    city=city, plz=m.group(1) if m else "", date=row.get("date_posted"),
                    url=row.get("job_url"), smin=row.get("min_amount"), smax=row.get("max_amount"),
                    cur=row.get("currency"), remote=bool(row.get("is_remote")), extra=tag)
    except FileNotFoundError:
        print("jobspy output missing")

# ---------- 3) Arbeitnow (no key, client-side geo filter) ----------
def pull_arbeitnow():
    import requests
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=30,
                         headers={"User-Agent": "jobhunt-research/1.0"})
        data = r.json().get("data", [])
        print(f"Arbeitnow: {len(data)} rows")
        for j in data:
            loc = j.get("location") or ""
            if not NEAR_RE.search(loc):
                continue
            add(src="Arbeitnow", refnr="", title=j.get("title"), company=j.get("company_name"),
                city=re.split(r"[,(]", loc)[0].strip(), plz="",
                date=datetime.datetime.fromtimestamp(j.get("created_at", 0),
                                                     datetime.timezone.utc).date().isoformat()
                     if j.get("created_at") else "",
                url=j.get("url"), smin=None, smax=None, cur=None,
                remote=bool(j.get("remote")), extra=j.get("slug") or "")
    except Exception as e:
        print(f"Arbeitnow ERR: {e}")

# ---------- run ----------
pull_ba()
pull_jobspy()
pull_arbeitnow()

recs = sorted(jobs.values(),
              key=lambda r: r["date_posted"], reverse=True)  # '' sorts last

# near-dupe merge: same title+city, companies share a token (Funkwerk AG vs Funkwerk Systems GmbH)
def _tok(c): return set(re.findall(r"[a-z]{4,}", norm_txt(c)))
final = []
for r in recs:
    hit = None
    for o in final:
        if norm_txt(o["title"]) == norm_txt(r["title"]) and o["city"] == r["city"] \
                and _tok(o["company"]) & _tok(r["company"]):
            hit = o; break
    if hit:
        hit["source"] = "+".join(sorted(set(hit["source"].split("+")) | set(r["source"].split("+"))))
        if r["date_posted"] > hit["date_posted"]: hit["date_posted"] = r["date_posted"]
        if r["salary_min"]: hit["salary_min"] = r["salary_min"]
        if r["salary_max"]: hit["salary_max"] = r["salary_max"]
        if r["junior_signal"]: hit["junior_signal"] = "yes"
    else:
        final.append(r)
recs = final
cols = ["date_posted", "title", "company", "city", "plz", "source", "salary_min",
        "salary_max", "currency", "remote", "junior_signal", "url", "refnr", "note"]
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(recs)

print(f"\n=== MERGED: {len(recs)} postings -> {OUT_CSV}")
from collections import Counter
print("by source:", dict(Counter(r["source"] for r in recs)))
print("by city:", dict(Counter(r["city"] for r in recs).most_common(8)))
print("junior_signal:", sum(1 for r in recs if r["junior_signal"]))
print("\n--- first 25 (date desc) ---")
for r in recs[:25]:
    print(f"{r['date_posted'] or '????-??-??'} | {r['title'][:58]:<58} | "
          f"{r['company'][:28]:<28} | {r['city'][:18]:<18} | {r['source']}")
