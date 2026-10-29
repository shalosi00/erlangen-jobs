# Task 7-a — Live-test of 4 open-source ATS job-scraping repos (GitHub)

Date: 2026-10-12 · Sandbox: Python 3.12 venv (`/tmp/atsvenv`) · Clones: `research/github-repos/clones/`
Rules honored: read-only public endpoints only, no logins, no api.github.com (quota exhausted — star counts from task brief), ≤15 HTTP req/site.

## Summary table

| # | Repo | What it is | License | Activity | API keys | DE relevance | Live test | Risk | Verdict for 4-layer pipeline |
|---|------|-----------|---------|----------|----------|--------------|-----------|------|------------------------------|
| 1 | elliottdehn/open-jobs | 3.58M-job dataset from 37 ATS + embeddings + LLM-enriched fields; **project shut down 10 Oct 2026**, static snapshot remains downloadable | CC0 1.0 | last commit 2026-10-10 (shutdown commit) | none | 37 ATS incl. personio (3,453 boards), softgarden (773), workday, successfactors; German postings confirmed but fleet is US-heavy | **PASS** — manifest.json HTTP 200 (25.2 MB, built_at 2026-10-05, 7,579,155 jobs incl. 4.0M aggregator boards); export tar HTTP 200 (31.8 GB); group JSON fetched: schema `{ats,slug,id,title,company,location,url,seen,pub,jd,v(1536-dim)}`; 2/352 jobs in one random ML group had DE locations (incl. "Bochum, Nordrhein-Westfalen, Germany") | 🟢 green (CC0, static files, CORS `*`, "no rate limit on /data/") | **ADOPT as one-time snapshot corpus + BORROW freshness-grading idea** (first_seen/verdict model detects re-stamped & ghost postings) |
| 2 | kalil0321/ats-scrapers | PyPI `ats-scrapers` 0.3.0: 70+ scraper adapters (16 ATS + first-party APIs + public sources) **plus** free hosted dataset (5.14M jobs, 80,390 companies, 63 sources, refreshed daily) | MIT | last commit 2026-09-02 (v0.3.0 release) | none | **Excellent**: hosted dataset contains `bundesagentur` = 1,011,761 rows and `eures` = 1,475,850 rows; adapters for Personio, Softgarden, Workday, SuccessFactors, Bundesagentur, EURES, Arbetsformedlingen | **PASS** — `GreenhouseScraper("celonis").fetch()` → 226 jobs, 46 with German location ("Munich, Germany"), correct `posted_at`; hosted manifest JSON verified live (generated_at 2026-10-11); hosted lever CSV slice contains "Berlin, Remote" DACH jobs | 🟢 green for scraper adapters (public JSON boards); hosted dataset = same public data on third-party cloud (stapply.ai), small project → pin version | **ADOPT** (best single repo of the four: scrapers + no-key dataset + BA/EURES mirrors) |
| 3 | adgramigna/job-board-scraper ("Levergreen") | Scrapy spiders (Greenhouse HTML, Lever HTML) → S3 → Postgres → dbt → Airtable/Hightouch → Softr site; daily GH-Actions cron | MIT | last commit 2025-11-26 | none (needs PG + S3 + dbt env) | partial: Lever path fine for DE companies; Greenhouse path broken | **PARTIAL PASS** — Lever spider (robots-obeying) on `jobs.lever.co/360learning` scraped **39/39 items** matching the Lever JSON API exactly, incl. 7 German ("Berlin, Remote") with location/dept/workplace_type; **Greenhouse spider DEAD**: `job-boards.greenhouse.io/robots.txt` now `Disallow: /` → spider obediently scrapes 0 items; Ashby is only a separate `get_ashby_jobs.py` (GraphQL) — no Ashby spider | 🟢 green (robots-obeying code), but repo itself = heavy infra for little gain | **BORROW-IDEA / SKIP as dependency** — borrow "scrape only what robots.txt allows" + `compare_workflow_success.py` (expected-vs-actual scrape-count guard); use Greenhouse **JSON API** (boards-api.greenhouse.io) instead, already covered by repo #2 |
| 4 | rishilahoti/ashby-job-scraper | Node/Docker production system: Ashby+Lever+Greenhouse(+Workable/Recruitee/Teamtailor/Pinpoint/SmartRecruiters/Workday/Keka) → Postgres → change detection → relevance scoring → Next.js UI; self-growing registry via Common Crawl CDX | **MIT + Commons Clause** (non-commercial resale restriction) | last commit 2026-10-09 (active) | none | Ashby endpoint verified for a DE fintech; shipped registry has 146 companies (135 ashby), none German — registry is self-growing, "2k companies/70k jobs" refers to maintainer's instance | **PASS** — repo's own client: `fetchJobBoard('moss','ashby')` → GET `https://api.ashbyhq.com/posting-api/job-board/moss?includeCompensation=true` → 31 jobs, **23 German ("Berlin")**, fields: title/location/isRemote/employmentType/publishedAt/applyUrl/compensation(min,max,currency)/descriptionPlain/secondaryLocations | 🟢 green (public POST/GET JSON, browser UA); license clause ⚠️ | **BORROW-IDEA** — adopt the Ashby endpoint pattern incl. `includeCompensation=true` + its normalize schema; borrow CDX-based board-discovery idea; don't deploy the full stack |

