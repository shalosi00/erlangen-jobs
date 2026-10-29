# -*- coding: utf-8 -*-
"""Report content, chapters 1-4."""

CH1 = {
    "title": "1. Executive Summary",
    "blocks": [
        ("body",
         "This report maps every practical way to gather job postings programmatically in Germany for a single, "
         "urgent use case: Asha, a freshly qualified Fachinformatiker für Systemintegration (FISI), needs his first "
         "junior IT job fast in the weakest junior hiring market in years. The research behind this document was "
         "performed on 11-12 October 2026 with six parallel deep-research tracks and live, first-party verification "
         "of every endpoint that matters. Every claim of the form this API works in this report was tested "
         "with a real HTTP request during the research window, and every dead end was verified as dead so that no "
         "time is wasted building on deprecated infrastructure."),
        ("body",
         "The headline finding is positive: a complete, fast, legally safe job-watching pipeline can be built today "
         "using exclusively green-tier sources. The single most valuable asset is the Bundesagentur für Arbeit "
         "(BA) Jobsuche API, a free official service that requires no registration and currently returns 238 "
         "Fachinformatiker Systemintegration postings within 50 km of Erlangen and roughly 6,755 Systemintegration "
         "postings Germany-wide. Around this backbone we assemble keyed aggregator APIs (Adzuna, Jooble), a "
         "no-key German board API (Arbeitnow), two verified low-volume portal channels (XING server-rendered "
         "search results and the LinkedIn guest endpoint), direct employer ATS feeds at DATEV, Schaeffler, adidas, "
         "GfK, PUMA, Siemens Healthineers, Hetzner and more, plus a remote-work RSS suite. Portals that actively "
         "block automation (StepStone, Indeed, meinestadt) are covered by their native email alerts instead of scraping."),
        ("callout", [
            ("238", "FISI postings within 50 km of Erlangen (BA API, live count)"),
            ("6,755", "Systemintegration postings Germany-wide (BA API)"),
            ("8x", "more interviews when applying within 72 h of posting"),
            ("30+", "programmatic sources mapped and risk-rated"),
        ]),
        ("body",
         "Because Asha commutes by train from Erlangen, the report includes a train-reachability filter derived "
         "from the official VGN GTFS open dataset: a verified whitelist of 29 municipalities reachable with zero "
         "transfers in under 60 minutes, plus explicit exclusions such as Herzogenaurach, which despite hosting "
         "PUMA and adidas has no rail station at all. The final chapters assemble these components into a concrete "
         "CSV-tracker pipeline on Python plus cron, a portal-native alerting checklist, a legal risk matrix, and a "
         "14-day action plan. The overall design principle is simple: automate finding and filtering completely, "
         "and reserve human effort for applying quickly and well."),
        ("table", {
            "headers": ["Pipeline layer", "Primary sources", "Why it wins"],
            "ratios": [0.24, 0.40, 0.36],
            "rows": [
                ["Backbone", "BA Jobsuche API v6, EURES API, Arbeitnow",
                 "Free, no key or public static key, hourly freshness, covers all of Germany incl. the BA-Jobbörse long tail"],
                ["Aggregators", "Adzuna DE, Jooble, Careerjet v4",
                 "One query reaches many boards; server-side keyword and geo filtering; salary fields"],
                ["Portal channels", "XING SSR extraction, LinkedIn guest endpoint",
                 "Real-time portal coverage without login; used at low personal-use volume (yellow tier)"],
                ["ATS-direct", "Personio /xml, SuccessFactors feed.xml, Workday CXS, SmartRecruiters",
                 "Zero competition: watch target employers before postings reach portals"],
                ["Remote suite", "WeWorkRemotely, Himalayas, Remotive, RemoteOK",
                 "Fully remote fallback positions across Germany and Europe"],
                ["Native alerts", "StepStone Jobagent, Indeed/meinestadt emails, XING Job-Alerts",
                 "Covers anti-bot portals legally through their own alert products"],
            ],
            "caption": "Table 1-1: The Speed Stack at a glance. Each layer is detailed in its own chapter.",
            "bold_first": True,
        }),
    ],
}

