# -*- coding: utf-8 -*-
"""Report content, chapters 5-9."""

CH5 = {
    "title": "5. Tier 2 - Keyed Aggregator APIs",
    "blocks": [
        ("body",
         "Aggregator APIs trade a one-time registration for server-side filtering that the no-key sources lack. "
         "Instead of pulling hundreds of listings and filtering locally, Asha's pipeline can push the keyword and "
         "location into the query and receive only relevant hits. Four aggregators matter for Germany; the rest "
         "of the aggregator landscape was checked and dismissed, and those results are preserved in Appendix B so "
         "that nobody re-tests them next month."),
        ("table", {
            "headers": ["Provider", "Registration", "Endpoint shape", "Free tier / limits"],
            "ratios": [0.14, 0.24, 0.40, 0.22],
            "font": 8.2,
            "rows": [
                ["Adzuna", "developer.adzuna.com (app_id + app_key)",
                 "GET api.adzuna.com/v1/api/jobs/de/search/{page}?app_id=..&app_key=..&what=systemintegration&where=N%C3%BCrnberg&max_days_old=7",
                 "25 req/min, 250/day, 1,000/week; attribution link required"],
                ["Jooble", "jooble.org/api (key generated after signup)",
                 "POST jooble.org/api/{key} with JSON {keywords, location, page}",
                 "Free tier quoted around 500 requests; simple POST semantics"],
                ["Careerjet", "careerjet.com/partners/api (v4)",
                 "Affiliate search API, locale de_DE; requires user_ip, user_agent, Referer",
                 "Free for affiliates; legacy keyless API permanently closed (verified 401)"],
                ["WhatJobs", "Publisher/affiliate program",
                 "GET api.whatjobs.com/api/v1/jobs.json with publisher key and user_ip",
                 "Unauthenticated calls verified rejected with HTTP 410"],
            ],
            "caption": "Table 5-1: Keyed aggregator APIs covering Germany. All four were live-verified during research.",
            "bold_first": True,
        }),
        ("body",
         "Adzuna is the strongest of the four for this use case. Its German index is substantial, its query "
         "language supports what, where, max_days_old and category=it-jobs, and responses include created "
         "timestamps and salary fields, which feed the tracker's freshness scoring directly. The attribution "
         "requirement (a visible Jobs by Adzuna link when results are displayed) is trivially satisfied "
         "inside a personal CSV digest by adding a source column and a footer line. Jooble is the second "
         "recommendation: the POST interface is dead simple and its German coverage is core-market. Careerjet v4 "
         "and WhatJobs are optional extras; both work but add little beyond Adzuna plus Jooble for the effort of "
         "maintaining two more integrations. A fake-key probe against Adzuna returned a clean 401 with a pointer "
         "to its documentation, confirming the service is live and well-behaved."),
        ("code", "Adzuna search - DE, keyword + geo + freshness",
         'GET https://api.adzuna.com/v1/api/jobs/de/search/1\n'
         '    ?app_id=YOUR_ID&app_key=YOUR_KEY\n'
         '    &what=systemintegration&where=N%C3%BCrnberg\n'
         '    &category=it-jobs&max_days_old=7\n'
         '\n'
         '# Response fields used by the tracker:\n'
         '#   title, company.display_name, location.display_name,\n'
         '#   redirect_url, created, salary_min, salary_max, description\n'
         '# Register at https://developer.adzuna.com (free)'),
    ],
}