---

## 1. elliottdehn/open-jobs (~381★ per task brief)

**Status: SHUT DOWN 10 Oct 2026** (README banner: "no longer running"; crawler, nightly build and search page offline; last snapshot 5 Oct 2026 "stays downloadable while the bucket is paid for").

**What it did:** Cloudflare Worker + Durable Objects fleet crawling 65,000 career sites across **37 ATS providers** (`slugs.json`, 114k boards incl. gone): ashby 3,048 / bamboohr 2,961 / breezy 3,287 / cornerstone / dark 11,986 ("dark pool" bespoke career sites via schema.org JobPosting JSON-LD) / dayforce / gohire / greenhouse 5,473 / jazzhr / lever 2,203 / paycom 6,602 / paylocity 9,879 / **personio 3,453** / phenom / pinpoint / recruitee 2,603 / smartrecruiters 1,358 / **softgarden 773** / **successfactors 59** / teamtailor 1,532 / ukg / usajobs / workable 6,818 / **workday 3,400** / … Every posting gets `first_seen` (never re-stamped) → nightly estimator grades **fresh / stale / re-stamped / ghost**. LLM enrichment (FIELDS.md): title_normalized, alt_titles, role_family (incl. `it_support`), seniority, years_experience_min/max, education, skills_required, certifications, languages, salary fields, remote/visa, + board-level company resolution (hq_location `{city, region, country_code}`, industry, size_bucket, is_staffing_agency).

**License:** CC0 1.0 Universal (LICENSE = Creative Commons legal code; /data/ index page: "Public files under CC0").

**Downloads (all verified live on 2026-10-12):**
- `HEAD https://backend.dehnbostele.workers.dev/data/exports/open-jobs-latest.tar` → **HTTP 200, 31,802,593,280 B** (~31 GB, one parquet per ATS, resumable).
- `GET .../data/manifest.json` → HTTP 200, 25.17 MB: `{recipe: "text-embedding-3-small:1536:v3", jobs: 3,577,995, jobs_aggregator: 4,001,160, jobs_total: 7,579,155, groups: "groups/2026-10-05/", built_at: 1791204136101, tree: [25,460 nodes / 12,828 leaves]}`.
- `GET .../data/groups/2026-10-05/13149.json` → HTTP 200, 4.5 MB: `{leaf, lo, hi, jobs:[352 × {ats, slug, id, title, company, location, url, seen, pub, jd (≤4k chars), v (base64 float32 1536-dim)}]}`.
- `GET .../data/ledger/index.json` → HTTP 200 (daily ledger of every job ever seen, open or removed).
- No rate limit, CORS `*` ("egress is free — copy at whatever pace suits you"; they ask for a contact in User-Agent).

**Germany coverage:** fleet contains the German-centric ATSes (personio/softgarden + workday/successfactors/greenhouse boards) but is US-heavy overall; random spot check of one software/ML group: 2/352 jobs with DE locations (`lawzero "Berlin; Montreal"`, SonarSource "Bochum, Nordrhein-Westfalen, Germany" via datacareer.de). Country filtering = client-side string filter on `location` (+ board hq_location). No hosted query API anymore (search page offline; `POST /status` endpoint stopped with the shutdown).

**Live-test commands (verbatim, results above):**
```
curl -sI https://backend.dehnbostele.workers.dev/data/manifest.json
curl -sI https://backend.dehnbostele.workers.dev/data/exports/open-jobs-latest.tar
curl -s -A "open-jobs-eval/7-a (...)" .../data/manifest.json -o oj_manifest.json   # 25,167,455 B
curl -s ".../data/groups/2026-10-05/13149.json" -o oj_g13149.json                 # 4,476,586 B
```

