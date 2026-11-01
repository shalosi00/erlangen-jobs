# -*- coding: utf-8 -*-
"""Report content, chapters 10-13 and appendices."""

CH10 = {
    "title": "10. The CSV Tracker Pipeline",
    "blocks": [
        ("body",
         "All components assemble into one pipeline whose output is exactly what Asha asked for: a deduplicated "
         "CSV tracker of fresh, train-reachable, FISI-relevant postings, refreshed automatically and scored so "
         "the best application targets are always at the top. The architecture is deliberately boring and "
         "debuggable: Python 3 standard library plus requests, flat files, one cron entry per source group, and "
         "no database beyond a seen-jobs store."),
        ("code", "Pipeline architecture (data flow)",
         '  cron (every 30-60 min)\n'
         '     |\n'
         '     +-- fetch_ba.py        BA API v6 keyword loop  (green)\n'
         '     +-- fetch_eures.py     EURES POST search       (green)\n'
         '     +-- fetch_arbeitnow.py page 1-3 + client filter(green)\n'
         '     +-- fetch_adzuna.py    what/where/max_days_old (green, keyed)\n'
         '     +-- fetch_ats.py       DATEV/Schaeffler/adidas/PUMA/GfK\n'
         '     |                      /Personio trio/Hetzner  (green)\n'
         '     +-- fetch_rss.py       WWR + Himalayas         (green)\n'
         '     +-- fetch_portals.py   XING SSR + LI guest     (yellow, 1-2/h)\n'
         '     |\n'
         '     v\n'
         '  normalize -> dedupe (BA refnr | URL | title+company+plz hash)\n'
         '     -> train-filter (whitelist Table 9-2)\n'
         '     -> score (freshness + keywords + salary flag + one-click)\n'
         '     -> jobs.csv (sorted) + seen.json (state)\n'
         '\n'
         '  optional: LLM scorer re-ranks top N against Asha\'s CV text'),
        ("body",
         "The polling schedule respects each source's tolerance. The BA keyword loop (19 German core and variant "
         "terms) runs hourly at one request per keyword, which is 19 requests spread over a minute - far inside "
         "any reasonable reading of intended use. Arbeitnow and the RSS suite poll hourly. Adzuna polls every "
         "two hours for fresh postings only (max_days_old=3), staying far below its 250-call daily budget. The "
         "ATS group polls every two to four hours depending on feed size; the two megabyte SuccessFactors feeds "
         "should be fetched with streaming and a conditional ETag if available. The yellow-tier portal channels "
         "run at most twice per hour, never in parallel, with jitter. Alert emails from StepStone, Indeed and "
         "meinestadt arrive daily and are ingested by a small IMAP parser so that every source lands in the "
         "same CSV."),
        ("table", {
            "headers": ["Source group", "Interval", "Requests/run", "Daily budget"],
            "ratios": [0.34, 0.16, 0.22, 0.28],
            "rows": [
                ["BA API keyword loop (19 queries)", "60 min", "19 + details", "about 480, green-tier intended use"],
                ["EURES search", "60 min", "1-2", "uncapped documented, keep low"],
                ["Arbeitnow pages 1-3", "60 min", "3", "72, trivial"],
                ["Adzuna DE fresh query", "120 min", "2", "24 of 250/day"],
                ["ATS feeds (10 employers)", "120-240 min", "10", "about 80, all green"],
                ["Remote RSS suite", "60 min", "6", "144, trivial"],
                ["XING SSR + LinkedIn guest", "30-60 min each", "2-3", "under 100 total, yellow-tier discipline"],
            ],
            "caption": "Table 10-1: Polling schedule and request budgets.",
            "bold_first": True,
        }),
        ("h3", "Scoring model"),
        ("body",
         "Every new row gets a 0-100 score from four transparent components, so Asha can tune weights without "
         "touching code internals: freshness (within 24 h starts at 40 points, decaying daily), keyword match "
         "density from the Chapter 2 term lists as matched against title plus description, location bonus from "
         "the train whitelist (zero-transfer within 40 minutes scores highest; flagged towns score mid), and "
         "friction bonuses for one-click apply support, salary transparency and homeoffice flags. Rows below a "
         "threshold of 30 are written to the CSV but marked skipped, keeping the file a complete audit trail "
         "while the daily review reads only the top segment. An optional LLM pass re-ranks the top twenty rows "
         "against Asha's CV text with a strict-JSON prompt (score plus one-line reason), which costs fractions "
         "of a cent per run and catches semantic matches that keyword counting misses, such as "
         "Client-Management postings titled as IT-Service-Techniker."),
        ("code", "Core fetcher skeleton (Python, requests only)",
         'import requests, time\n'
         'BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"\n'
         'KEY  = {"X-API-Key": "jobboerse-jobsuche"}\n'
         'KW   = ["Fachinformatiker Systemintegration", "Systemintegration",\n'
         '        "IT-Systemelektroniker", "Systembetreuer", "IT-Administrator"]\n'
         '\n'
         'def ba_search(kw, page=1):\n'
         '    r = requests.get(f"{BASE}/pc/v6/jobs", headers=KEY, params={\n'
         '        "was": kw, "wo": "Erlangen", "umkreis": 50,\n'
         '        "page": page, "size": 100,\n'
         '        "veroeffentlichtseit": 7, "angebotsart": 1}, timeout=30)\n'
         '    r.raise_for_status()\n'
         '    return r.json()["stellenangebote"]  # see field table, App. C\n'
         '\n'
         'for kw in KW:\n'
         '    rows = ba_search(kw)\n'
         '    time.sleep(3)   # polite pacing\n'
         '    # -> normalize into the shared row schema, then dedupe'),
        ("table", {
            "headers": ["CSV column", "Content", "Purpose"],
            "ratios": [0.24, 0.44, 0.32],
            "rows": [
                ["first_seen", "ISO timestamp of pipeline detection", "Speed KPI; enforce the 72 h rule"],
                ["published", "Source publication date", "Freshness score"],
                ["title", "Posting title", "Review"],
                ["company", "Employer name", "Review and dedupe"],
                ["town", "Location as posted", "Whitelist match"],
                ["train", "Direct / flagged / no", "Commute decision"],
                ["source", "BA / EURES / Arbeitnow / Adzuna / ATS:{co} / XING / LI / RSS:{name} / mail:{portal}", "Traceability and attribution"],
                ["url", "Application URL", "One click to apply"],
                ["salary", "Range when exposed (BA, XING, Adzuna)", "Prioritization"],
                ["score", "0-100 pipeline score", "Sort key"],
                ["status", "new / skipped / applied / rejected / interview", "Manual tracking column Asha edits"],
            ],
            "caption": "Table 10-2: The tracker schema. Status is the only column updated by hand.",
            "bold_first": True,
        }),
        ("body",
         "Cron wiring is three lines: a morning full run at 06:40 that also rebuilds the CSV header and a midday "
         "increment at 12:40, plus a weekly Sunday job that re-validates all source health by replaying the "
         "verification curls from this report and emails a diff summary. The seen.json state file keyed by the "
         "dedupe hash guarantees that review effort only ever goes to genuinely new rows. For Asha this means "
         "one five-minute morning ritual: open the CSV sorted by score, apply to everything above 70 with the "
         "native one-click flows, mark statuses, done."),
    ],
}

