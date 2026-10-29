# GitHub Open-Source Ecosystem Survey — Programmatic Job Search

**Date:** 2026-10-12 · **Phase:** 3 (post-PDF) · **Method:** 18 web-search queries + 8 GitHub Search
API categories + prior-session search files → 87 unique candidates → 30+ triaged → **11 repos deep-tested
(4 live-tested against real endpoints, 6 code-inspected, 1 fully exercised)**.

---

## TL;DR — what to adopt for Asha's pipeline

| # | Repo | Stars* | License | Verdict | Why |
|---|------|-------:|---------|---------|-----|
| 1 | **speedyapply/JobSpy** (`pip install python-jobspy`) | 4,463 | MIT | **ADOPT — verified live** | Indeed DE + LinkedIn guest both work WITHOUT credentials/keys; 32-col normalized schema incl. salary |
| 2 | **kalil0321/ats-scrapers** (`pip install ats-scrapers`) | 173 | MIT | **ADOPT — verified live** | 70+ ATS adapters + free no-key hosted dataset (5.14 M jobs, 80,390 companies, BA/EURES mirrors, refreshed daily) |
| 3 | **jutt7/JobHunter** | 1 | MIT | **ADOPT (fork-adapt)** | It *is* our chapter-10 blueprint in code: BA v6 + LLM score + digest; 38 offline tests pass; adds `angebotsart=1`, `pav=false`, v4-details recipe |
| 4 | **career-ops-hq/career-ops** | 74,093 | MIT | **BORROW (reference base)** | 118 no-auth provider modules incl. `arbeitsagentur.mjs`, Personio/SoftGarden, Deutsche Bahn; eval rubric; BA v6 remote-mode recipes |
| 5 | **elliottdehn/open-jobs** | 381 | CC0 | BORROW (frozen corpus) | Shut down 2026-10-10 but 31.8 GB CC0 snapshot still downloadable; best anti-ghost-job freshness schema |
| 6 | rishilahoti/ashby-job-scraper | 51 | MIT + **Commons Clause** | BORROW pattern | Verified `api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` (Moss Berlin: 31 jobs, 23 DE) |
| 7 | adgramigna/job-board-scraper | 46 | MIT | BORROW process guard | Lever spider works (39/39, 7× Berlin); **Greenhouse HTML now robots-Disallow** → use boards JSON API |
| 8 | Gsync/jobsync | 1,390 | MIT | SKIP (MCP idea) | Self-hosted tracker over Greenhouse/Lever/Ashby only; no DE sources |
| 9 | DaKheera47/job-ops | 4,003 | **AGPL-3.0 + Commons Clause** | SKIP (license trap) | Runs jobspy+Adzuna+Apify; DE-weak; NOT MIT — do not fork |
| 10 | vesaias/JobNavigator | 152 | MIT | SKIP | Logged-in LinkedIn automation = our red zone; US-centric |
| 11 | borgius/jobspy-mcp-server | 117 | MIT | optional | Exposes JobSpy via MCP — only relevant if Asha uses Claude Desktop |

*stars at test time, 2026-10-12.

---

## 1. Headline live-test result (main agent, venv, python-jobspy 2.x)

```
indeed_fisi_erlangen       15 rows ✅  (real FISI postings: InnoSenT Donnersdorf 2026-10-08,
                                       Frankana Gollhofen FISI Systemintegration, …)
indeed_itsupport_nuremberg 15 rows ✅  (NETWAYS Ausbildung SI 2027, Paessler, grey engineering 52–72k EUR)
linkedin_guest             10 rows ✅  (NO login, NO proxy needed — Germany-wide Systemintegration)
glassdoor_guest             0 rows ❌  (403 — consistent with our RED-zone classification)
```

