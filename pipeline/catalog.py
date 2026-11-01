"""Catalog of every job aggregator/board evaluated for Asha's FISI search.
status: live (fetchable now) | key (needs free API key via env) | recipe (works from
residential IP / with FlareSolverr/Playwright) | blocked (WAF) | dead | policy.
`sources` command prints this; `fetch` runs every `live`/`key` source."""

CATALOG = [
    # --- LIVE, no key -------------------------------------------------------
    dict(id="ba",          name="Bundesagentur für Arbeit v6", kind="JSON API", status="live",
         note="rest.arbeitsagentur.de/.../v6/jobs; X-API-Key jobboerse-jobsuche; angebotsart=1+pav=false; geo radius authoritative"),
    dict(id="eures",       name="EURES (EU portal)", kind="JSON API", status="live",
         note="POST europa.eu/eures/api/jv-searchengine/public/jv-search/search; full text in search response; mirrors BA + EU cross-border"),
    dict(id="xing",        name="XING Jobs (SSR)", kind="HTML/Apollo-state", status="live",
         note="logged-out SSR page embeds jobSearchByQuery APOLLO_STATE; yellow zone: 1 req/poll, back off on 403"),
    dict(id="connecticum", name="Connecticum", kind="HTML", status="live",
         note="junior/graduate focus; /jobs?searchterm=; client-side geo filter"),
    dict(id="getinit",     name="Get-in-IT", kind="HTML", status="live",
         note="IT-only board; /jobsuche?was=&wo=; CardJob anchors"),
    dict(id="berufsstart", name="Berufsstart.de", kind="HTML", status="live",
         note="entry-level board; ergebnisliste.php?suchbegriff=; country-wide -> geo filter"),
    dict(id="infranken",   name="Jobs.InFranken.de", kind="HTML", status="live",
         note="Franconia local SMEs (Erlangen goldmine); /suchergebnisse?Searchterm=; AreaRadius param exists"),
    dict(id="talent",      name="Talent.com DE", kind="HTML", status="live",
         note="global meta-aggregator; de.talent.com/jobs?k=&l=; JSON-LD #jobList urls"),
    dict(id="arbeitnow",   name="Arbeitnow", kind="JSON API", status="live",
         note="free public API no key; arbeitnow.com/api/job-board-api; client-side keyword+geo filter; link back per terms"),
    dict(id="remotive",    name="Remotive", kind="JSON API", status="live",
         note="remote/global; remotive.com/api/remote-jobs; 24h delay; attribution required"),
    dict(id="remoteok",    name="RemoteOK", kind="JSON API", status="live",
         note="remoteok.com/api; first element = legal notice; sysadmin/support tags relevant"),
    dict(id="jobicy",      name="Jobicy", kind="JSON API", status="live",
         note="jobicy.com/api/v2/remote-jobs?count=50; v2 API verified 200; credit + redirect to source"),
    dict(id="wwr",         name="We Work Remotely", kind="RSS", status="live",
         note="weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss (+programming)"),
    dict(id="himalayas",   name="Himalayas", kind="RSS", status="live",
         note="himalayas.app/jobs/rss; pubDate + custom ns"),
    dict(id="indeed",      name="Indeed DE (via jobspy)", kind="scraper-lib", status="live",
         note="python-jobspy guest mode; needs pip install python-jobspy; hours_old param"),
    dict(id="linkedin",    name="LinkedIn (via jobspy)", kind="scraper-lib", status="live",
         note="python-jobspy guest mode, NO login; low volume; yellow zone"),
    # --- KEY-GATED (free registration) --------------------------------------
    dict(id="adzuna",      name="Adzuna DE", kind="JSON API", status="key",
         note="set ADZUNA_APP_ID + ADZUNA_APP_KEY (free: developer.adzuna.com); 25 calls/min free; salary data"),
    dict(id="jooble",      name="Jooble", kind="JSON API", status="key",
         note="set JOOBLE_API_KEY (free: jooble.org/api); POST keywords/location"),
    dict(id="careerjet",   name="Careerjet v4", kind="JSON API", status="key",
         note="set CAREERJET_AFFID (free: careerjet.com/partners/api); DC-unreachable, works from residential"),
    dict(id="whatjobs",    name="WhatJobs", kind="JSON API", status="key",
         note="set WHATJOBS_PUBLISHER_KEY (affiliate program); api.whatjobs.com/api/v1/jobs.json"),
    # --- RECIPE (works from residential IP / with FlareSolverr/Playwright) ---
    dict(id="kimeta",      name="Kimeta.de", kind="HTML", status="live",
         note="UNLOCKED via proxy pool (pipeline/sources/kimeta.py): SEO URL {keyword}-jobs-{city}, SSR cards h3.jt/div.cn/pin-svg; DC IP nginx-503 -> fetch via validated proxies; no dates on cards (first-seen convention)"),
    dict(id="jobvector",   name="Jobvector", kind="HTML", status="recipe",
         note="Cloudflare cookie challenge; curl_cffi 403, only 3/1255 proxies pass -> FlareSolverr if ever needed; white-label twin: jobs.sueddeutsche.de"),
    dict(id="gigajob",     name="Gigajob", kind="HTML", status="recipe",
         note="Cloudflare 401 -> FlareSolverr; RSS feeds dead"),
    dict(id="yourfirm",    name="Yourfirm", kind="HTML", status="recipe",
         note="Cloudflare 403 -> FlareSolverr; Mittelstand focus"),
    dict(id="stellenanzeigen", name="Stellenanzeigen.de", kind="JSON API", status="live",
         note="UNLOCKED (Task 11): WAF defeated by curl_cffi impersonate=chrome124; results via browser-captured JSON API (pipeline/sources/stellenanzeigen.py) — no proxy needed"),
    dict(id="jobrapido",   name="Jobrapido.de", kind="HTML", status="recipe",
         note="hard 403 IP block; survives curl_cffi TLS spoof (93B reply); residential proxy + cookies only"),
    dict(id="jobware",     name="Jobware", kind="HTML", status="recipe",
         note="flaky DC rate-limit; Playwright + 1 req/30s; low priority"),
    dict(id="absolventa",  name="Absolventa", kind="HTML/turbo", status="recipe",
         note="params /jobs?query[keywords][]=&query[cities][]={city}-de-{region}; JS-rendered -> Playwright; autocomplete API keyless"),
    dict(id="interamt",    name="Interamt (public sector)", kind="SPA", status="recipe",
         note="Angular SPA; record XHR once with Playwright then replay; Stadt Erlangen IT roles appear here"),
    dict(id="fau",         name="FAU Jobbörse (Uni Erlangen-Nbg)", kind="HTML", status="recipe",
         note="unreachable from DC; plain board from any German residential IP"),
    dict(id="bsj",         name="Berlin Startup Jobs", kind="RSS", status="recipe",
         note="berlinstartupjobs.com/feed/ CF-challenged from DC; works from residential; Berlin only"),
    dict(id="jobworld",    name="JOBworld", kind="HTML", status="recipe",
         note="alive, no API; SEO search URLs need RE from residential"),
    dict(id="heisejobs",   name="heise.de/jobs", kind="HTML", status="recipe",
         note="503 from DC; unverified"),
    dict(id="jobtensor",   name="jobtensor", kind="HTML", status="recipe",
         note="CF-protected; no public API; IT + Ausbildung Hub; manual or FlareSolverr"),
    dict(id="kalaydo",     name="Kalaydo", kind="HTML", status="recipe",
         note="hub 200 but only category links; detail URL shape needs RE"),
    dict(id="stellenmarkt", name="Stellenmarkt.de", kind="HTML", status="recipe",
         note="200 but category landing pages; SERP detail shape needs RE"),
    # --- BLOCKED (WAF/JS) ----------------------------------------------------
    dict(id="monster",     name="Monster.de", kind="HTML", status="blocked",
         note="403 WAF on every path incl. robots.txt from DC"),
    dict(id="meinestadt",  name="meinestadt.de jobs", kind="HTML", status="blocked",
         note="403 WAF from DC; robots 200; residential needed"),
    dict(id="englishjobs", name="englishjobs.de", kind="HTML", status="blocked",
         note="403 WAF from DC"),
    dict(id="jobscout24",  name="Jobscout24", kind="HTML", status="blocked",
         note="connection reset from DC"),
    dict(id="jobisjob",    name="JobisJob.de", kind="HTML", status="blocked",
         note="403 WAF on all paths"),
    dict(id="jobninja",    name="Jobninja", kind="HTML", status="blocked",
         note="403 WAF"),
    dict(id="wellfound",   name="Wellfound", kind="SPA", status="blocked",
         note="JS-rendered shell, no jobs in __NEXT_DATA__; guest API gone"),
    dict(id="wttj",        name="Welcome to the Jungle (Otta)", kind="SPA", status="blocked",
         note="JS-rendered; state fetched post-load -> Playwright; startup-heavy"),
    # --- DEAD / POLICY -------------------------------------------------------
    dict(id="joblift",     name="Joblift", kind="-", status="dead",
         note="CloudFront error page — service defunct"),
    dict(id="glassdoor",   name="Glassdoor", kind="-", status="dead",
         note="403 even via jobspy; login-walled"),
    dict(id="trovit",      name="Trovit DE", kind="-", status="dead",
         note="connection timeout; effectively gone"),
    dict(id="jobsde",      name="jobs.de", kind="-", status="dead",
         note="botchallenge.html redirect"),
    dict(id="staufenbiel", name="Staufenbiel", kind="-", status="dead",
         note="connection timeout"),
    dict(id="t3n",         name="t3n.de/jobs", kind="-", status="dead",
         note="503 WAF"),
    dict(id="germantechjobs", name="GermanTechJobs", kind="-", status="dead",
         note="public API redirects to jobcopilot signup; data behind auth"),
    dict(id="meinefirma",  name="meinefirma.de", kind="-", status="dead",
         note="broken TLS chain"),
    dict(id="munichstartups", name="Munich-startups jobs", kind="-", status="dead",
         note="jobs subdomain NXDOMAIN"),
    dict(id="azubiyo",     name="azubi.de / ausbildung.de / azubiyo", kind="-", status="policy",
         note="Ausbildung-only boards — excluded by user filter (first job AFTER Ausbildung)"),
    dict(id="stepstone",   name="StepStone", kind="-", status="policy",
         note="RED zone (Akamai + robots); use email alerts instead; coverage exists legally via BA/EURES mirror"),
]

LIVE = [c["id"] for c in CATALOG if c["status"] == "live"]
KEYED = [c["id"] for c in CATALOG if c["status"] == "key"]

def print_catalog(only_fetchable=False):
    rows = [c for c in CATALOG if not only_fetchable or c["status"] in ("live", "key")]
    marks = dict(live="✓ live", key="🔑 key", recipe="🛠 recipe", blocked="✗ blocked",
                 dead="✗ dead", policy="— policy")
    print(f"{'ID':<16} {'STATUS':<11} {'KIND':<16} NAME — note")
    print("-" * 110)
    for c in rows:
        print(f"{c['id']:<16} {marks[c['status']]:<11} {c['kind']:<16} {c['name']} — {c['note'][:80]}")
    n_live = len(LIVE)
    n_key = len(KEYED)
    print("-" * 110)
    print(f"total catalog: {len(CATALOG)} sources | fetchable now: {n_live} live + {n_key} key-gated = {n_live+n_key}")
    print("note: `fetch` is driven by RUN_ORDER (pipeline/sources/__init__.py), not by this status column — RUN_ORDER is the fetch-authoritative list")