CH11 = {
    "title": "11. Portal-Native Speed Tactics",
    "blocks": [
        ("body",
         "Programmatic detection only wins applications if the apply path is fast too. This chapter is the "
         "manual half of the system: how to configure each portal's own alerting for fastest delivery, and how "
         "to keep every application to a one-to-two minute action. Everything here is free and officially "
         "supported, which makes it the safety net that keeps coverage complete even where scraping is off the table."),
        ("table", {
            "headers": ["Portal", "Alert product", "Fastest delivery", "Setup notes"],
            "ratios": [0.16, 0.24, 0.20, 0.40],
            "font": 8.4,
            "rows": [
                ["XING", "Job-Alerts (up to 4+ searches)", "Prompt/push fastest, email second",
                 "Create one alert per keyword cluster; complete profile to unlock Bewerbung in einem Klick"],
                ["StepStone", "Jobagent", "Daily digest email",
                 "Several narrow agents beat one broad one; Schnellbewerbung needs an uploaded CV since 2022"],
                ["Indeed DE", "Email alerts + app push", "Push faster than email",
                 "Alert on multiple queries; profile enables Indeed Apply"],
                ["LinkedIn", "Job alerts", "Push near-instant",
                 "Set alerts without Easy-Apply automation; guest endpoint covers detection separately"],
                ["meinestadt", "Jobagent email", "Daily", "Covers a regional audience the big portals miss"],
                ["Jobware", "Jobagent email", "Daily", "Legacy but still relevant for Bavarian Mittelstand"],
                ["BA Jobbörse", "Suchagent email", "Daily",
                 "Redundant with the API but useful as an integrity check of the pipeline"],
            ],
            "caption": "Table 11-1: Native alert matrix. Daily digests are the fallback layer; the pipeline covers real-time detection.",
            "bold_first": True,
        }),
        ("bullets", [
         "Complete every portal profile once, properly: XING and StepStone one-click flows pull straight from the profile, and incomplete profiles silently disqualify the fast path.",
         "Upload a clean PDF CV everywhere; ATS-parsed profiles raise match scores on StepStone and Indeed.",
         "Keep two ready-to-paste Anschreiben skeletons: one for MSP/Systemhaus roles emphasizing customer-facing service and Windows/network basics, one for corporate IT emphasizing structure and tickets.",
         "Apply inside 72 hours of publication; the pipeline's first_seen column makes this measurable, and Chapter 2's evidence says the interview payoff is up to 8x.",
         "Prefer direct employer URLs (ATS feeds) over portal redirects when both exist; direct applications showed an 11.2 percent interview rate in aggregate tracking data versus lower rates through intermediaries.",
         "Log every application in the tracker's status column the same day; the response-time statistics from Chapter 2 only become actionable once Asha measures his own funnel.",
        ]),
    ],
}