**Verdict: ADOPT (one-time snapshot corpus) + BORROW-IDEA (freshness grading).** For our pipeline: (a) optional one-time download of a few DE-relevant parquets (personio/softgarden/greenhouse slices) via DuckDB for historical posting-lifetime stats; (b) the first_seen + verdict-model idea is the best anti-ghost-job mechanism seen anywhere — implement with our own crawler state (jobs table with first_seen_at, changed_at, removed_at exactly as their schema). Not a live feed.

---

## 2. kalil0321/ats-scrapers (~173★ per task brief)

**What it is (two layers):**
1. **Free hosted dataset** — manifest `https://storage.stapply.ai/jobhive/v1/manifest.json` (verified 2026-10-11 build): `stats: {ats_count: 63, total_companies: 80,390, total_jobs: 5,140,934, schema_version: "2.0"}`, per-source CSV + parquet artifacts with sha256. **Schema (27 cols):** url, title, company, ats_type, ats_id, location, **country_iso, region, language, lat, lon**, is_remote, salary_min/max/currency/period/summary, employment_type, department, team, description, posted_at, requisition_id, apply_url, commitment, raw.
   - **Germany-relevant slices:** `bundesagentur` **1,011,761 rows** (1.18 GB CSV) and `eures` **1,475,850 rows** (3.5 GB CSV) — literally mirrors of the two APIs we validated in phase 2-a; plus greenhouse 178,903, lever 72,681, workday?, smartrecruiters?, personio? etc. (63 sources total).
2. **Scraper adapters** (pip `ats-scrapers`, MIT): ~70 modules — Workday, Greenhouse, Lever, Ashby, SmartRecruiters, SuccessFactors, **Personio**, **Softgarden**, Oracle, iCIMS, Paycom, Keka, Workable, ADP + first-party (Amazon/Apple/Google/TikTok/Uber/Meta/Tesla) + **public sources: EURES, Bundesagentur, Arbetsformedlingen**, Welcome to the Jungle, RemoteOK, WWR, YC. Company directory `ats-companies/*.csv` = 80,437 companies with slugs (Celonis confirmed in greenhouse.csv; German companies in personio.csv).

**Install notes:** base deps httpx/pydantic/pandas (pure-python). `from ats_scrapers.scrapers import …` pulls ALL adapters → needs `beautifulsoup4` + `html2text` (light); heavy stealth extras (`httpcloak`, `cloakbrowser` — bundled Chromium!, `pycryptodome`) only for Avature/JazzHR/Moka/Tesla/Meta — **not needed** for the standard ATS boards. PEP 668: use a venv.

**Live test (PASS):**
```
python3 -m venv /tmp/atsvenv && /tmp/atsvenv/bin/pip install ats-scrapers aiohttp beautifulsoup4 html2text
from ats_scrapers.scrapers import GreenhouseScraper
jobs = GreenhouseScraper("celonis").fetch()
→ 226 jobs; 46 with German location ("Munich, Germany"); posted_at parsed (tz-aware)
→ endpoint used: https://boards-api.greenhouse.io/v1/boards/celonis/jobs?content=true
sample: "Associate Account Executive (Top Talent Sales Program - Lunar)" | Munich, Germany | 2026-08-25
note: country_iso/region/language are null on raw scraper objects (filled only in hosted dataset)
```
Also verified hosted lever CSV (25 MB range-request of 352 MB) contains German jobs: 360learning "Business Development Representative DACH (m/f/d)" — "Berlin, Remote".

**Risk:** 🟢 green — public JSON boards, no auth; hosted dataset is the same public data re-hosted (no key, no account). Caveats: one-maintainer project (v0.3.0, Sep 2026) → pin version, don't blind-trust schema stability; hosted storage is `stapply.ai` (third-party, undocumented ToS — fine for caching-style use, don't make it a single point of failure; the BA/EURES slices duplicate sources we already fetch ourselves).

**Verdict: ADOPT.** Best of the four: use (a) scraper adapters as reference implementations / fallback for ATS we haven't hand-coded, (b) the hosted dataset as a discovery source ("which companies use which ATS", incl. German slugs) and as cross-check for our own BA/EURES pulls.

---

## 3. adgramigna/job-board-scraper — "Levergreen" (~46★ per task brief)