**This changes the PDF risk matrix in one spot:** Indeed & LinkedIn *guest reads via JobSpy's
maintained guest endpoints* are feasible today at low volume (treat as YELLOW: hourly cadence,
≤100 req/d, back off on 403) — while raw scraping and Glassdoor stay RED. All 4 CSVs saved under
`tests/jobspy_*.csv` with 32-column schema (`title, company, location, date_posted, min/max_amount,
currency, is_remote, job_url, description, …`).

**Caveats observed:** LinkedIn guest returns senior-heavy results for broad terms (needs
location + `google_search_term` tuning); salary fields sparse on Indeed DE; `hours_old` filter works.

## 2. ATS layer (subagent 7-a) — all 4 hit real public endpoints

- **ats-scrapers** = best single find: `GreenhouseScraper("celonis").fetch()` → 226 jobs, 46 German.
  Hosted dataset `https://storage.stapply.ai/jobhive/v1/manifest.json` re-verified by main agent:
  **63 sources, 80,390 companies, 5,140,934 jobs, generated 2026-10-11** — contains
  `bundesagentur` 1,011,761 rows + `eures` 1,475,850 rows (mirrors of OUR validated APIs),
  plus a company→ATS directory with German Personio/Softgarden slugs. 27-col schema with
  `country_iso/lat/lon/language/salary`. ⚠️ one-maintainer project → pin `ats-scrapers==0.3.0`;
  treat hosted mirror as cross-check, never as source of truth.
- **open-jobs**: project sunset 2026-10-10, but CC0 export tar (31.8 GB) + manifest still HTTP 200;
  7.58 M jobs from 37 ATS with full JD + 1536-dim embeddings; German postings present but fleet US-heavy.
  **Borrow its freshness grading** (first-seen / never-re-stamped "ghost" detection) for our CSV tracker.
- **Ashby pattern**: public `posting-api/job-board/{slug}?includeCompensation=true` — key additions for
  our ATS layer 2 (Moss/Berlin verified). Commons Clause = fine for personal use.
- **Structural discovery:** `job-boards.greenhouse.io/robots.txt` flipped to `Disallow: /` — HTML
  scrapers that obey robots die; **JSON `boards-api.greenhouse.io` unaffected** (our green path stands).

## 3. AI agents & platforms (subagent 7-b)

- **career-ops-hq/career-ops** (74k★, pushed 2026-10-12): Markdown-prompt agentic workflow + ~200
  Node `.mjs` scripts; **118 no-auth providers** — confirms our entire source map and extends it
  (BambooHR, Teamtailor, Phenom, iCIMS, Taleo, VDAB, single-company modules incl. Deutsche Bahn
  db.jobs/Avature). Documents BA v4/v5 endpoints 404 since 2026-08 and v6 `homeoffice` recipes.
  No credentials, no forced LLM keys (Ollama works). → steal provider-registry architecture.
- **jutt7/JobHunter**: 2,036 lines, GitHub-Actions cron daily, BA v6 search + **v4 jobdetails
  (`base64(refnr)` — v6 details still 403, corroborates our finding)**, strict-JSON LLM scoring,
  `pav=false` (filters private agencies!) + `angebotsart=1`, dedupe key = company + gender-neutral
  title + PLZ (BA refreshes dates), seen-after-send, budget cap. 38 unit tests pass in our sandbox.
  → fastest path to a working Phase-4 prototype: fork + swap in our FISI/Erlangen profile.
- Consensus architecture across cohort = exactly our ch. 10 design: *fetch → stable-key dedupe →
  free pre-filter → budget-capped strict-JSON LLM score → threshold → digest*.
- **Nobody covers XING/StepStone** — our SSR/Apollo-state differentiator stands.

## 4. Master directory (candidates not deep-tested)

Germany/BA ecosystem (from phase 2-a files + wave-2 searches): `bundesAPI/jobsuche-api` (161★, OpenAPI
codegen), `wunderfrucht/jobsuche` (Rust client, 2026-06), `philippolis/jobsuche-agent` (Python filter
agent), `vlzware/JobSuche-Py` (LLM matching), `hansdoebel/n8n-nodes-jobsuche` (n8n node),
`kemdev/jobsuche-api-js` (TS), `AndreasFischer1985/*-api` series (BERUFENET, Ausbildung, Entgeltatlas …),
`pashtetx/arbeitsagentur-notifier`, `yanucodes/job-search-tool` (tracker, 2026-09-30).