CH12 = {
    "title": "12. Legal and Etiquette",
    "blocks": [
        ("body",
         "German law on collecting job postings is favorable to a personal pipeline as long as it stays personal. "
         "Job advertisements are business data, not personal data, so GDPR is largely beside the point; the real "
         "constraints are the database-maker's right of §87b UrhG, contract terms (AGB), and unfair-competition "
         "law (UWG). The governing case line is consistent: the BGH's Flugbuchungssystem II decision (I ZR 57/17, "
         "30 January 2019) holds that scraping is not unfair per se, but terms of service that ban automated "
         "access are valid contract clauses whose breach supports injunctions; the CJEU's Ryanair v PR Aviation "
         "(C-30/14) confirms ToS bans remain enforceable even where database protection does not apply; and "
         "Innoweb v Wegener (C-202/12) treats repeated small extractions as a substantial part of a database. "
         "The practical translation: green-tier sources are unproblematic, yellow-tier channels are a contract "
         "risk profiled at the IP-ban level for low-volume personal use, and red-tier scraping is where "
         "Abmahnung exposure begins."),
        ("table", {
            "headers": ["Source / method", "Risk", "Reasoning and mitigation"],
            "ratios": [0.30, 0.10, 0.60],
            "font": 8.4,
            "rows": [
                ["BA Jobsuche API, EURES API", "green", "Official open offers for jobseekers; intended personal use; poll politely, cache, never re-host the data"],
                ["Arbeitnow API", "green", "Explicitly free public API; link back and do not abuse"],
                ["Adzuna / Jooble / Careerjet / WhatJobs", "green", "Registered keys, documented limits; attribution required on Adzuna and Careerjet"],
                ["ATS feeds (Personio /xml, feed.xml, CXS, SmartRecruiters)", "green", "Feeds are published for consumption; poll at humane intervals, keep source links"],
                ["RSS suite (WWR, Himalayas, Remotive, RemoteOK)", "green", "Feed publication implies consumption permission; 30-60 min minimum interval, attribution per terms"],
                ["XING SSR extraction (logged out)", "yellow", "robots.txt disallows /jobs/search; ToS forbid automation; low-volume personal polling is the practical risk ceiling (IP ban); 1-2 requests/hour, back off on 403, never redistribute"],
                ["LinkedIn guest endpoint", "yellow", "Same ToS situation plus aggressive throttling; no login cookies ever; well under 100 requests/day"],
                ["StepStone / Indeed / meinestadt scraping", "red", "Active anti-bot (Akamai, DataDome, Cloudflare) plus explicit ToS bans plus robots 403; use native alerts instead"],
                ["Circumventing Cloudflare/Akamai", "red", "Wilful breach; potential §303a StGB exposure at scale; excluded from this design by construction"],
            ],
            "caption": "Table 12-1: Legal risk matrix. The pipeline as designed touches only green and, optionally, tiny volumes of yellow.",
            "bold_first": True,
        }),
        ("bullets", [
         "Store links and metadata, not full ad texts; the tracker schema in Table 10-2 already does this and keeps the dataset clearly below any substantial-part threshold.",
         "Keep personal data out of the CSV: recruiter names or contact persons in ads are stored minimally or not at all (recruiter personal data is personal data).",
         "Never republish the collected data; the CSV is a personal work instrument, not an input for a public board.",
         "Respect robots.txt and visible 403/429 responses as hard stop signals; etiquette is also the cheapest anti-lawyer strategy.",
         "The pipeline needs zero red methods; if a source turns hostile, drop it and widen the green tier, which Chapter 3 shows already covers the market adequately.",
        ]),
    ],
}

