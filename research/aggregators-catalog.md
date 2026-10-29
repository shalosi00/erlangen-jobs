# Aggregator Master Catalog — 55 sources probed, 20 fetchable (2026-10-13)

Companion to `pipeline/` (the CLI). Legend:
- **live** = fetchable right now by the pipeline, no key, no proxy
- **key** = fetchable after a free API-key registration (activate via env var)
- **recipe** = blocked from this datacenter IP; concrete bypass documented below
- **blocked / dead / policy** = not viable, reason recorded so nobody retries blindly

Probe evidence: `research/aggregators-round2/probe/` (incl. `r7_summary.json`),
probe scripts `scripts/probe_aggregators_r1..r7.py`.

## 1. Fetchable NOW — pipeline source ids

| # | id | Source | Method (verified live) | Notes for FISI/Erlangen |
|---|----|--------|------------------------|-------------------------|
| 1 | `ba` | Bundesagentur für Arbeit v6 | REST JSON, static public key `jobboerse-jobsuche`; `angebotsart=1` + `pav=false` + `umkreis=50` + `veroeffentlichtseit=14` | Authoritative geo+date; v4 jobdetails (base64 refnr) powers experience/parttime filters |
| 2 | `xing` | XING Jobs | Logged-out SSR page embeds `jobSearchByQuery` GraphQL result in `serverData.APOLLO_STATE` (brace-match parser) | Structured `employmentType` incl. Vollzeit, salary min/max/median; yellow zone: 1 req/poll |
| 3 | `eures` | EURES (EU portal) | POST `europa.eu/eures/api/jv-searchengine/public/jv-search/search` | Full text in search response; mirrors BA + EU cross-border; `positionScheduleCodes` available |
| 4 | `infranken` | Jobs.InFranken.de | HTML: `/suchergebnisse?Searchterm=`; per-card `date-company-city` + `job-description` | Franconia SMEs invisible on StepStone/Indeed; dates+descriptions in SERP |
| 5 | `getinit` | Get-in-IT | HTML: `/jobsuche?was=&wo=`; `CardJob_jobTitle` + logo `title` attr | IT-only board → less noise |
| 6 | `connecticum` | Connecticum | HTML: `/jobs?searchterm=&submit=1`, page pagination | Junior/graduate demographic |
| 7 | `berufsstart` | Berufsstart.de | HTML: `ergebnisliste.php?suchbegriff=` | Country-wide → pipeline geo-filters; entry-level focus |
| 8 | `talent` | Talent.com DE | HTML: `de.talent.com/jobs?k=&l=`; JSON-LD `#jobList` + h2 blocks | Long-tail aggregator incl. kununu-sourced ads |
| 9 | `arbeitnow` | Arbeitnow | JSON `arbeitnow.com/api/job-board-api` (no key, 325/page) | Client-side keyword+geo filter; attribution per terms |
| 10 | `indeed` | Indeed DE | python-jobspy guest mode (`hours_old`, `country_indeed='germany'`) | `pip3 install python-jobspy`; 429 → back off |
| 11 | `linkedin` | LinkedIn | python-jobspy guest mode, no login | Low volume; 429s common; keep polite |
| 12 | `remotive` | Remotive | JSON `remotive.com/api/remote-jobs?limit=100` | Remote; 24 h delay; attribution |
| 13 | `remoteok` | RemoteOK | JSON `remoteok.com/api` (element 0 = legal notice) | Remote; `tags` incl. sysadmin |
| 14 | `jobicy` | Jobicy | JSON `jobicy.com/api/v2/remote-jobs?count=50` (v2 verified 200) | Remote; credit + redirect to source |
| 15 | `wwr` | We Work Remotely | RSS `remote-devops-sysadmin-jobs.rss` + `remote-programming-jobs.rss` | Remote; title format "Company: Role" |
| 16 | `himalayas` | Himalayas | RSS `himalayas.app/jobs/rss` | Remote |

## 2. Fetchable after FREE key registration (env vars → auto-enabled)

| # | id | Source | Env vars | Where to register | Free tier |
|---|----|--------|----------|-------------------|-----------|
| 17 | `adzuna` | Adzuna DE | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | developer.adzuna.com | 25 calls/min, 250/day; salary data |
| 18 | `jooble` | Jooble | `JOOBLE_API_KEY` | jooble.org/api | ~500 req/key |
| 19 | `careerjet` | Careerjet v4 | `CAREERJET_AFFID` | careerjet.com/partners/api | affiliate; API DC-blocked → run from home IP |
| 20 | `whatjobs` | WhatJobs | `WHATJOBS_PUBLISHER_KEY` | whatjobs affiliate program | publisher feed |

## 3. Recipes — blocked from THIS datacenter, concrete bypass documented