**What it is:** Personal-scale production pipeline: Scrapy spiders (2× Greenhouse HTML, 1× Lever HTML) → raw HTML to S3 → Postgres (Neon) → dbt transforms → Hightouch reverse-ETL → Airtable → Softr website (levergreen.dev). Daily cron via GitHub Actions. Also `get_ashby_jobs.py` (Ashby **GraphQL** `https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams`, queries/ashby_jobs_outline.graphql, variables `{organizationHostedJobsPageName}`) and `get_rippling_jobs.py`. No Ashby/Lever JSON-API spider — Greenhouse/Lever are scraped as **HTML pages with XPath**, not the JSON APIs.

**License:** MIT (c) 2023 Andrew Gramigna. Last commit 2025-11-26 ("update department xpath").

**Live tests:**
1. **Lever spider — PASS.** With repo-pinned `scrapy==2.10.1` (+ w3lib 2.1.2/parsel 1.8.1; scrapy 2.19 **silently yields 0 start requests** with this codebase — pin matters!), robots-obeying (jobs.lever.co robots.txt = `Allow: /, Crawl-delay: 1`), run against a Lever-hosted company with DE office (360learning, found via the hosted CSV of repo #2):
   - `ITEMS SCRAPED: 39` (== JSON API count 39), `GERMAN-LOCATION ITEMS: 7` (== API 7)
   - item fields: opening_title, location, department_names, workplace_type, opening_link, company_name, id/created_at/updated_at/run_hash/source
   - sample: "Trainer EMEA | loc='Berlin, Remote' | dept=Customer Success – Learning Engagement"
   - harness patches needed: `ITEM_PIPELINES={}` (skip Postgres), monkey-patch `export_html` (spider ALWAYS uploads raw HTML to S3), provide `S3_HTML_BUCKET` + `HASHIDS_SALT` env.
2. **Greenhouse spider — DEAD for compliant use.** `https://job-boards.greenhouse.io/robots.txt` now says `User-agent: * / Disallow: /` → with the repo's own `ROBOTSTXT_OBEY=True` the spider fetches robots (200) and scrapes **0 items** (verified by running it on Celonis). Greenhouse changed their board hosting/templates since the repo was written.
3. (Cross-check) Lever JSON API `api.lever.co/v0/postings/360learning?mode=json` → 200, 39 postings, 7 DE — exact match with the spider output. Note: 9 of 10 well-known company slugs I probed (taxfix, moss, getyourguide, soundcloud, choco, wolt, pitch…) → 404 on Lever (companies left Lever / custom domains) — expect a rotten company list in any Lever project.

**Germany relevance:** partial — Lever path works fine for DE offices; Greenhouse path must go through the JSON API (not this repo's scraper).

**Risk:** 🟢 green (robots-obeying, polite delays) — but the repo drags in S3+Postgres+dbt+Hightouch+Airtable+Softr for what we need; the valuable parts are two ideas.

**Verdict: BORROW-IDEA / SKIP as dependency.** Borrow: (a) robots.txt-first scraping stance (their greenhouse spider quietly dying when Greenhouse flipped robots.txt is the perfect cautionary tale — exactly why our pipeline should prefer the boards-api JSON); (b) `compare_workflow_success.py` guard (expected-vs-actual scraped-boards count, alert on drift); (c) content-hash change tracking per posting.

---

## 4. rishilahoti/ashby-job-scraper (~51★ per task brief)

**What it is:** Production-grade **Node.js** system (not Python): Docker Compose (scraper + Postgres 17 + watchtower), Next.js 16 frontend on Vercel, daily cron + jitter, change detection via content hashing, relevance scoring (keyword/location/remote/department/freshness rules engine — with **German keywords built in**: Vertrieb, Kundenservice, Buchhaltung, Informatik…), localStorage apply/ignore tracking, Markdown reports. Sources: ashby, lever, greenhouse + workable, recruitee, teamtailor, pinpoint, smartrecruiters (+ dedicated workday/keka fetchers). **Self-growing registry:** daily Common Crawl CDX discovery (`node index.js discover --source ashby|greenhouse`) → verify candidates against the live API → auto-add. Notes Lever blocks Common Crawl's bot (robots.txt) → Lever companies need manual `site:jobs.lever.co` search.

**License:** **MIT + Commons Clause v1.0** — source free to use, but may not be *sold*. Fine for a personal/non-commercial toolkit; flag for anything commercial.

**Registry:** shipped `src/sources/registry.json` = **146 companies (135 ashby, 6 greenhouse, 5 lever)** — OpenAI, Notion, Ramp, Anthropic-type US startups; **no German companies**. The "70k jobs / 2k companies" figure describes the maintainer's own grown instance, not the repo.

**The Ashby endpoint it uses (verified):**
```
GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
→ {jobs: [...]}  (no auth, no key)
```
(This is the REST posting-API, not the `jobs.ashbyhq.com/api/non-user-listing/{uid}` page API nor the GraphQL op used by Levergreen.)

**Live test (PASS, via the repo's own `fetchJobBoard` client, no DB needed):**
```
const { fetchJobBoard } = require('./src/fetch/client');
const { jobs } = await fetchJobBoard('moss', 'ashby');
→ log: "Fetched 31 jobs from moss (ashby)"
→ GERMAN-LOCATION JOBS: 23  ("Customer Success Manager (f/m/d)" | Berlin | FullTime | publishedAt 2025-04-07 | applyUrl jobs.ashbyhq.com/moss/…/application | compensation {min,max,currency})
raw job keys: address, applyUrl, compensation, department, descriptionHtml, descriptionPlain, employmentType, id, isListed, isRemote, jobUrl, location, publishedAt, secondaryLocations, shouldDisplayCompensationOnJobPostings, team, title, workplaceType
probe notes: parloa/sennder/wfox/etc → 404 (gone or never), choco → 200 (1 job), moss → 200 (31)
```
Normalize layer extracts salary min/max/currency/interval from `compensation.summaryComponents` (Salary component only), `normalizeLocation(raw.location, raw.isRemote)`, department grouping rules incl. German terms.

**Risk:** 🟢 green for the endpoint (public JSON, browser-like UA, 2–10 s delays between companies in their scheduler); ⚠️ license = MIT + Commons Clause; ⚠️ `rejectUnauthorized:false` SSL in their DB code (self-signed certs) — irrelevant if we only borrow the fetch pattern.

**Verdict: BORROW-IDEA.** (a) Adopt the `api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` pattern + their normalize schema (salary + secondaryLocations + employmentType) — this is the cleanest documented Ashby feed of the four repos; (b) borrow the Common-Crawl-CDX board-discovery loop (cheap way to grow a company→ATS registry automatically); (c) don't deploy the Docker/Postgres/Next stack — we already have our own pipeline shape.

---

## Cross-repo takeaways for our 4-layer pipeline

1. **ATS JSON feeds remain the green backbone** — all four repos, like our phase 2-d work, ultimately rely on the same public endpoints: `boards-api.greenhouse.io/v1/boards/{slug}/jobs`, `api.lever.co/v0/postings/{slug}?mode=json`, `api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true`, `api.smartrecruiters.com/v1/companies/{slug}/postings`, Personio `/xml`, Workday CXS. Repo #2 packages these best (70+ adapters, typed schema) → **ADOPT**.
2. **Germany data is real but fragmented** — repo #2's hosted dataset is the only one with native DE mass data (BA 1.01M + EURES 1.48M rows, refreshed daily, no key) and DE-aware adapters (Personio/Softgarden). open-jobs has German postings inside a US-heavy 3.58M corpus (frozen). Ashby/Lever per-company fetches work fine for DE offices (Moss/Berlin, 360learning/Berlin, Celonis/Munich verified).
3. **robots.txt is a live risk, not theory** — Greenhouse flipped `job-boards.greenhouse.io/robots.txt` to `Disallow: /`, silently killing repo #3's HTML spider (it obeyed and scraped 0). Prefer JSON APIs; add an expected-vs-actual scrape-count guard (repo #3's best idea).
4. **Freshness/ghost-job grading is a differentiator worth stealing** from open-jobs (first_seen never re-stamped + fresh/stale/re-stamped/ghost verdicts; full schema in their backend/DOCS.md).
5. **Company→ATS discovery**: repo #2 ships 80k company-slugs per ATS (CSV), repo #4 grows a registry via Common Crawl CDX, open-jobs shipped 114k boards incl. a "dark pool" of bespoke career sites. For our DE watchlist: use repo #2's CSVs + `site:` searches; consider CDX discovery as a later enhancement.
6. **Pitfalls recorded**: scrapy 2.13+ silently yields 0 requests for old `start_requests`-style spiders (pin scrapy==2.10.1 if ever using repo #3); `ats_scrapers.scrapers` needs bs4/html2text extras; open-jobs is CC0 but FROZEN (no updates after 2026-10-05); ashby-job-scraper is Commons-Clause + Node (license + stack mismatch).

HTTP request budget used: workers.dev ~6, storage.stapply.ai 2, greenhouse family ~7, api.lever.co 11, jobs.lever.co ~6, api.ashbyhq.com 10 — all ≤15/site, all read-only.