CH2 = {
    "title": "2. Target Profile and Search Strategy",
    "blocks": [
        ("body",
         "Asha's profile defines the search surface. He completed an Ausbildung as Fachinformatiker für "
         "Systemintegration, which in German postings appears under a predictable cluster of titles: FISI roles, "
         "IT-Systemelektroniker, Systembetreuer, junior IT-Administrator, First/Second-Level Support and MSP "
         "service technician positions. The scope agreed for this search is FISI plus adjacent junior IT, which "
         "is deliberately wider than strict title matching because many employers title these jobs as "
         "IT-Support or Systemadministrator while the actual work is classic Systemintegration: "
         "client and server rollout, Windows domains, networking, ticket handling and customer-site service."),
        ("h3", "Market reality: why speed is the whole game"),
        ("body",
         "The 2025/2026 junior IT market is structurally hostile to newcomers. Bitkom counted roughly 149,000 "
         "open IT positions in 2023 but only about 76,000 in 2024, and the senior overhang from tech layoffs has "
         "crowded entry-level pipelines. The BA Fachkräfteengpassanalyse keeps technical IT professions in the "
         "shortage or observation zone, but the shortage is concentrated in experienced profiles; juniors face "
         "the bottleneck. The practical consequence is that Asha needs both volume and speed: 40 to 80 high-quality "
         "applications, and a repeatable process that surfaces each new relevant posting within hours rather than days."),
        ("body",
         "Timing evidence justifies the whole engineering effort. The widely cited TalentWorks analysis of roughly "
         "1,600 applications found that applying within the first 72 hours of a posting yields up to eight times "
         "more interviews than applying late. More recent aggregate data from careery (2026) puts the median "
         "employer first-response at 6.7 days, and huntr data shows an 11.2 percent interview rate for direct "
         "company applications. Together these numbers define the pipeline requirement: detect new postings within "
         "24 hours, apply within 72, and never hear about a good posting a week late from a daily digest alone."),
        ("callout", [
            ("2.800-3.900 \u20ac", "typical FISI entry salary range, brutto/month (ausbildung.de)"),
            ("6.7 d", "median first response across applications (careery 2026)"),
            ("11.2 %", "interview rate for direct company applications (huntr)"),
        ]),
        ("h3", "Certifications that shorten the search"),
        ("body",
         "Two certifications give the best effort-to-signal ratio for FISI applicants. Microsoft AZ-900 can be "
         "earned in one or two weekends and appears in a large share of junior infrastructure postings as a "
         "baseline cloud credential. ITIL 4 Foundation matches the vocabulary of servicedesk-heavy roles and is "
         "frequently used as an HR filter keyword by MSPs. CCNA is the stretch goal for the Netzwerkadministrator "
         "track and pays off specifically in Systemhaus environments. LPIC-1 is respectable but carries less "
         "recognition in German HR filtering than the Microsoft line."),
        ("h3", "Keyword engineering"),
        ("body",
         "API queries are only as good as their keyword sets. The table below is the copy-paste-ready search "
         "vocabulary for the whole pipeline. It separates core German role names, additional German variants that "
         "appear in real postings, English-language variants increasingly used in German IT ads, employer-type "
         "terms for discovering MSPs and Systemhäuser, and the exclusion list that keeps senior and unrelated "
         "roles out of the tracker. Query syntax differs per source and is noted per row; the BA API takes one "
         "string per query, so the pipeline loops over the keyword list rather than trying to build one OR query."),
        ("table", {
            "headers": ["Category", "Terms", "Usage notes"],
            "ratios": [0.20, 0.52, 0.28],
            "rows": [
                ["DE core", "Fachinformatiker Systemintegration; Systemintegration; IT-Systemelektroniker; Systembetreuer; Systemadministrator; IT-Administrator; IT-Support; First-Level-Support; Second-Level-Support; IT-Servicedesk; IT-Techniker; Client Management; Netzwerkadministrator; Serveradministrator; Cloud-Administrator; Junior DevOps; Anwendungsbetreuer; IT-Service",
                 "BA API: one was= string per query, loop over all; Adzuna what=; LinkedIn keywords="],
                ["DE extra", "IT-Helpdesk; Helpdesk-Mitarbeiter; IT-Betreuung; IT-Mitarbeiter; IT-Infrastruktur; Infrastruktur-Administrator; Systemadministration; IT-Systemtechniker; IT-Supporter; IT-Anwenderbetreuung; Junior Systemadministrator",
                 "Second wave of BA queries; same loop"],
                ["EN variants", "IT Support Specialist; System Administrator; Junior System Engineer; IT Operations; Service Desk; Helpdesk Technician",
                 "Common in international and corporate postings; Adzuna and LinkedIn respond well"],
                ["Employer types", "Systemhaus; IT-Dienstleister; Managed Service Provider; MSP; IT-Serviceprovider; Rechenzentrum",
                 "Used for building the employer watchlist (Chapter 7), not for title search"],
                ["Exclusions", "Senior; Principal; Lead; Head of; Teamleitung; Architekt; 5 Jahre Berufserfahrung; mehrjährige Berufserfahrung; Werkstudent; Praktikum; Ausbildung; Azubi; Vertrieb; Sales; Student; Freelance; freiberuflich",
                 "Negative filter in the tracker scorer; Ausbildung and Praktikum are excluded because Asha has completed his Ausbildung"],
            ],
            "caption": "Table 2-1: The keyword set for the pipeline. Semicolons separate individual terms.",
            "bold_first": True,
        }),
    ],
}