Other notables: `PaulMcInnis/JobFunnel` (2,193★ but **ARCHIVED**), `nicolomantini/LinkedIn-Easy-Apply-Bot`
(1,154★, auto-apply = red zone), `GodsScion/Auto_job_applier_linkedIn` (2,928★, same), `Donvink/swiss-job-hunter`
(147★, CH cross-border option), `Stupidoodle/swissdevjobs-cli` (102★, salary-transparent DACH),
`pinloop-ai/pinloop-cli` (557★, needs OAuth login; provenance risk), `emredurukn/awesome-job-boards`
(1,077★, board directory), `rainmanjam/jobspy-api` (381★, Dockerized JobSpy with key auth),
`t0mer/Applyfy`, `qpwm06/QuickApply`, `alpharomercoma/ts-jobspy` (TS port), `DaKheera47/jobspy-node`.
Auto-apply bots (LinkedIn/Wellfound/hh.ru/Boss直聘: `Anshul439/job-auto-apply`, `Vlad9572324/hh.ru-clicker`,
`jolie-z/Auto-JobHunter` …) = **RED ZONE — account-ban risk; not tested, not recommended.**

## 5. Updated pipeline mapping (PDF ch. 5 layers)

| Layer | PDF baseline | Add from survey |
|-------|--------------|-----------------|
| L1 official APIs | BA v6 (own client), EURES, Arbeitnow, Adzuna, Jooble | + JobHunter's `angebotsart=1`/`pav=false`/v4-details recipes; career-ops v6 remote modes |
| L2 ATS feeds | Workday, SmartRecruiters, Personio, feed.xml (hand-coded) | + `ats-scrapers` adapters + hosted company→ATS directory; + Ashby `posting-api` pattern |
| L3 aggregator reads | XING SSR, LinkedIn guest (hand-rolled) | + **python-jobspy** replaces hand-rolled LinkedIn/Indeed guest code (maintained, 4.4k★) |
| L4 red zone | StepStone/Indeed/Glassdoor scraping | unchanged — Glassdoor 403 re-confirmed; Greenhouse HTML dead (robots), JSON alive |

## 6. Risks & license traps found

1. `job-ops` looks MIT-like in badges but is **AGPL-3.0 + Commons Clause** → never copy code into our repo.
2. `ashby-job-scraper` MIT + **Commons Clause** (no commercial resale) — fine for personal job hunt.
3. `open-jobs` data is **CC0** (safe), but frozen → use for statistics only.
4. JobSpy guest endpoints are undocumented portal reads → keep YELLOW discipline (low volume, no auth).
5. Auto-apply bots violate portal ToS and risk account bans — excluded from adoption.
6. Small-maintainer deps (`ats-scrapers`, `jobspy-mcp-server`) → pin versions, vendor critical adapters.

## 7. Recommended Phase-4 build order

1. `git` repo skeleton `pipeline/` with BA v6 fetcher (own code + JobHunter recipes) → CSV tracker.
2. Add JobSpy source (Indeed DE + LinkedIn guest, hourly, `hours_old=72`) — merge into same CSV.
3. Add `ats-scrapers` for Greenhouse/Lever/Personio/Softgarden boards of the Erlangen employer map.
4. Optional LLM scoring slot (strict-JSON, budget-capped) + digest — port from jutt7/JobHunter.
5. Keep open-jobs freshness-grading idea in the tracker schema (`first_seen`, `last_seen`, `ghost_flag`).

Artifacts: `tests/7-a_ats_layer.md`, `tests/7-b_agents_platforms.md`, `tests/jobspy_*.csv`,
`gh_search/_index.json`, `candidates.json`, clones under `clones/` (gitignored).
