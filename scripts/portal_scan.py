#!/usr/bin/env python3
"""portal_scan.py — German job portal discovery + live liveness probe.
Builds a seed catalog (~170 portals, 12 categories) and probes each one
concurrently: HTTP status, WAF/block detection, title, redirect target.
Output: data/portals/portal_scan_<ts>.json + .csv
"""
import concurrent.futures as cf
import csv, json, re, ssl, sys, time
from datetime import datetime
from urllib.parse import urlparse
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7"}

# name, url, category, access_hint, note, in_pipeline
SEEDS = [
 # ---------- GENERALISTS ----------
 ("Indeed DE", "https://de.indeed.com", "generalist", "html/WAF", "Largest aggregator; guest pages blocked by WAF", "yes (1,977 harvested)"),
 ("LinkedIn Jobs", "https://www.linkedin.com/jobs", "generalist", "js/guest-api", "Guest API rate-limited", "yes (1,848 harvested)"),
 ("XING Jobs", "https://www.xing.com/jobs/search", "generalist", "js", "DACH network; API needs OAuth", ""),
 ("StepStone", "https://www.stepstone.de", "generalist", "WAF", "Big board; heavy bot protection", ""),
 ("Monster DE", "https://www.monster.de", "generalist", "html", "Post-merger status unclear", "probed r7"),
 ("Glassdoor DE", "https://www.glassdoor.de", "generalist", "WAF", "Indeed-group; hard bot wall", ""),
 ("kimeta.de", "https://www.kimeta.de", "generalist", "html+proxy", "Meta-search 1.1M+ ads; proxy mandatory", "yes (via proxy pool)"),
 ("Jobware", "https://www.jobware.de", "generalist", "html", "Specialists/execs; 400 partner platforms", ""),
 ("JobScout24", "https://www.jobscout24.de", "generalist", "html", "Classic board", "probed r7"),
 ("meinestadt.de Jobs", "https://jobs.meinestadt.de", "generalist", "html", "450k+ regional ads", "probed r7"),
 ("Jobboerse.de", "https://www.jobboerse.de", "generalist", "html", "1.7M ads incl. 180k Ausbildungsplaetze", ""),
 ("Stellenanzeigen.de", "https://www.stellenanzeigen.de", "generalist", "html", "75 regional job markets network", ""),
 ("Stellenmarkt.de", "https://www.stellenmarkt.de", "generalist", "html", "Qualified specialists", "probed r7"),
 ("Jobs.de", "https://www.jobs.de", "generalist", "html", "", ""),
 ("Jobboerse.com", "https://www.jobboerse.com", "generalist", "html", "", ""),
 ("Stellenboerse.de", "https://www.stellenboerse.de", "generalist", "html", "", ""),
 ("Gigajob", "https://www.gigajob.com", "generalist", "html", "Free classifieds job board", ""),
 ("Kleinanzeigen.de Jobs", "https://www.kleinanzeigen.de/s-jobs", "generalist", "html", "Classifieds (ex-eBay Kleinanzeigen)", ""),
 ("Quoka Jobs", "https://www.quoka.de/jobs", "generalist", "html", "Classifieds", ""),
 ("FAZJOB.NET", "https://www.fazjob.net", "generalist", "html", "FAZ group; specialists/execs", ""),
 ("SZ Jobs", "https://jobs.sueddeutsche.de", "generalist", "html", "Sueddeutsche Zeitung; strong in Bavaria/BW", ""),
 ("ZEIT Jobs", "https://jobs.zeit.de", "generalist", "html/rss", "ZEIT group", ""),
 ("karriere.de", "https://www.karriere.de", "generalist", "html", "Handelsblatt Media group", ""),
 ("Tagesspiegel Jobs", "https://jobs.tagesspiegel.de", "generalist", "html", "", ""),
 ("t3n Jobs", "https://t3n.de/jobs", "generalist", "html", "Digital/tech/marketing magazine board", ""),
 ("heise Jobs", "https://jobs.heise.de", "generalist", "html", "Tech magazine board", ""),
 ("Golem Jobs", "https://www.golem.de/jobs", "generalist", "html", "Tech magazine board", ""),
 ("Jobworld", "https://www.jobworld.de", "generalist", "html", "", "probed r7"),
 ("Kalaydo Jobs", "https://www.kalaydo.de/jobs", "generalist", "html", "Legacy Cologne portal", "probed r7 (dead?)"),
 # ---------- PUBLIC / GOV ----------
 ("BA Jobboerse", "https://www.arbeitsagentur.de/jobsuche", "public", "api", "Official federal job board; open REST API", "yes (core source)"),
 ("EURES", "https://eures.europa.eu/jobs-search", "public", "api", "EU-wide; JSON search endpoint", "yes"),
 ("Interamt", "https://www.interamt.de/koop/app/", "public", "html", "Federal public-sector career portal (Bund)", ""),
 ("Make it in Germany", "https://www.make-it-in-germany.com/en/working-in-germany/job-listings", "public", "js", "Federal portal for international skilled workers", ""),
 ("Berlin.de Jobs", "https://www.berlin.de/jobs/", "public", "html", "City/state portal incl. public sector", ""),
 ("oeffentlicher-dienst.info", "https://www.oeffentlicher-dienst.info", "public", "html", "Public service info + job listings", ""),
 ("Stellenwerk", "https://www.stellenwerk.de", "public", "html", "University job boards network (HH/MUC/HH...)", ""),
 ("academics.de", "https://www.academics.de", "public", "html", "Science/research/academia (Zeit group)", ""),
 ("jobvector", "https://www.jobvector.de", "public", "html", "STEM/medicine/science; Bayer/Siemens/Airbus", ""),
 ("Bundeswehr Karriere", "https://www.bundeswehr.de/karriere", "public", "html", "Own career portal", ""),
 ("Kirchenjobs", "https://www.kirchenjobs.de", "public", "html", "Church/charity sector", ""),
 # ---------- TECH / IT ----------
 ("Get in IT", "https://www.get-in-it.de", "tech", "html", "IT juniors/graduates", "yes"),
 ("Get in Engineering", "https://www.get-in-engineering.de", "tech", "html", "Engineering students/graduates", ""),
 ("GermanTechJobs", "https://germantechjobs.de", "tech", "html", "IT jobs with salary/stack transparency", ""),
 ("Berlin Startup Jobs", "https://berlinstartupjobs.com", "tech", "html", "Berlin startup scene incl. IT support roles", ""),
 ("startup.jobs", "https://startup.jobs", "tech", "js", "Global startup board, DE filter", ""),
 ("Wellfound", "https://wellfound.com/jobs", "tech", "js", "ex-AngelList Talent", "probed r7"),
 ("Welcome to the Jungle", "https://www.welcometothejungle.com/en/jobs", "tech", "js", "ex-Otta; DE section", "probed r7"),
 ("Instaffo", "https://www.instaffo.com", "tech", "js", "AI matching job network", ""),
 ("ITsax.de", "https://www.itsax.de", "tech", "html", "IT specialists/execs, active since 2003", ""),
 ("ITmitte.de", "https://www.itmitte.de", "tech", "html", "IT jobs + forum + network", ""),
 ("Stack Overflow Jobs", "https://stackoverflow.com/jobs", "tech", "html", "Likely discontinued", ""),
 ("Jobicy", "https://jobicy.com", "tech", "html/api", "Remote tech + RSS/API", "probed r7"),
 ("Joberty", "https://joberty.com", "tech", "html", "Dev community job board", ""),
 ("EnglishJobs.de", "https://www.englishjobs.de", "tech", "html", "English-language DE jobs", "probed r7"),
 # ---------- FREELANCE ----------
 ("freelancermap", "https://www.freelancermap.de", "freelance", "html", "Largest DE freelance market", ""),
 ("GULP", "https://www.gulp.de", "freelance", "html", "SAP/engineering freelance (Randstad group)", ""),
 ("freelance.de", "https://www.freelance.de", "freelance", "html", "", ""),
 ("projektwerk", "https://www.projektwerk.de", "freelance", "html", "Project/freelance marketplace", ""),
 ("Malt.de", "https://www.malt.de", "freelance", "js", "", ""),
 ("twago", "https://www.twago.com", "freelance", "html", "", ""),
 ("Uplink", "https://uplink.io", "freelance", "html", "IT freelancers", ""),
 ("COMUNDO", "https://comundo.com", "freelance", "js", "ex-COMATCH consulting marketplace", ""),
 # ---------- JUNIOR / AUSBILDUNG ----------
 ("Absolventa", "https://www.absolventa.de", "junior", "html", "Entry-level/graduate focus", ""),
 ("ausbildung.de", "https://www.ausbildung.de", "junior", "html", "Apprenticeships", ""),
 ("Azubiyo", "https://www.azubiyo.de", "junior", "html", "Ausbildung/Dual study", ""),
 ("Azubi.de", "https://www.azubi.de", "junior", "html", "Redirect target of ausbildung.de?", ""),
 ("IHK Lehrstellenboerse", "https://www.ihk-lehrstellenboerse.de", "junior", "html", "IHK apprenticeship exchange", ""),
 ("Lehrstellen-Radar", "https://www.lehrstellen-radar.de", "junior", "html/app", "IHK/DIHK apprenticeship radar", ""),
 ("Praktikum.info", "https://www.praktikum.info", "junior", "html", "Internships/working students/trainees", ""),
 ("StudentJob DE", "https://www.studentjob.de", "junior", "html", "Student/mini jobs", ""),
 ("JobTeaser", "https://www.jobteaser.com", "junior", "js", "University-embedded boards", ""),
 ("Berufsstart.de", "https://www.berufsstart.de", "junior", "html", "Graduate portal", ""),
 ("Ausbildungsatlas", "https://www.ausbildungsatlas.de", "junior", "html", "", ""),
 ("Ausbildungspark", "https://www.ausbildungspark.com", "junior", "html", "", ""),
 # ---------- REGIONAL ----------
 ("InFranken.de Jobs", "https://www.infranken.de/jobs", "regional", "html", "Franconia (Erlangen/Nuernberg/Bamberg)", "yes (core regional)"),
 ("Regio-Jobanzeiger", "https://www.regiojobanzeiger.de", "regional", "html", "NRW/Rhineland-Palatinate/Hessen SMEs", ""),
 ("Nordbayern Jobs", "https://www.nordbayern.de/jobs", "regional", "html", "NN/NZ publisher, North Bavaria", ""),
 ("RegioJobs-NI", "https://www.regiojobs-ni.de", "regional", "html", "Lower Saxony specialists", ""),
 ("Yourfirm", "https://www.yourfirm.de", "regional", "html", "Mittelstand only (<5,000 employees)", ""),
 ("jobs-in-franken", "https://www.jobs-in-franken.de", "regional", "html", "", ""),
 ("Frankenjobs", "https://www.frankenjobs.de", "regional", "html", "", ""),
 ("Munich Startup Jobs", "https://www.munich-startup.de/jobs", "regional", "html", "Munich startup board", ""),
 ("muenchen.de Jobs", "https://www.muenchen.de/jobs", "regional", "html", "City portal", ""),
 ("Karriere-Hamburg", "https://www.karriere-hamburg.de", "regional", "html", "Hamburg regional portal", ""),
 ("Karriere-Bremen", "https://www.karriere-bremen.de", "regional", "html", "Bremen regional portal", ""),
 ("Jobboerse Bayern", "https://www.jobboerse.bayern", "regional", "html", "", ""),
 # ---------- AGGREGATORS / META ----------
 ("Jooble DE", "https://de.jooble.org", "aggregator", "html/api-key", "Aggregator; API needs free key", ""),
 ("Careerjet DE", "https://www.careerjet.de", "aggregator", "html/api-key", "Affiliate search API", ""),
 ("Adzuna DE", "https://www.adzuna.de", "aggregator", "html/api-key", "Open API with free key", ""),
 ("Talent.com DE", "https://de.talent.com", "aggregator", "html/api-key", "ex-Neuvoo", ""),
 ("Jobrapido DE", "https://de.jobrapido.com", "aggregator", "html", "", ""),
 ("Jobijoba DE", "https://www.jobijoba.de", "aggregator", "html", "", ""),
 ("Trovit DE", "https://www.trovit.de", "aggregator", "html", "", ""),
 ("WhatJobs DE", "https://de.whatjobs.com", "aggregator", "html", "", ""),
 ("JobisJob DE", "https://www.jobisjob.de", "aggregator", "html", "", "probed r7"),
 ("Jobleads DE", "https://www.jobleads.de", "aggregator", "html", "", ""),
 ("Jobsora DE", "https://de.jobsora.com", "aggregator", "html", "Low-trust scraper aggregator", ""),
 ("Joblift", "https://joblift.de", "aggregator", "html", "Meta-search; shut down ~2023?", ""),
 ("Jobninja", "https://jobninja.com", "aggregator", "js", "", "probed r7"),
 ("Jobspotting", "https://www.jobspotting.com", "aggregator", "html", "Likely defunct", ""),
 # ---------- STAFFING AGENCIES (direct boards) ----------
 ("Randstad DE", "https://www.randstad.de/jobs/", "staffing", "js", "Large agency board", ""),
 ("Adecco DE", "https://www.adecco.de/jobs/", "staffing", "js", "", ""),
 ("Hays DE", "https://www.hays.de/jobs/", "staffing", "js", "IT staffing", ""),
 ("Manpower DE", "https://www.manpower.de/jobs/", "staffing", "html", "", ""),
 ("Brunel DE", "https://www.brunel.de/de/jobs", "staffing", "html", "Seen in corpus (BA ads)", "enrichment-seen"),
 ("DIS AG", "https://www.dis-ag.com", "staffing", "js", "Skilled trades/IT staffing", ""),
 ("Hofmann Personal", "https://www.hofmann-personal.de", "staffing", "html", "", ""),
 ("Amadeus Fire", "https://www.amadeus-fire.de", "staffing", "html", "", ""),
 ("persona service", "https://www.persona.de", "staffing", "html", "", ""),
 ("Trenkwalder DE", "https://www.trenkwalder.com/de/", "staffing", "html", "", ""),
 ("Robert Half DE", "https://www.roberthalf.de/jobs", "staffing", "js", "", ""),
 ("Page Personnel DE", "https://www.pagepersonnel.de/jobs", "staffing", "js", "", ""),
 ("Experteer", "https://www.experteer.de", "staffing", "js", "Senior/executive level", ""),
 # ---------- INDUSTRY NICHES ----------
 ("Hotelcareer", "https://www.hotelcareer.de", "niche", "html", "Hospitality (StepStone group)", ""),
 ("Gastrojobs", "https://www.gastrojobs.de", "niche", "html", "", ""),
 ("Medi-Karriere", "https://www.medi-karriere.de", "niche", "html", "Medicine/health", ""),
 ("Medijobs", "https://www.medijobs.de", "niche", "html", "Healthcare", ""),
 ("Pflege.jobs", "https://pflege.jobs", "niche", "html", "Nursing/care", ""),
 ("eFinancialCareers DE", "https://www.efinancialcareers.de", "niche", "html", "Finance/IT in finance", ""),
 ("Bankjob.de", "https://www.bankjob.de", "niche", "html", "Banks/insurance/accounting", ""),
 ("Salesjob.de", "https://www.salesjob.de", "niche", "html", "Sales specialists", ""),
 ("Greenjobs.de", "https://www.greenjobs.de", "niche", "html", "Environment/renewables", ""),
 ("Handwerkerjobs.de", "https://handwerkerjobs.de", "niche", "html", "Crafts/trades", ""),
 ("Jurajobs", "https://www.jurajobs.de", "niche", "html", "Legal", ""),
 ("Pharmajobs", "https://www.pharmajobs.de", "niche", "html", "Pharma", ""),
 ("Sozialjobs", "https://www.sozialjobs.de", "niche", "html", "Social sector", ""),
 ("Mediengestalter Jobs", "https://www.mediengestalter.de/jobs", "niche", "html", "Design/creative", ""),
 # ---------- ENGLISH / EXPAT ----------
 ("The Local Jobs DE", "https://www.thelocal.de/jobs", "english", "html", "English-language DE news + jobs", ""),
 ("Toytown Germany", "https://www.toytowngermany.com/jobs", "english", "html", "Expat forum board", ""),
 ("iamexpat.de", "https://www.iamexpat.de/career/jobs", "english", "html", "Expat jobs DE", ""),
 ("InterNations", "https://www.internations.org", "english", "js", "Expat network", ""),
 ("Connexion-Emploi", "https://www.connexion-emploi.com", "english", "html", "Franco-German board since 2005", ""),
 # ---------- REMOTE ----------
 ("We Work Remotely", "https://weworkremotely.com", "remote", "html", "Largest remote board", ""),
 ("RemoteOK", "https://remoteok.com", "remote", "html/api", "Public JSON API", ""),
 ("Remotive", "https://remotive.com", "remote", "html/api", "Public API", ""),
 ("Working Nomads", "https://www.workingnomads.com/jobs", "remote", "html/api", "", ""),
 ("Remote.co", "https://remote.co/remote-jobs/", "remote", "html", "", ""),
 ("NoFluffJobs", "https://nofluffjobs.com/de", "remote", "js", "EU tech, DE filter", ""),
 ("JustJoinIT", "https://justjoin.it", "remote", "js/api", "EU tech; DE jobs", ""),
 ("FlexJobs", "https://www.flexjobs.com", "remote", "paid", "Paid membership", ""),
 ("Turing Jobs", "https://www.turing.com/jobs", "remote", "js", "Hiring marketplace", ""),
 # ---------- ATS DIRECT FEEDS (public per-company APIs) ----------
 ("Greenhouse boards", "https://boards.greenhouse.io", "ats", "public-api", "/v1/boards/{org}/jobs — direct employer data", ""),
 ("Lever", "https://jobs.lever.co", "ats", "public-api", "api.lever.co/v0/postings/{org}", ""),
 ("Ashby", "https://jobs.ashbyhq.com", "ats", "public-api", "posting-api/job-board/{org}", ""),
 ("Recruitee", "https://recruitee.com", "ats", "public-api", "{co}.recruitee.com/api/offers/", ""),
 ("Personio feeds", "https://www.personio.com", "ats", "public-xml", "{co}.jobs.personio.de/xml", ""),
 ("SmartRecruiters", "https://jobs.smartrecruiters.com", "ats", "public-api", "/v1/companies/{id}/postings", ""),
 ("Workable", "https://apply.workable.com", "ats", "public-api", "widget/accounts/{org}/jobs", ""),
 ("Softgarden", "https://jobs.softgarden.de", "ats", "xml/rss", "Per-company feeds", ""),
 ("join.com", "https://join.com", "ats", "html", "ATS job board; sitemap scrape", ""),
 ("Teamtailor", "https://www.teamtailor.com", "ats", "html", "Per-company boards", ""),
 ("d.vinci", "https://www.dvinci.de", "ats", "html", "Per-company boards", ""),
 # ---------- MISC / LEGACY PROBES ----------
 ("dein-stellenmarkt (Joblocal)", "https://www.dein-stellenmarkt.de", "misc", "html", "Regional network (Joblocal)", ""),
 ("Jobregio", "https://www.jobregio.de", "misc", "html", "", ""),
 ("Stellen.com", "https://www.stellen.com", "misc", "html", "", ""),
 ("CareerBuilder DE", "https://www.careerbuilder.de", "misc", "html", "US group; DE presence?", ""),
]