CH3 = {
    "title": "3. Provider Coverage Matrix",
    "blocks": [
        ("body",
         "This chapter is the master map. More than 30 German and Germany-covering providers were investigated; "
         "the table below condenses each to its access method, authentication requirement, freshness, and legal "
         "risk tier. Green means a source is explicitly offered for consumption (official API, public feed, RSS) "
         "and can be polled on a schedule. Yellow means a technically accessible channel that the provider's "
         "terms do not bless, safe only at low personal-use volume. Red means actively defended infrastructure "
         "where automated access is both contractually banned and technically punished; red sources are handled "
         "through native alerts instead. The striking result of the research: the green tier alone already covers "
         "the vast majority of reachable FISI postings in Asha's region, so the pipeline never needs to touch a red source."),
        ("table", {
            "headers": ["Provider", "Method", "Auth", "Freshness", "Risk", "Verdict"],
            "ratios": [0.17, 0.27, 0.12, 0.13, 0.08, 0.23],
            "font": 8.2,
            "rows": [
                ["Bundesagentur für Arbeit", "REST API v6 (jobsuche-service)", "static public key", "realtime", "green", "Backbone. 238 FISI hits near Erlangen, detail endpoint per job"],
                ["EURES (EU portal)", "JSON search API", "none", "realtime", "green", "8,499 FISI records; BA mirror plus EU extras"],
                ["Arbeitnow", "JSON API, no key", "none", "hourly", "green", "German board; client-side filtering required"],
                ["Adzuna", "REST API /jobs/de", "free app key", "realtime", "green", "Best queryable API; 250 calls/day free tier"],
                ["Jooble", "POST API", "free key", "realtime", "green", "Simple keywords+location search"],
                ["Careerjet", "Partner API v4", "partner key", "realtime", "green", "Legacy keyless API closed to new users"],
                ["WhatJobs", "Publisher API", "publisher key", "realtime", "green", "Affiliate program required"],
                ["XING Jobs", "SSR page JSON (APOLLO_STATE)", "none (logged out)", "realtime", "yellow", "16+ jobs per page incl. salary, one-click flag; robots.txt disallows /jobs/search so keep volume tiny"],
                ["LinkedIn Jobs", "Guest API seeMoreJobPostings", "none (logged out)", "realtime", "yellow", "Works unauthenticated; throttle hard, never with account cookies"],
                ["StepStone", "none; native Jobagent email", "n/a", "daily digest", "red", "Akamai bot manager verified; do not scrape"],
                ["Indeed DE", "none; native alerts", "n/a", "daily digest", "red", "API off since 2024, RSS dead (403), login wall"],
                ["meinestadt.de", "none; native alerts", "n/a", "daily", "red", "Akamai 403 on all endpoints"],
                ["Jobware", "none", "n/a", "n/a", "red", "403/connection kill"],
                ["Monster.de", "none", "n/a", "n/a", "red", "DataDome; inventory shrinking post-bankruptcy"],
                ["glassdoor.de", "none", "n/a", "n/a", "red", "Cloudflare; merged into Indeed 07/2026"],
                ["GermanTechJobs", "none", "n/a", "n/a", "red", "Old API 302-redirects to a paid jobcopilot signup"],
                ["kimeta, JOBworld, jobs.de, jobtensor, Get-in-IT, heise/t3n/Golem jobs", "none verified", "n/a", "n/a", "red", "Bot walls, 404/503; no individual-access API"],
                ["Personio-hosted careers", "GET /xml per company", "none", "realtime", "green", "Verified at NürnbergMesse, ITONICS, Nerdware"],
                ["SuccessFactors careers", "GET feed.xml per company", "none", "realtime", "green", "Verified at Schaeffler (5.6 MB) and adidas (5.9 MB)"],
                ["Workday CXS", "POST .../wday/cxs/...", "none", "realtime", "green", "Verified at DATEV"],
                ["SmartRecruiters", "public API per company", "none", "realtime", "green", "Verified at GfK via NielsenIQ slug"],
                ["PUMA careers", "JSON search endpoint", "none", "realtime", "green", "594 jobs in one response"],
                ["Siemens Healthineers", "career sitemaps", "none", "weekly-ish", "green", "Phenom API blocked; sitemap fallback works"],
                ["Hetzner", "career sitemap", "none", "realtime", "green", "142 URLs incl. live FISI pages"],
                ["WeWorkRemotely", "RSS per category", "none", "realtime", "green", "DevOps/sysadmin feed fits FISI"],
                ["Himalayas", "RSS", "none", "realtime", "green", "Simple, reliable"],
                ["Remotive", "JSON API", "none (attribution)", "24 h delay", "green", "Free tier requires attribution; paid tier exists"],
                ["RemoteOK", "JSON API", "none", "realtime", "green", "Tags include junior and sysadmin"],
                ["VGN GTFS (transit)", "GTFS zip download", "none", "quarterly", "green", "Powers the train-reachability filter (Chapter 9)"],
            ],
            "caption": "Table 3-1: Master coverage matrix. Live verification status as of 11-12 October 2026.",
            "bold_first": True,
        }),
        ("body",
         "Three structural observations emerge from the matrix. First, Germany's public-sector data infrastructure "
         "is dramatically more open than its commercial portal sector: the two most powerful sources (BA and EURES) "
         "are government services. Second, the aggregator tier is thin but sufficient; Adzuna alone aggregates a "
         "meaningful share of the market and offers proper server-side filtering, which the no-key German APIs lack. "
         "Third, the ATS layer is the hidden gem: major Franconian employers publish machine-readable feeds that "
         "most competitors never watch, which is exactly where an applicant seeking speed gains an edge."),
    ],
}