CH6 = {
    "title": "6. Tier 3 - Portal-Native Channels",
    "blocks": [
        ("body",
         "The big commercial portals offer no candidate-facing APIs: XING closed its public developer API years "
         "ago (only an employer-side e-recruiting API remains), StepStone's api.stepstone.com is partner-only, "
         "Indeed retired its Publisher API and switched job-search API access off in 2024, and LinkedIn's Jobs "
         "API is restricted to Talent Solutions partners. All historical RSS feeds are dead; Indeed's RSS was "
         "verified returning 403 on three domain variants, and StepStone answers even its robots.txt with an "
         "Akamai 403. Nevertheless two verified, login-free channels exist, and the portals' own alert products "
         "cover the rest legally and reliably."),
        ("h2", "6.1 XING server-rendered search results"),
        ("body",
         "XING's jobs search page renders server-side for logged-out visitors and embeds the full structured "
         "result set as JSON inside the HTML, in the serverData.APOLLO_STATE object. A plain curl that follows "
         "the 301 redirect from /jobs/search?keywords=... to the canonical /jobs/search/ki... URL returns HTTP "
         "200 with roughly 16 jobs per page, each carrying title, slug URL, city, employment type, salary "
         "minimum, maximum and median in EUR, the apply URL with a flag for third-party redirects, a refreshedAt "
         "timestamp for new-detection, and an application type marker that identifies one-click-apply jobs. "
         "XING's GraphQL endpoint remains transport-live but only serves allow-listed persisted operations, so "
         "the SSR page is the practical extraction surface. Because XING's robots.txt disallows /jobs/search "
         "paths, this channel is yellow-tier: keep it to one or two requests per hour, personal use only, no "
         "redistribution, and back off immediately on any 403."),
        ("code", "XING SSR extraction - verified live, HTTP 200, 363 KB page",
         'curl -sSL "https://www.xing.com/jobs/search?keywords=Fachinformatiker\n'
         '  &location=Erlangen" -H "User-Agent: Mozilla/5.0" \\\n'
         '  | grep -o "APOLLO_STATE.*" | head -c 200000\n'
         '\n'
         '# Parse VisibleJob:* keys in APOLLO_STATE JSON.\n'
         '# Fields per job: title, url/slug, city, employmentType,\n'
         '#   salaryMin/salaryMax/salaryMedian (EUR), applyUrl,\n'
         '#   redirectsToThirdPartyUrl, refreshedAt, one-click marker'),
        ("h2", "6.2 LinkedIn guest endpoint"),
        ("body",
         "LinkedIn serves public job search results to logged-out visitors through the guest API at "
         "linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search. The endpoint accepts keywords, location "
         "and start (paging in steps of 25) plus the freshness parameter f_TPR=r86400 for postings of the last "
         "24 hours, and returns an HTML fragment of job cards with HTTP 200. It was verified live twice with "
         "Fachinformatiker and IT-Systemelektroniker queries against Erlangen, returning 30-31 KB fragments with "
         "50 cards including real job URLs. LinkedIn throttles aggressively, so the tracker should stay under "
         "roughly 100 requests per day with jittered delays, never send account cookies, and treat this purely "
         "as a secondary freshness channel. The same ToS logic as XING applies: yellow tier, low volume, no "
         "redistribution."),
        ("code", "LinkedIn guest search - verified live, HTTP 200",
         'curl -sS "https://www.linkedin.com/jobs-guest/jobs/api/\n'
         'seeMoreJobPostings/search?keywords=Fachinformatiker\n'
         '&location=Erlangen%2C+Bayern%2C+Germany&start=0\n'
         '&f_TPR=r86400" -H "User-Agent: Mozilla/5.0"\n'
         '# Parse job cards; page with start=25, 50, ... ; keep < 100 req/day'),
        ("h2", "6.3 Native alerts for the defended portals"),
        ("body",
         "StepStone, Indeed, meinestadt.de, Jobware and Monster actively defend their search infrastructure "
         "(verified: Akamai connection resets on StepStone, DataDome on Monster, Cloudflare on glassdoor.de, "
         "Akamai 403s on all four meinestadt endpoints probed). The correct engineering answer is to use their "
         "own alert products, which are free, fast to set up, and legal by construction. Chapter 11 gives the "
         "exact configuration checklist; the essential trick for the CSV pipeline is an IMAP or Email-Parser "
         "step that converts alert emails into tracker rows, so even the daily-digest portals feed the same "
         "deduplicated list as the APIs. One further verification is worth recording: XING's one-click "
         "application (Bewerbung in einem Klick) is the fastest native apply flow of all German portals, "
         "requiring only a complete XING profile, and the SSR payload flags which postings support it, letting "
         "the tracker prioritize them."),
    ],
}