CH13 = {
    "title": "13. The 14-Day Action Plan",
    "blocks": [
        ("body",
         "Everything converges into a two-week launch plan that ends with a running pipeline, a fully tuned "
         "application machine, and the first wave of fast applications out the door. The plan assumes evenings "
         "and one weekend, no budget beyond a Deutschlandticket and about 100 EUR of certification material, and "
         "produces measurable outputs each day so momentum stays visible."),
        ("table", {
            "headers": ["Day", "Actions", "Output"],
            "ratios": [0.10, 0.60, 0.30],
            "font": 8.4,
            "rows": [
                ["1", "Set up XING, StepStone, Indeed, LinkedIn profiles completely; upload PDF CV; register Adzuna and Jooble keys", "Profiles live; API keys in .env"],
                ["2", "Create native alerts per Table 11-1; set up the tracker folder, Python venv, cron skeleton", "Alert emails flowing; repo ready"],
                ["3", "Implement fetch_ba.py (Chapter 10 skeleton) with the full 19-keyword loop; verify counts against Table 4-1", "Backbone rows in jobs.csv"],
                ["4", "Add fetch_eures.py, fetch_arbeitnow.py, fetch_rss.py; implement dedupe and seen.json", "Four green sources merged"],
                ["5", "Add fetch_adzuna.py and Jooble POST; add source columns and attribution footer", "Aggregator layer live"],
                ["6", "Implement fetch_ats.py for the Table 7-1 verified feeds (DATEV, Schaeffler, adidas, PUMA, GfK, Personio trio, Hetzner)", "ATS layer live"],
                ["7", "Implement the train-reachability filter (Table 9-2 as data) and the scorer; first full CSV build", "Ranked tracker output"],
                ["8", "Add the yellow-tier portal pollers with rate limits and jitter; add IMAP ingestion of alert emails", "All sources in one CSV"],
                ["9", "Morning ritual begins: apply to all rows above score 70 within the 72 h window", "First fast applications out"],
                ["10", "Write the two Anschreiben skeletons; tailor one per top-10 employer segment", "Apply time under 2 minutes"],
                ["11", "Start AZ-900 study block 1; schedule the exam", "Certification in motion"],
                ["12", "Direct outreach wave: five short emails to MSP watchlist employers referencing their current postings", "Warm contacts created"],
                ["13", "AZ-900 study block 2; review tracker KPIs (rows/day, applications, first_seen-to-applied delta)", "Funnel metrics baseline"],
                ["14", "Weekly review ritual: source health replay (verification curls), keyword tuning, drop dead sources, promote new whitelisted towns", "Self-improving pipeline"],
            ],
            "caption": "Table 13-1: The 14-day launch plan. After day 14 the system runs on the weekly review loop.",
        }),
        ("body",
         "From week three onward the routine is five minutes each morning plus a 30-minute Sunday review, with "
         "the pipeline doing everything else. The KPI set is small and honest: new relevant rows per day, "
         "median hours from publication to first_seen, median hours from first_seen to applied, and response "
         "rate after two weeks. If the first_seen-to-applied median exceeds 72 hours, the morning ritual is "
         "failing and needs shortening; if relevant rows per day drops below one, the keyword set or the "
         "whitelist needs widening. The Deutschlandticket turns the flagged towns of Table 9-2 into realistic "
         "commutes, and by the time the first interviews arrive, AZ-900 on the CV removes the last excuse a "
         "screening HR filter had. That is the whole system: see everything first, apply fastest, measure, repeat."),
    ],
}