CH4 = {
    "title": "4. Tier 1 - Official Backbone APIs",
    "blocks": [
        ("h2", "4.1 Bundesagentur für Arbeit Jobsuche API"),
        ("body",
         "The BA jobsuche service is the most important single discovery in this research. Much of the internet "
         "still documents the old endpoint rest.arbeitsagentur.de/jobads/jobs with the key jobsearch-beta; that "
         "combination is dead and returns HTTP 403 on every variation tested. The current production API, "
         "confirmed against the BA's own web client configuration, is versioned under "
         "jobboerse/jobsuche-service and accepts a static public client key, jobboerse-jobsuche. The official "
         "OpenAPI specification at jobsuche.api.bund.dev states that this key is public, that the API is free and "
         "that no registration is required, which makes this the lowest-friction high-volume job data source in Germany."),
        ("code", "BA search - verified live 2026-10-12, HTTP 200",
         'curl -sS -H "X-API-Key: jobboerse-jobsuche" \\\n'
         '  "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs\n'
         '?was=Fachinformatiker%20Systemintegration&wo=Erlangen&umkreis=50\n'
         '&page=1&size=100&veroeffentlichtseit=7&angebotsart=1"\n'
         '\n'
         '# detail page for one posting (base64 of referenznummer):\n'
         'curl -sS -H "X-API-Key: jobboerse-jobsuche" \\\n'
         '  "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/\n'
         'jobdetails/MTAwMDEtMTAwMzgzMjk5My1T"'),
        ("body",
         "Search parameters verified against the live service: was (keyword), wo (location), umkreis (radius km), "
         "page (1-based), size (max 100), veroeffentlichtseit (days 0-100, the freshness filter), angebotsart "
         "(1 = Arbeit, 4 = Ausbildung, 34 = Praktikum), arbeitszeit (vz/tz/snw/ho/mj), befristung, zeitarbeit, "
         "pav, behinderung, arbeitgeber (exact, case-sensitive) and berufsfeld. Old parameter names from the "
         "jobads era such as publishedSince are silently ignored. The search response contains the list under "
         "ergebnisliste plus maxErgebnisse, page, size, woOutput (geocoding) and facetten. Each item carries "
         "referenznummer, stellenangebotsTitel, firma, hauptberuf, alleBerufe, stellenlokationen with "
         "ort/plz/region and coordinates, entfernung (distance in km), datumErsteVeroeffentlichung, "
         "aenderungsdatum, eintrittszeitraum, gehaltsspanneVon/Bis, homeofficemoeglich, quereinstiegGeeignet and "
         "externeURL. Note that hashId and externBoersenId from the old API no longer exist: the detail key is "
         "base64(referenznummer), and private-board referrals are detected via externeURL presence."),
        ("table", {
            "headers": ["Query (live tested)", "maxErgebnisse"],
            "ratios": [0.78, 0.22],
            "rows": [
                ["Fachinformatiker Systemintegration, Erlangen, 50 km", "238"],
                ["Fachinformatiker Systemintegration, Nürnberg, 50 km", "237"],
                ["Systemintegration, Erlangen, 50 km", "305 (225 with angebotsart=1)"],
                ["Systemintegration, Erlangen, 50 km, veroeffentlichtseit=7", "56 (1 within 24 h)"],
                ["IT-Systemelektroniker, Erlangen 50 km / Nürnberg 50 km", "35 / 32"],
                ["IT-Support, Nürnberg, 50 km", "316"],
                ["IT-Administrator, Erlangen, 50 km", "96"],
                ["berufsfeld=Informatik, Erlangen, 50 km", "478"],
                ["Systemintegration, Germany-wide", "6,755"],
                ["Fachinformatiker Systemintegration, Germany-wide", "5,190"],
            ],
            "caption": "Table 4-1: Live result counts from the BA v6 API (2026-10-11/12). Erlangen and Nürnberg 50 km circles overlap almost completely, so one Nürnberg query covers the metro.",
        }),
        ("body",
         "Operational notes matter for a cron pipeline. Twelve rapid consecutive requests all returned 200 during "
         "testing and every response carries an X-API-BLOCKED header (observed value 0), so an explicit blocking "
         "mechanism exists even though no numeric limits are documented. The BA terms of use prohibit automated "
         "access contrary to the intended purpose and bulk redistribution; a personal tracker polling a keyword "
         "loop every 30 to 60 minutes with caching by referenznummer is comfortably within intended use. Community "
         "libraries worth knowing: bundesAPI/jobsuche-api (161 stars, maintained), wunderfrucht/jobsuche (Rust, "
         "documents quirks such as sporadic 403-as-rate-limit and no sort parameter), long39ng/jobsuche (R), "
         "kemdev/jobsuche-api-js (TypeScript) and an n8n node, hansdoebel/n8n-nodes-jobsuche. There is no live "
         "Python package on PyPI, which is why Chapter 10 ships a minimal requests-based fetcher."),
        ("h2", "4.2 EURES search API"),
        ("body",
         "The EU EURES portal exposes an unauthenticated JSON search API that mirrors BA data and adds EU-wide "
         "extraditional listings. A POST to europa.eu/eures/api/jv-searchengine/public/jv-search/search with a "
         "keywords array returned HTTP 200 and 8,499 records for Fachinformatiker Systemintegration; the companion "
         "getNumberOfJobs endpoint reports 2.6 million live postings, and jv-search/search/getNumberOfJobs plus "
         "/jv/id/{id} give counts and detail. EURES job ids turn out to be base64 encodings of BA reference "
         "numbers, so the two sources deduplicate trivially. EURES is green-tier by construction: it is an "
         "official EU jobseeker service. Its search response embeds full text, which makes it useful for "
         "keyword-scoring without a second detail call."),
        ("code", "EURES search - verified live, HTTP 200",
         'curl -sS -X POST \\\n'
         '  "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search" \\\n'
         '  -H "Content-Type: application/json" \\\n'
         '  -d \'{"keywords":[{"keyword":"Fachinformatiker Systemintegration",\n'
         '        "specificSearchCode":"EVERYWHERE"}],\n'
         '       "locationCodes":["de"],"resultsPerPage":50,"page":1}\''),
        ("h2", "4.3 Arbeitnow API"),
        ("body",
         "Arbeitnow is a German job board with a genuinely free public API and no key. The endpoint "
         "api/job-board-api returns 325 listings per page in a stable schema (slug, company_name, title, url, "
         "location, description, tags, job_types, remote, created_at) and updates hourly, ordered by created_at. "
         "Two caveats shape its use: the search parameter is ignored server-side, so the pipeline paginates one "
         "to three pages per run and filters client-side against the Chapter 2 keyword set; and the terms ask "
         "for a link back and no abuse, so a single-digit number of requests per hour is appropriate. During "
         "testing, an unfiltered page of 325 contained two Systemintegration-related listings, consistent with a "
         "board that skews toward software development but still carries infrastructure and support roles. "
         "Arbeitnow is the only no-key source besides the BA that is German-native, which earns it a permanent "
         "slot in the backbone."),
        ("code", "Arbeitnow - verified live, HTTP 200",
         'curl -sS "https://www.arbeitnow.com/api/job-board-api?page=1"\n'
         '# hourly refresh, ordered by created_at; filter client-side\n'
         '# against the FISI keyword list and the train-reachable town list'),
    ],
}

CHAPTERS_A = [CH1, CH2, CH3, CH4]
