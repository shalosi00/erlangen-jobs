#!/usr/bin/env python3
"""Round-1 probe of 18 German job aggregators: reachability, tech fingerprint,
data signals (JSON-LD JobPosting / __NEXT_DATA__ / NUXT / RSS / api hints).
Saves full HTML per target into research/aggregators-round2/probe/."""
import concurrent.futures as cf
import json, os, re
import requests

BASE = "/home/z/my-project/research/aggregators-round2/probe"
os.makedirs(BASE, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
     "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}

TARGETS = {
  "kimeta":        ["https://www.kimeta.de/fachinformatiker-jobs-erlangen",
                    "https://www.kimeta.de/suche?q=fachinformatiker+erlangen"],
  "jobvector":     ["https://www.jobvector.de/suche?q=fachinformatiker&l=Erlangen",
                    "https://www.jobvector.de/jobboerse?searchterm=fachinformatiker"],
  "get-in-it":     ["https://www.get-in-it.de/jobs?keywords=fachinformatiker&locations=Erlangen",
                    "https://www.get-in-it.de/"],
  "absolventa":    ["https://www.absolventa.de/jobs?q=fachinformatiker",
                    "https://www.absolventa.de/jobs/fachinformatiker-erlangen"],
  "stellenanzeigen":["https://www.stellenanzeigen.de/fachinformatiker/erlangen/",
                     "https://www.stellenanzeigen.de/suche/?what=fachinformatiker&where=Erlangen"],
  "jobware":       ["https://www.jobware.de/jobs?jw_jobname=fachinformatiker&jw_jobort=Erlangen",
                    "https://www.jobware.de/"],
  "gigajob":       ["https://www.gigajob.com/de/suche?q=fachinformatiker&l=Erlangen",
                    "https://www.gigajob.com/de/stellenangebote-fachinformatiker-erlangen.html"],
  "jobrapido":     ["https://de.jobrapido.com/jobs?q=fachinformatiker&l=Erlangen"],
  "trovit":        ["https://de.trovit.com/jobs/fachinformatiker/erlangen",
                    "https://de.trovit.com/"],
  "careerjet-api": ["https://public.careerjet.com/search/jobs?v=2&locale_code=de_DE&keywords=fachinformatiker&location=Erlangen",
                    "https://api.careerjet.com/search?v=2&locale_code=de_DE&keywords=fachinformatiker&location=Erlangen"],
  "germantechjobs":["https://germantechjobs.de/jobs?search=fachinformatiker",
                    "https://germantechjobs.de/jobs/germany/erlangen"],
  "yourfirm":      ["https://www.yourfirm.de/job/fachinformatiker/erlangen/",
                    "https://www.yourfirm.de/stellenangebote/?keyword=fachinformatiker"],
  "interamt":      ["https://interamt.de/mpi/public/stellensuche.html",
                    "https://interamt.de/oppa-service/api/v1/stellen?page=1&size=5"],
  "berufsstart":   ["https://www.berufsstart.de/jobs/suche?q=fachinformatiker",
                    "https://www.berufsstart.de/stellenboerse/"],
  "connecticum":   ["https://www.connecticum.de/jobboerse/suche/?q=fachinformatiker",
                    "https://www.connecticum.de/jobboerse/"],
  "meinefirma":    ["https://www.meinefirma.de/jobs/fachinformatiker-erlangen",
                    "https://www.meinefirma.de/"],
  "fau-jobboard":  ["https://www.jobboerse.fau.de/jobs/?search=fachinformatiker",
                    "https://www.jobboerse.fau.de/"],
  "infranken":     ["https://www.infranken.de/stellenmarkt",
                    "https://jobs.infranken.de/jobs?searchterm=fachinformatiker"],
}

SIGS = {
 "jsonld_jobposting": re.compile(r'"@type"\s*:\s*"(JobPosting|ItemList)"'),
 "next_data":   re.compile(r'__NEXT_DATA__'),
 "nuxt":        re.compile(r'__NUXT__|window\.__NUXT__'),
 "rss_feed":    re.compile(r'<rss[\s>]|<feed[\s>]', re.I),
 "vue_app":     re.compile(r'id="app"|data-server-rendered'),
 "react_app":   re.compile(r'id="__next"|data-reactroot|id="root"'),
 "angular_app": re.compile(r'ng-version|angular'),
 "cf_challenge":re.compile(r'Just a moment|challenge-platform|cf-chl'),
 "anubis":      re.compile(r'anubis|Making sure you'),
 "api_hint":    re.compile(r'"(/api/[a-z0-9/_\-\.]{3,60})"'),
 "json_body":   re.compile(r'^\s*[\{\[]'),
}
COMPILED_SIGS = {}
for k, pat in SIGS.items():
    try:
        COMPILED_SIGS[k] = re.compile(pat.pattern if hasattr(pat, "pattern") else pat)
    except Exception:
        pass

def probe_one(args):
    name, url = args
    rec = {"name": name, "url": url}
    try:
        r = requests.get(url, headers=H, timeout=22, allow_redirects=True)
        rec["status"] = r.status_code
        rec["final_url"] = r.url[:120]
        rec["len"] = len(r.text)
        body = r.text
        if len(body) > 3_000_000:
            body = body[:3_000_000]
        fname = f"{BASE}/{name}_{url.split('//')[1].split('/')[0].replace('.', '_')}_{r.status_code}.html"
        with open(fname, "w", errors="ignore") as f:
            f.write(body)
        rec["file"] = os.path.basename(fname)
        rec["sigs"] = [k for k, rx in COMPILED_SIGS.items() if rx.search(body)]
        ct = r.headers.get("content-type", "")
        rec["ctype"] = ct.split(";")[0]
        if rec["ctype"].startswith("application/json"):
            try:
                j = r.json()
                rec["json_keys"] = list(j.keys())[:12] if isinstance(j, dict) else f"list[{len(j)}]"
            except Exception:
                pass
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:80]}"
    return rec

jobs = []
for name, urls in TARGETS.items():
    for u in urls:
        jobs.append((name, u))
results = []
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    for rec in ex.map(probe_one, jobs):
        results.append(rec)
        s = rec.get("sigs") or rec.get("error", "")
        print(f"{rec['name']:16} {rec.get('status','ERR'):>3} {rec.get('len',0):>8}B  {s}", flush=True)

with open(f"{BASE}/summary.json", "w") as f:
    json.dump(results, f, indent=1, ensure_ascii=False)
print("\nsaved ->", f"{BASE}/summary.json")