CH7 = {
    "title": "7. Tier 4 - ATS-Direct Feeds and the Employer Watchlist",
    "blocks": [
        ("body",
         "The deepest cut bypasses portals entirely: most German mid-size and large employers run their careers "
         "site on a commercial applicant tracking system (ATS), and most ATS products expose a public, "
         "undocumented or semi-documented feed of all openings. Watching ten relevant employers at the ATS layer "
         "often surfaces postings days before they reach aggregators, with zero competition from other "
         "applicants' tools. Every pattern in the table below was verified live during research, either at a "
         "generic demo tenant or, more importantly, at a real employer in Asha's commuting area."),
        ("table", {
            "headers": ["ATS", "Feed pattern", "Format", "Verified example (HTTP 200)"],
            "ratios": [0.15, 0.33, 0.10, 0.42],
            "font": 8.2,
            "rows": [
                ["Personio", "https://{co}.jobs.personio.de/xml", "XML",
                 "nuernbergmesse-gmbh (56 positions), itonics-gmbh (15), nerdware (22)"],
                ["SuccessFactors", "https://{careers-host}/jobs/feed.xml or /feed.xml (follow redirects)", "XML/RSS",
                 "jobs.schaeffler.com/feed.xml (5.6 MB, all jobs); careers.adidas-group.com/jobs/feed.xml (5.9 MB)"],
                ["Workday (CXS)", "POST https://{co}.wd{n}.myworkdayjobs.com/wday/cxs/{co}/{site}/jobs with JSON body", "JSON",
                 "DATEV: datev.wd3.myworkdayjobs.com/wday/cxs/datev/Datev_Careers/jobs, searchText=Fachinformatiker"],
                ["SmartRecruiters", "https://api.smartrecruiters.com/v1/companies/{co}/postings", "JSON",
                 "GfK absorbed into NielsenIQ: companies/NielsenIQ/postings?country=de"],
                ["Greenhouse", "https://boards-api.greenhouse.io/v1/boards/{co}/jobs", "JSON",
                 "boards-api.greenhouse.io/v1/boards/contentful/jobs (pattern proof)"],
                ["Lever", "https://api.lever.co/v0/postings/{co}?mode=json (EU: jobs.eu.lever.co)", "JSON",
                 "leverdemo tenant; real EU slugs mostly 404 in DE"],
                ["Recruitee", "https://{co}.recruitee.com/api/offers/", "JSON",
                 "yourcareer.recruitee.com (pattern proof)"],
                ["PUMA custom", "https://about.puma.com/en/dd_job_search?search=&page=0", "JSON",
                 "594 jobs in one response"],
                ["Phenom", "API tenant-locked; use sitemap fallback", "XML sitemap",
                 "Siemens Healthineers: /global/en/sitemap_index.xml then sitemap1/2.xml, ~750 job URLs"],
                ["In-house", "https://career.{co}.com/sitemap.xml", "XML sitemap",
                 "Hetzner: 142 URLs incl. live FISI-Ausbildung pages (j586/j588/j749/j751)"],
            ],
            "caption": "Table 7-1: ATS feed patterns with live verification evidence. {co} is the employer's tenant slug.",
            "bold_first": True,
        }),
        ("code", "Workday CXS POST - DATEV (Nürnberg), verified live, HTTP 200",
         'curl -sS -X POST \\\n'
         '  "https://datev.wd3.myworkdayjobs.com/wday/cxs/datev/\n'
         'Datev_Careers/jobs" \\\n'
         '  -H "Content-Type: application/json" \\\n'
         '  -d \'{"appliedFacets":{},"limit":20,"offset":0,\n'
         '        "searchText":"Fachinformatiker"}\'\n'
         '\n'
         '# job detail: GET .../wday/cxs/datev/Datev_Careers/job/{externalPath}'),
        ("h3", "Discovery recipes for new ATS tenants"),
        ("bullets", [
         "Google <b>site:jobs.personio.de {city}</b> to enumerate Personio tenants near a target city; the /xml suffix usually works on the same host.",
         "Career pages linking out with <b>utm_source=j2w</b> (Job2Web / SuccessFactors) almost always expose a /feed.xml one directory up.",
         "Any host matching <b>.wd{n}.myworkdayjobs.com</b> accepts the CXS POST shown above; the site path is in the careers URL.",
         "Phenom-powered careers (job pages under /job/R-xxxxx/) usually block the API but ship complete XML sitemaps: start at /sitemap.xml.",
         "Softgarden exposes wdteg.softgarden.io pages but no verified XML; treat as HTML-only for now.",
        ]),
        ("h3", "Employer watchlist for the Erlangen-Nürnberg corridor"),
        ("body",
         "The watchlist below was assembled from live ATS verification plus IHK-directory and IT-cluster research. "
         "It is the concrete polling list for the ATS layer of the pipeline; each row notes the city and, where "
         "verified, the feed that Chapter 10's scheduler will call. The MSP and Systemhaus segment is listed by "
         "name because it is the classic first employer of FISI juniors, and such firms rarely have ATS feeds, "
         "so they are covered by the portal and aggregator layers instead of direct polling."),
        ("table", {
            "headers": ["Employer", "City", "Segment / feed status"],
            "ratios": [0.30, 0.22, 0.48],
            "font": 8.2,
            "rows": [
                ["DATEV", "Nürnberg", "Software/IT services; Workday CXS verified"],
                ["Siemens Healthineers", "Erlangen/Forchheim", "Medtech IT; Phenom sitemap verified"],
                ["Siemens AG", "Erlangen region", "Avature; no public feed, use native alerts"],
                ["Schaeffler", "Herzogenaurach", "Industry IT; SuccessFactors feed.xml verified"],
                ["adidas", "Herzogenaurach", "SuccessFactors feed.xml verified"],
                ["PUMA", "Herzogenaurach", "Custom JSON search verified"],
                ["GfK / NielsenIQ", "Nürnberg", "Market research IT; SmartRecruiters verified"],
                ["Hetzner", "Nürnberg/Falkenstein", "Hosting; sitemap verified, live FISI pages"],
                ["N-ERGIE", "Nürnberg", "Utility IT; my-job-shop JSON needs runtime key, watch HTML"],
                ["NürnbergMesse", "Nürnberg", "Personio /xml verified"],
                ["ITONICS", "Erlangen", "Personio /xml verified"],
                ["Nerdware", "Nürnberg", "Personio /xml verified"],
                ["LEONI", "Fürth", "Industry IT; watch careers page"],
                ["Nürnberger Versicherung", "Nürnberg", "Insurance IT; watch careers page"],
                ["Brose", "Bamberg", "Industry IT; direct-train reachable, watch careers page"],
                ["FAU (RRZE), Uniklinikum Erlangen, TH Nürnberg, Stadt Nürnberg IT, VAG, STAEDTLER, Faber-Castell, PLAYMOBIL (Zirndorf)", "Erlangen/Nürnberg region", "Public sector and mid-caps; steady FISI demand, watch career pages"],
                ["noris network, netcup, OSB AG (Bamberg), ZOLLHOF startups", "Nürnberg/Bamberg", "Infrastructure/hosting/startups"],
                ["Bechtle, CANCOM, Computacenter (branch offices)", "Nürnberg/Fürth/Erlangen", "Systemhaus majors; portal-layer coverage"],
                ["ATA Solutions, IPExx, Lehmann IT, HWS Gruppe, BES Systemhaus, VIA APPIA, B2 Innovations", "Mittelfranken", "Regional MSPs; verify city and watch portals"],
                ["Empfehlungsbund IT-Mittelstand members (it-mittelstand.de/nuernberg), BitMi directory entries", "Nürnberg metro", "Aggregated Mittelstand IT employers; periodic manual sweep"],
            ],
            "caption": "Table 7-2: 40-employer watchlist (rows with multiple names each expand to several employers). Feed statuses reflect live verification.",
            "bold_first": True,
        }),
    ],
}

