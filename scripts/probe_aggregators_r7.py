#!/usr/bin/env python3
"""Round-7 probe: fill the aggregator catalog to 40+. One polite request per target,
evidence saved to research/aggregators-round2/probe/r7_*. Status table printed."""
import json, time, requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
      "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}
OUT = "/home/z/my-project/research/aggregators-round2/probe/"
results = []

def probe(name, method, url, save=None, **kw):
    t0 = time.time()
    try:
        r = requests.request(method, url, headers=UA, timeout=18, allow_redirects=True, **kw)
        dt = round(time.time() - t0, 1)
        body = r.text if "json" not in str(r.headers.get("content-type", "")) else r.text[:200000]
        if save:
            with open(f"{OUT}r7_{save}", "w", encoding="utf-8", errors="replace") as f:
                f.write(body[:400000])
        verdict = "OK" if r.status_code == 200 else f"HTTP{r.status_code}"
        # classify blocker
        low = body[:3000].lower()
        if r.status_code in (403, 503, 429) or "just a moment" in low or "cloudflare" in low and "challenge" in low:
            verdict += " WAF"
        if "error: the request could not be satisfied" in low:
            verdict += " CLOUDFRONT-DEAD"
        size = len(body)
        results.append((name, verdict, f"{dt}s", f"{size//1024}KB", kw.get("note", "")))
        return r
    except Exception as e:
        dt = round(time.time() - t0, 1)
        results.append((name, f"FAIL {type(e).__name__}", f"{dt}s", "-", str(e)[:90]))
        return None

# 1. Monster.de (status unknown — RIF gut? probe SERP + robots)
probe("monster.de SERP", "GET", "https://www.monster.de/jobs/suche?q=fachinformatiker&where=Erlangen", save="monster_serp.html")
probe("monster.de robots", "GET", "https://www.monster.de/robots.txt", save="monster_robots.txt")
# 2. Jobscout24.de
probe("jobscout24 SERP", "GET", "https://www.jobscout24.de/jobs?q=fachinformatiker&l=Erlangen", save="jobscout24_serp.html")
# 3. JobisJob.de
probe("jobisjob.de SERP", "GET", "https://www.jobisjob.de/fachinformatiker-erlangen-jobs", save="jobisjob_serp.html")
probe("jobisjob.de home", "GET", "https://www.jobisjob.de/", save="jobisjob_home.html")
# 4. Stellenmarkt.de
probe("stellenmarkt.de SERP", "GET", "https://www.stellenmarkt.de/stellenangebote-fachinformatiker", save="stellenmarkt_serp.html")
probe("stellenmarkt.de robots", "GET", "https://www.stellenmarkt.de/robots.txt", save="stellenmarkt_robots.txt")
# 5. meinestadt.de jobs
probe("meinestadt SERP", "GET", "https://jobs.meinestadt.de/fachinformatiker?location=Erlangen", save="meinestadt_serp.html")
probe("meinestadt robots", "GET", "https://jobs.meinestadt.de/robots.txt", save="meinestadt_robots.txt")
# 6. englishjobs.de
probe("englishjobs SERP", "GET", "https://www.englishjobs.de/de/jobs?search-term=fachinformatiker", save="englishjobs_serp.html")
# 7. Wellfound
probe("wellfound", "GET", "https://wellfound.com/jobs", save="wellfound.html")
# 8. Welcome to the Jungle (Otta)
probe("wttj", "GET", "https://www.welcometothejungle.com/de/jobs?query=fachinformatiker", save="wttj.html")
# 9. Kalaydo
probe("kalaydo", "GET", "https://www.kalaydo.de/jobs", save="kalaydo.html")
# 10. Jobninja
probe("jobninja", "GET", "https://jobninja.com/", save="jobninja.html")
# 11. Jobicy API v2 (new)
r = probe("jobicy api v2", "GET", "https://jobicy.com/api/v2/remote-jobs?count=20&industry=sysadmin", save="jobicy_v2.json")
if r is not None:
    try:
        j = r.json(); results.append(("jobicy api v2 JOBS", f"OK jobs={len(j.get('jobs', []))}", "-", "-", "JSON shape verified"))
    except Exception as e:
        results.append(("jobicy api v2 JOBS", "NOT-JSON", "-", "-", str(e)[:60]))
# 12. EURES re-verify (europa.eu host, from 2-a findings)
EURES_BODY = {"resultsPerPage": 10, "page": 1, "sortSearch": "BEST_MATCH",
              "keywords": [{"keyword": "Fachinformatiker Systemintegration", "specificSearchCode": "EVERYWHERE"}],
              "publicationPeriod": None, "occupationUris": [], "skillUris": [],
              "requiredExperienceCodes": [], "positionScheduleCodes": [], "sectorCodes": [],
              "educationAndQualificationLevelCodes": [], "positionOfferingCodes": [],
              "locationCodes": [], "euresFlagCodes": [], "otherBenefitsCodes": [], "requiredLanguages": []}
r = probe("eures search", "POST", "https://europa.eu/eures/jv-searchengine/public/jv-search/search",
          json=EURES_BODY, save="eures_r7.json")
if r is not None:
    try:
        j = r.json()
        n = j.get("numberRecords")
        results.append(("eures JOBS", f"OK numberRecords={n}", "-", "-", "jvs[] full-text in search response"))
    except Exception as e:
        results.append(("eures JOBS", "NOT-JSON", "-", "-", str(e)[:60]))
# 13. FAU jobboerse recheck
probe("fau jobboerse", "GET", "https://jobboerse.fau.de/", save="fau.html")
# 14. JOBworld search URL shape
probe("jobworld SERP", "GET", "https://www.jobworld.de/suche?q=fachinformatiker", save="jobworld_serp.html")
# 15. Kimeta one-shot recheck (SEO URL, single request)
probe("kimeta SEO URL", "GET", "https://www.kimeta.de/fachinformatiker-jobs-erlangen", save="kimeta_seo.html")

print(f"\n{'SOURCE':<24} {'VERDICT':<34} {'TIME':<7} {'SIZE':<8} NOTE")
print("-" * 100)
for row in results:
    print(f"{row[0]:<24} {row[1]:<34} {row[2]:<7} {row[3]:<8} {row[4][:60]}")
with open(OUT + "r7_summary.json", "w") as f:
    json.dump(results, f, indent=1)
print("\nsaved r7_summary.json")