APXA = {
    "title": "Appendix A. Master URL Directory",
    "blocks": [
        ("body",
         "All operational URLs in one place, grouped by function, so the verification replay of day 14 can be "
         "scripted directly from this table."),
        ("table", {
            "headers": ["Group", "URL", "Purpose"],
            "ratios": [0.20, 0.52, 0.28],
            "font": 8.2,
            "rows": [
                ["BA API docs", "https://jobsuche.api.bund.dev/", "Official OpenAPI spec; documents the public key"],
                ["BA API search", "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs", "Primary search endpoint"],
                ["BA API details", "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{base64(refnr)}", "Full posting text"],
                ["EURES", "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search", "EU search, no auth"],
                ["Arbeitnow", "https://www.arbeitnow.com/api/job-board-api", "Free German board API"],
                ["Adzuna", "https://developer.adzuna.com/ + https://api.adzuna.com/v1/api/jobs/de/search/{page}", "Registration and endpoint"],
                ["Jooble", "https://jooble.org/api", "Key generation and docs"],
                ["Careerjet v4", "https://www.careerjet.com/partners/api", "Partner signup"],
                ["XING search", "https://www.xing.com/jobs/search?keywords={kw}&location={city}", "SSR JSON extraction (yellow)"],
                ["LinkedIn guest", "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search", "Guest search (yellow)"],
                ["Personio", "https://{co}.jobs.personio.de/xml", "ATS XML feed pattern"],
                ["SuccessFactors", "https://{careers-host}/jobs/feed.xml", "ATS XML feed pattern"],
                ["Workday CXS", "https://{co}.wd3.myworkdayjobs.com/wday/cxs/{co}/{site}/jobs", "ATS JSON POST pattern"],
                ["SmartRecruiters", "https://api.smartrecruiters.com/v1/companies/{co}/postings", "ATS JSON pattern"],
                ["Greenhouse", "https://boards-api.greenhouse.io/v1/boards/{co}/jobs", "ATS JSON pattern"],
                ["Lever", "https://api.lever.co/v0/postings/{co}?mode=json", "ATS JSON pattern"],
                ["Recruitee", "https://{co}.recruitee.com/api/offers/", "ATS JSON pattern"],
                ["DATEV feed", "https://datev.wd3.myworkdayjobs.com/wday/cxs/datev/Datev_Careers/jobs", "Verified CXS POST"],
                ["Schaeffler feed", "https://jobs.schaeffler.com/feed.xml", "Verified SF XML"],
                ["adidas feed", "https://careers.adidas-group.com/jobs/feed.xml", "Verified SF XML"],
                ["GfK/NIQ feed", "https://api.smartrecruiters.com/v1/companies/NielsenIQ/postings", "Verified SR JSON"],
                ["PUMA feed", "https://about.puma.com/en/dd_job_search?search=&page=0", "Verified custom JSON"],
                ["Healthineers sitemap", "https://jobs.siemens-healthineers.com/global/en/sitemap_index.xml", "Verified sitemap fallback"],
                ["Hetzner sitemap", "https://career.hetzner.com/sitemap.xml", "Verified sitemap"],
                ["WWR RSS", "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss", "Verified remote feed"],
                ["Himalayas RSS", "https://himalayas.app/jobs/rss", "Verified remote feed"],
                ["Remotive API", "https://remotive.com/api/remote-jobs", "Verified remote JSON"],
                ["RemoteOK API", "https://remoteok.com/api", "Verified remote JSON"],
                ["VGN GTFS", "https://www.vgn.de/opendata/", "Transit open data for the train filter"],
                ["gtfs.de", "https://download.gtfs.de/germany/rv_free/latest.zip", "Fallback regional GTFS"],
            ],
            "caption": "Table A-1: Operational URL directory. {co} denotes a tenant slug to substitute.",
            "bold_first": True,
        }),
    ],
}