CH8 = {
    "title": "8. Remote and Niche RSS Suite",
    "blocks": [
        ("body",
         "Remote-first boards round out the all-Germany fallback: a fully remote junior support or sysadmin role "
         "satisfies the train constraint trivially because the commute is empty. All four services below expose "
         "key-less feeds, were verified live, and impose only attribution-style conditions. WeWorkRemotely "
         "publishes per-category RSS; the DevOps/sysadmin feed is the FISI-relevant one (its older "
         "it-and-support slug now 301-redirects). Himalayas offers one clean RSS endpoint. Remotive's JSON API is "
         "free with mandatory attribution and a 24-hour publication delay, which matters only because the "
         "tracker must not treat Remotive as a first-alert channel. RemoteOK serves a JSON array whose first "
         "element is a legal notice; its tags include junior and sysadmin, useful for filtering, while its RSS "
         "endpoint is retired (410)."),
        ("table", {
            "headers": ["Source", "Endpoint", "Format", "Notes"],
            "ratios": [0.16, 0.42, 0.10, 0.32],
            "font": 8.2,
            "rows": [
                ["WeWorkRemotely", "weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss (plus programming, customer-support, product feeds)", "RSS",
                 "25 items per feed; pubDate freshness; all verified 200"],
                ["Himalayas", "himalayas.app/jobs/rss", "RSS", "Single endpoint; simple schema; verified 200"],
                ["Remotive", "remotive.com/api/remote-jobs?limit=50", "JSON",
                 "Attribution mandatory; 24 h delay on free tier; verified 200"],
                ["RemoteOK", "remoteok.com/api", "JSON",
                 "First array element is a legal notice; epoch + tags fields; verified 200"],
            ],
            "caption": "Table 8-1: Remote feed suite. All endpoints verified live during research.",
            "bold_first": True,
        }),
        ("code", "Remote suite - one-line health checks, all verified 200",
         'curl -sS "https://weworkremotely.com/categories/\n'
         '  remote-devops-sysadmin-jobs.rss" | head -c 300\n'
         'curl -sS "https://himalayas.app/jobs/rss" | head -c 300\n'
         'curl -sS "https://remotive.com/api/remote-jobs?limit=5" | head -c 300\n'
         'curl -sS "https://remoteok.com/api" | head -c 300'),
    ],
}