| # | Source | Blocker | Bypass recipe |
|---|--------|---------|---------------|
| 21 | Kimeta.de (~1 M listings) | nginx 503 + connection reset | SEO URL `kimeta.de/{keyword}-jobs-{city}` from residential proxy; server-rendered HTML |
| 22 | Jobvector | Cloudflare JS challenge | FlareSolverr / Playwright-stealth; white-label twin `jobs.sueddeutsche.de` |
| 23 | Stellenanzeigen.de | CF JS challenge | FlareSolverr; SERP `/suche/?what=&where=` |
| 24 | Gigajob | CF 401 | FlareSolverr; historic RSS dead |
| 25 | Yourfirm | CF 403 | FlareSolverr |
| 26 | Jobrapido.de | hard 403 IP block | residential proxy only |
| 27 | Jobware | path-level DC rate limit | Playwright, 1 req/30 s |
| 28 | Absolventa | JS-rendered results | params known: `/jobs?query[keywords][]=X&query[cities][]={city}-de-{region}`; Playwright; keyless autocomplete API `/api/p/autocompletes/absolventa?q=` |
| 29 | Interamt (public sector) | Angular SPA | record XHR once in Playwright, replay; Stadt Erlangen IT roles appear here first |
| 30 | FAU Jobbörse | unreachable from DC | plain board from any German residential IP |
| 31 | Berlin Startup Jobs | CF challenge | RSS `/feed/` from residential; Berlin only |
| 32 | JOBworld | no API, HTML only | SEO search URLs need RE from residential |
| 33 | heise.de/jobs | 503 from DC | unverified; retry from residential |
| 34 | jobtensor | CF + no API | manual or FlareSolverr; IT + Ausbildung Hub |
| 35 | Kalaydo | hub OK, detail shape unknown | category pages 200; detail URL RE needed |
| 36 | Stellenmarkt.de | SERP = category landings | detail-link shape RE needed |

## 4. Blocked / dead / policy (do NOT retry)

| # | Source | Status | Reason |
|---|--------|--------|--------|
| 37 | Monster.de | blocked | 403 WAF on every path incl. robots.txt |
| 38 | meinestadt.de jobs | blocked | 403 WAF (robots 200) |
| 39 | englishjobs.de | blocked | 403 WAF |
| 40 | Jobscout24 | blocked | connection reset |
| 41 | JobisJob.de | blocked | 403 all paths |
| 42 | Jobninja | blocked | 403 |
| 43 | Wellfound | blocked | JS shell; guest API gone; no jobs in `__NEXT_DATA__` |
| 44 | Welcome to the Jungle (Otta) | blocked | state fetched post-load → Playwright; startup-heavy |
| 45 | Joblift | dead | CloudFront "request could not be satisfied" — defunct |
| 46 | Glassdoor | dead | 403 even via jobspy; login-walled |
| 47 | Trovit DE | dead | connection timeout |
| 48 | jobs.de | dead | `botchallenge.html` |
| 49 | Staufenbiel | dead | connection timeout |
| 50 | t3n.de/jobs | dead | 503 WAF |
| 51 | GermanTechJobs | dead | public API redirects to jobcopilot signup |
| 52 | meinefirma.de | dead | broken TLS chain |
| 53 | Munich-startups jobs | dead | jobs subdomain NXDOMAIN |
| 54 | azubi.de / ausbildung.de / azubiyo | policy | Ausbildung-only boards — excluded by hard filter (first job AFTER Ausbildung) |
| 55 | StepStone | policy | RED zone (Akamai, robots); email alerts instead; BA/EURES mirror covers the same ads legally |

## 5. Pipeline usage

```bash
cd /home/z/my-project
PY=/home/z/.venv/bin/python3
$PY -m pipeline sources                      # full catalog table
$PY -m pipeline fetch                        # all live sources, hard filters ON
$PY -m pipeline fetch --days 7 --sources ba,xing,infranken,getinit
ADZUNA_APP_ID=... ADZUNA_APP_KEY=... $PY -m pipeline fetch   # auto-enables adzuna
```

Outputs land in `download/`: `jobs_<query>-<city>-<radius>-<days>_<ts>.csv` + `.json`
+ `_rejected.csv` (audit of every filtered row with reason), plus stable aliases
`jobs_latest.csv` / `jobs_latest.json`. Run logs: `logs/pipeline_run_*.log`.

Hard filters always ON: **no Ausbildung**, **no part-time/minijob**, **no
experience-required** (title + description regexes), **full-time only**
(structured field or description; rows without any signal are kept but flagged
`ft_unknown` for one-click filtering in Excel). Dedupe = exact + near-dupe
(title+city, company-token overlap), sources merged into `source` column.

## 6. Count check

**55 cataloged** — 16 live + 4 key-gated = **20 fetchable**; 16 recipes; 8 blocked; 5 dead; 2 policy. Catalog goal of 40 reached with margin; every blocked entry carries its exact bypass recipe or a do-not-retry reason.