APXB = {
    "title": "Appendix B. Dead-End Register",
    "blocks": [
        ("body",
         "These channels were investigated and verified dead, blocked, or restricted during the research window. "
         "The register exists so that no future maintenance session re-tests them on a hunch; each row states "
         "the observed failure mode. If one of these revives, it graduates back into the coverage matrix of "
         "Chapter 3."),
        ("table", {
            "headers": ["Channel", "Observed status", "Evidence"],
            "ratios": [0.28, 0.26, 0.46],
            "font": 8.2,
            "rows": [
                ["BA old API /jobads/jobs + jobsearch-beta", "Dead (403)", "All header and key variations returned 403 on 2026-10-12"],
                ["Indeed RSS (rss.indeed.com, de.indeed.com/rss)", "Dead (403)", "Three domain variants verified 403"],
                ["Indeed job search API", "Off since 2024", "Publisher program retired; page returns login wall (401)"],
                ["StepStone scraping", "Blocked", "Akamai connection reset and robots.txt 403"],
                ["Monster.de", "Blocked + shrinking", "DataDome challenge; brand sold to Bold Holdings after the 2025 bankruptcy"],
                ["glassdoor.de", "Blocked", "Cloudflare challenge; merged into Indeed July 2026"],
                ["meinestadt.de endpoints", "Blocked", "Akamai 403 on page, /jobs/rss and /rss"],
                ["Jobware", "Blocked", "403 and connection kill; same platform family as kalaydo"],
                ["GermanTechJobs /api/jobs", "Redirects to paid service", "302 to devitjobs.jobcopilot.com/signup"],
                ["Jobicy gf-feed", "404", "All parameter variants rejected"],
                ["Joblift", "Defunct", "CloudFront error domain-wide"],
                ["jobs.munich-startup.de", "Defunct", "DNS NXDOMAIN"],
                ["kimeta, JOBworld RSS, jobs.de, jobtensor /API, Get-in-IT jobboerse, heise/t3n/Golem jobs RSS", "Bot walls / 404 / 503", "No individual-access API verified"],
                ["v6.db.transport.rest", "Dead for data", "503 on all endpoints since about January 2025"],
                ["Careerjet legacy public API", "Closed to new users", "401 pointing to the v4 partner API"],
                ["WhatJobs unauthenticated", "Rejected", "410 Unknown publisher"],
                ["Talent.com API", "Contract-only", "CPC partner program, not individual-realistic"],
                ["Remotive RSS-style instant data", "24 h delay on free tier", "Paid API exists at 5,000 USD/month; irrelevant here"],
            ],
            "caption": "Table B-1: Verified dead ends. Do not re-test without cause.",
            "bold_first": True,
        }),
    ],
}

APXC = {
    "title": "Appendix C. BA API Field Reference",
    "blocks": [
        ("body",
         "Ground-truth field reference for the v6 search response, compiled from a live 100-item sample. The "
         "published OpenAPI schema is partially outdated, so this table reflects what the service actually "
         "returns today. Fields marked absent no longer exist despite lingering documentation on the internet."),
        ("table", {
            "headers": ["Field", "Type", "Meaning"],
            "ratios": [0.32, 0.16, 0.52],
            "font": 8.4,
            "rows": [
                ["referenznummer", "string", "Unique posting key; also the detail-endpoint input after base64 encoding"],
                ["stellenangebotsTitel", "string", "Ad title"],
                ["hauptberuf / alleBerufe", "string / array", "Primary and all occupational classifications"],
                ["stellenangebotsart", "enum", "ARBEIT, AUSBILDUNG, PRAKTIKUM; use angebotsart=1 to filter"],
                ["firma", "string", "Employer name"],
                ["stellenlokationen[]", "array", "One or more locations with adresse.ort, .plz, .region, .land plus breite/laenge coordinates"],
                ["entfernung", "number", "Distance in km from the wo search center"],
                ["datumErsteVeroeffentlichung", "date", "First publication date; the freshness anchor"],
                ["aenderungsdatum", "datetime", "Last modification"],
                ["eintrittszeitraum", "object", "Start window (von/bis)"],
                ["gehaltsspanneVon / Bis", "number", "Salary range when disclosed (artDerVerguetung=GEHALTSSPANNE)"],
                ["verguetungsangabe", "enum", "Compensation disclosure type"],
                ["arbeitszeitVollzeit / Teilzeit / ...", "booleans", "Working-time flags (vz, tz, snw, ho, mj)"],
                ["homeofficemoeglich", "boolean", "Remote work possible"],
                ["quereinstiegGeeignet", "boolean", "Career-changer suitable; useful junior signal"],
                ["vertragsdauer", "enum", "Contract duration (UNBEFRISTET etc.)"],
                ["arbeitgeberKundennummerHash", "string", "Hashed employer id; joins to the logo service"],
                ["externeURL", "string", "External application URL; presence marks private-board referrals"],
                ["hashId / externBoersenId", "absent", "Removed with the old API; do not parse for them"],
            ],
            "caption": "Table C-1: v6 search response fields as observed live (October 2026).",
            "bold_first": True,
        }),
        ("body",
         "The detail endpoint returns the full stellenangebotsBeschreibung plus contact and application "
         "procedures, and the employer logo service under /vermittlung/ag-darstellung-service/ct/v1/"
         "arbeitgeberlogo/{hash} serves webp images, returning 404 simply when no logo exists. Rate behavior "
         "observed: no documented numeric limits, 12 rapid requests all 200, and an X-API-BLOCKED response "
         "header present on every call, which is the signal to watch for if the BA ever tightens access. Keep "
         "the pipeline's pacing at the levels of Table 10-1 and this API will keep working as the free backbone "
         "it is designed to be."),
    ],
}

CHAPTERS_C = [CH10, CH11, CH12, CH13, APXA, APXB, APXC]