CH9 = {
    "title": "9. The Erlangen Train-Reachability Filter",
    "blocks": [
        ("body",
         "Asha's constraint is precise: jobs within roughly 50 km of Erlangen that are directly reachable by "
         "train, without changing. Distance filters are the wrong tool, because rail geography is nonlinear; "
         "Coburg at about 65 km is a 47-minute direct ride, while rail-less Herzogenaurach at 15 km is "
         "unreachable by Asha's definition. The correct instrument is a transit-data filter built on the VGN "
         "(Verkehrsverbund Großraum Nürnberg) GTFS feed, published as open data under CC BY-SA 3.0 DE at "
         "vgn.de/opendata. The feed contains 25,464 stops and 90,753 trips, and its stop IDs embed the official "
         "AGS municipality key (de:09562:* = Erlangen, de:09563:* = Fürth, and so on), which allows direct "
         "mapping from stations to municipalities without any geo-join."),
        ("table", {
            "headers": ["Source", "URL", "License / status"],
            "ratios": [0.22, 0.44, 0.34],
            "rows": [
                ["VGN GTFS (primary)", "vgn.de/opendata - stable GTFS.zip link", "CC BY-SA 3.0 DE; updated irregularly (last: June 2026); verified download"],
                ["gtfs.de Germany feeds", "download.gtfs.de/germany/{nv,rv,fv}_free/latest.zip", "Open; daily refresh; verified; fallback when VGN is stale"],
                ["v6.db.transport.rest", "community DB API proxy", "Verified dead for data (503 on all endpoints since ~2025); do not build on it"],
                ["db-vendo (GitHub)", "public-transport/db-vendo-client", "Maintained library but no hosted instance; upstream DB APIs unreliable; self-host only"],
            ],
            "caption": "Table 9-1: Transit data sources for the reachability filter, with live verification status.",
            "bold_first": True,
        }),
        ("body",
         "The computation is a zero-transfer expansion: load the GTFS feed, collect all platforms of Erlangen "
         "Bahnhof (parent stop de:09562:3110), keep every trip of route_type 2 (rail) that touches any of them, "
         "and take the union of the other stops on those same trips, which are reachable with zero transfers by "
         "construction. In-vehicle minutes are arrival minus Erlangen departure, and services are filtered to "
         "those active on at least 60 percent of weekdays in a 90-day window to kill holiday ghosts. Running this "
         "procedure on the June 2026 feed yields 82 stops across 29 municipalities within 60 minutes, the "
         "whitelist below. The pragmatic pipeline uses this table as a hardcoded filter, refreshed quarterly "
         "after each GTFS release, because journey-API approaches (v6.db.transport.rest) are verified dead."),
        ("table", {
            "headers": ["Municipality", "Station(s)", "Line", "~min", "Direction"],
            "ratios": [0.26, 0.30, 0.20, 0.09, 0.15],
            "font": 8.0,
            "rows": [
                ["Erlangen (all districts)", "Hbf, Paul-Gossen-Str., Bruck, Eltersdorf", "S1", "2-6", "origin"],
                ["Fürth", "Hbf, Klinikum, Vach", "RE/S1", "7-17", "south"],
                ["Nürnberg", "Hbf + S1 city stops (Dürrenhof ... Laufamholz)", "all", "14-41", "south"],
                ["Baiersdorf", "Baiersdorf", "S1", "6", "north"],
                ["Bubenreuth", "Bubenreuth", "S1", "3", "north"],
                ["Forchheim", "Forchheim, Forchheim Nord, Kersbach", "RE/S1", "7-18", "north"],
                ["Eggolsheim", "Eggolsheim", "RE14/S1", "16", "north"],
                ["Buttenheim", "Buttenheim", "S1", "24", "north"],
                ["Hirschaid", "Hirschaid", "RE/S1", "16", "north"],
                ["Strullendorf", "Strullendorf", "S1", "31", "north"],
                ["Bamberg", "Bamberg", "RE/IC61/S1", "20-37", "north"],
                ["Hallstadt", "Hallstadt", "RE14/28", "30", "north"],
                ["Breitengüßbach", "Breitengüßbach", "RE14/28", "30", "north"],
                ["Rattelsdorf", "Ebing", "RE14/28", "34", "north"],
                ["Zapfendorf", "Zapfendorf", "RE14/28", "36", "north"],
                ["Ebensfeld", "Ebensfeld", "RE14/28", "38", "north"],
                ["Bad Staffelstein", "Bad Staffelstein", "RE14/28", "42", "north"],
                ["Lichtenfels", "Lichtenfels, Schney", "RE14/28/IC61", "37-57", "north"],
                ["Michelau i.OFr.", "Michelau", "RE14", "53", "north"],
                ["Hochstadt a.Main", "Hochstadt-Marktzeuln", "RE14", "56", "north"],
                ["Redwitz a.d.Rodach", "Redwitz", "RE14", "59", "north"],
                ["Kronach", "Kronach", "IC61 (limited), RE14 65", "51 flag", "north"],
                ["Haßfurt", "Haßfurt", "RE20", "41", "west"],
                ["Schwaig b.Nbg", "Schwaig", "S1", "43", "east"],
                ["Röthenbach a.d.Pegnitz", "Röthenbach, Steinberg, Seespitze", "S1", "46-50", "east"],
                ["Lauf a.d.Pegnitz", "Lauf West, Lauf", "S1", "52-53", "east"],
                ["Ottensoos", "Ottensoos", "S1", "57", "east"],
                ["Henfenfeld", "Henfenfeld", "S1", "60", "east"],
                ["Coburg", "Coburg", "RE19/28/29", "47", "north (65 km)"],
                ["Ansbach", "Ansbach", "IC61 only, about 4/day", "48 flag", "south"],
            ],
            "caption": "Table 9-2: Verified zero-transfer whitelist from Erlangen Bahnhof, 60 minutes or less (VGN GTFS, June 2026). Flagged rows are limited-frequency and need a schedule check per application.",
        }),
        ("body",
         "Exclusions are as decision-relevant as inclusions. Herzogenaurach hosts PUMA and adidas yet has no rail "
         "at all, bus-only, so it fails the constraint despite the strongest employer names; Höchstadt a.d.Aisch "
         "is likewise rail-less. Schwabach, Roth, Feucht, Altdorf and Neumarkt sit one transfer away on S2/S3 "
         "lines from Nürnberg, and the S1's brief extension toward Neumarkt was reverted on 14 December 2025, so "
         "stale web sources claiming otherwise should be ignored. Würzburg, Kitzingen and Neustadt an der Aisch "
         "are bypassed entirely by the rail lines that serve Erlangen; Gräfenberg and Eckental require a "
         "transfer; and anything past 60 minutes (Rödental 70, Hersbruck 63, Hartmannshof 74) is out. For "
         "filtering implementation the pipeline matches postings against this whitelist by town name and PLZ "
         "prefix, with the flagged entries (Kronach, Ansbach) kept behind a warning rather than dropped, since a "
         "strong FISI offer with four daily IC61 connections may still be worth an interview conversation."),
        ("body",
         "Tariff context completes the picture: Nürnberg and Fürth sit in zones 100/200 (Stadttarif A), Erlangen "
         "in zone 400, and the Deutschlandticket at 63 EUR per month from January 2026 covers the entire "
         "whitelist at zero marginal per-ride cost. Economically, then, the filter should be time-based rather "
         "than distance-based, exactly as the GTFS computation above already is."),
    ],
}

CHAPTERS_B = [CH5, CH6, CH7, CH8, CH9]