WAF_PAT = re.compile(r"Just a moment|Attention Required|Access denied|captcha|challenge-platform|cf-browser-verification", re.I)
TITLE_PAT = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)

def probe(entry):
    name, url, cat, access, note, pipe = entry
    rec = {"name": name, "url": url, "category": cat, "access_hint": access,
           "note": note, "in_pipeline": pipe or "no"}
    try:
        r = requests.get(url, headers=HDRS, timeout=(6, 9), allow_redirects=True, verify=False)
        body = r.content[:150000].decode("utf-8", "ignore")
        rec["http"] = r.status_code
        rec["final_url"] = r.url
        rec["server"] = r.headers.get("server", "")
        m = TITLE_PAT.search(body)
        rec["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:90] if m else ""
        rec["waf"] = bool(r.status_code in (403, 429, 503) or WAF_PAT.search(body[:20000]))
        if r.status_code == 200 and not rec["waf"]:
            rec["status"] = "OK"
        elif rec["waf"]:
            rec["status"] = "BLOCKED-WAF"
        elif r.status_code in (301, 302, 307, 308):
            rec["status"] = "REDIR"
        else:
            rec["status"] = f"HTTP-{r.status_code}"
    except requests.exceptions.SSLError:
        rec.update(status="SSL-ERR", http=0)
    except requests.exceptions.ConnectionError:
        rec.update(status="CONN-ERR", http=0)
    except requests.exceptions.Timeout:
        rec.update(status="TIMEOUT", http=0)
    except Exception as e:
        rec.update(status="ERR:" + type(e).__name__, http=0)
    return rec

def main():
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    import urllib3; urllib3.disable_warnings()
    results = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        for i, rec in enumerate(ex.map(probe, SEEDS, chunksize=1)):
            results.append(rec)
            if (i + 1) % 50 == 0:
                print(f"  ...probed {i+1}/{len(SEEDS)} ({time.time()-t0:.0f}s)", flush=True)
    # matrix
    from collections import Counter
    by_status = Counter(r["status"] for r in results)
    by_cat = Counter(r["category"] for r in results)
    live = [r for r in results if r["status"] == "OK"]
    blocked = [r for r in results if r["status"] == "BLOCKED-WAF"]
    print(f"\n=== PORTAL SCAN {ts}: {len(SEEDS)} portals probed in {time.time()-t0:.0f}s ===")
    print("status:", dict(by_status))
    print("categories:", dict(by_cat))
    print(f"\nOK ({len(live)}):")
    for r in live:
        print(f"  [{r['category']:9}] {r['name']:32} {r['url'][:60]}")
    print(f"\nBLOCKED-WAF ({len(blocked)}):")
    for r in blocked:
        print(f"  [{r['category']:9}] {r['name']:32} {r['url'][:60]}")
    dead = [r for r in results if r["status"] not in ("OK", "BLOCKED-WAF")]
    print(f"\nDEAD/ERR ({len(dead)}):")
    for r in dead:
        print(f"  [{r['category']:9}] {r['name']:32} {r['status']}")
    import os
    os.makedirs("/home/z/my-project/data/portals", exist_ok=True)
    jf = f"/home/z/my-project/data/portals/portal_scan_{ts}.json"
    json.dump({"ts": ts, "count": len(SEEDS), "results": results}, open(jf, "w"), ensure_ascii=False, indent=1)
    cf_path = f"/home/z/my-project/data/portals/portal_scan_{ts}.csv"
    with open(cf_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "url", "category", "access_hint", "status", "http", "waf", "title", "in_pipeline", "note"])
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    print(f"\nsaved: {jf}\nsaved: {cf_path}")

if __name__ == "__main__":
    main()
