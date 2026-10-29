# Programmatic Job Hunting — Germany (FISI Edition)

Toolkit + research for finding a first IT job (Fachinformatiker Systemintegration & adjacent
junior IT roles) around **Erlangen / Bavaria** using official APIs, ATS feeds and
low-risk scraping — built around the "apply within 72 h" advantage.

## Contents

| Path | What it is |
|------|------------|
| `download/Programmatic_Job_Hunting_Germany_Systemintegration.pdf` | 30-page deep-dive report: data sources, legal risk matrix (green/yellow/red), 4-layer pipeline architecture, 14-day action plan |
| `download/cover_source.html` | Editable cover source for the report |
| `research/2-a` | Bundesagentur für Arbeit Jobsuche v6 API live validation + EURES API + community clients |
| `research/2-b` | XING SSR / LinkedIn guest endpoints feasibility |
| `research/2-c` | Aggregator APIs (Arbeitnow, Adzuna, Careerjet, Jooble) |
| `research/2-d` | ATS direct feeds (Workday, SmartRecruiters, Personio, feed.xml) + Erlangen employer map |
| `research/2-e` | Train-commute analysis (VGN GTFS → 29 zero-transfer towns ≤60 min) |
| `research/2-f` | Legal (§87b UrhG, BGH precedent), market stats, keyword corpus |
| `research/github-repos/` | Survey of open-source GitHub repos for programmatic job search |
| `research/aggregators-round2/` | Round-2: 24 German aggregator boards probed (kimeta & co) — 5 live-working recipes, 11 bypass recipes, probe evidence |
| `research/aggregators-catalog.md` | **Master catalog: 55 aggregator sources probed — 22 fetchable (18 live + 4 free-key), every blocked one with bypass recipe or do-not-retry reason** |
| `pipeline/` | **Unified fetcher CLI (`python -m pipeline fetch|sources`): 22-source RUN_ORDER → hard filters → dedupe → CSV/JSON/audit** |
| `scrapers/` | Legacy working scrapers: `aggregator_search.py` = unified 5-board search → date-sorted CSV |
| `scripts/` | Report build + pipeline blueprints + probe scripts (r1…r7) |
| `BACKUPS.md` | Where everything is mirrored (gofile, surge.sh) + restore instructions |

## Key validated sources

- **BA Jobsuche API v6** — `rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs`, key `jobboerse-jobsuche` (238 FISI jobs ≤50 km Erlangen)
- **EURES** (no auth, 8.5k DE listings), **Arbeitnow** (no key), **Adzuna/Jooble** (free keys)
- **ATS direct feeds** beat portals: DATEV, Schaeffler, GfK, adidas, PUMA, Hetzner …
- **Round-2 aggregators, working today with plain requests:** Connecticum, Get-in-IT,
  Berufsstart.de, Jobs.InFranken.de (local Franconia!), Talent.com DE → `scrapers/aggregator_search.py`
- **Blocked from DC, recipes documented:** Kimeta (residential proxy), Jobvector/Gigajob/
  Yourfirm/Stellenanzeigen.de (FlareSolverr), Absolventa (Playwright, params reverse-engineered),
  Careerjet (free API key, run from home IP)

## Quick start

```bash
# venv restore (sandbox wipes it periodically — F7/F9 self-heal):
python3 -m venv /home/z/.venv && /home/z/.venv/bin/pip install -r requirements.txt

PY=/home/z/.venv/bin/python3        # needs requirements.txt (jobspy, sqlite-utils, ...)

# 1) see all 55 aggregator sources and their status/access method
$PY -m pipeline sources

# 2) fetch everything, hard filters ON (no Ausbildung, no part-time,
#    no experience-required, full-time only), sorted by date
$PY -m pipeline fetch

# 3) selective / custom
$PY -m pipeline fetch --query "IT-Support" --city Erlangen --radius 50 --days 7 \
        --sources ba,xing,infranken,getinit,talent

# 4) unlock key-gated sources (free registrations)
ADZUNA_APP_ID=... ADZUNA_APP_KEY=... $PY -m pipeline fetch
```

Outputs (`download/`): `jobs_<query>_<ts>.csv` + `.json` + `_rejected.csv`
(audit of every filtered row with its reason) + stable `jobs_latest.csv`.
Run logs with per-source error details: `logs/pipeline_run_*.log`.
Exit codes: 0 = at least one source OK, 2 = all failed, 1 = usage error.

Error handling: every source is isolated; failures are captured as typed
errors (`auth` / `waf` / `http` / `parse` / `shape` / `timeout` / `net`) with
URL + response snippet, printed in the summary table and logged — so it is
always obvious which source broke and why.

## Legacy quick start (round-2 scraper)

```bash
python3 scrapers/aggregator_search.py "Fachinformatiker"
```

## Proxy pool (unlocking WAF-blocked boards)

Free-proxy repos are fetched, deduped and two-phase validated against the real
targets; only usable proxies survive into `data/proxies/validated_proxies.json`:

```bash
python -m pipeline.proxy_pool refresh   # re-fetch 8 vetted repos + re-validate (~4 min)
python -m pipeline.proxy_pool stats     # alive count, per-target usability
```

`kimeta` (largest German meta-search, DC-IP-503'd) runs transparently through
this pool as source #6 in RUN_ORDER — no flags needed. Full study + repo
verdicts: `research/infra-repos/findings.md`.

## Job memory + daily digest (Phase 7)

Every fetch now upserts into a persistent SQLite job memory
(`data/jobs_history.db`, via sqlite-utils + FTS5) — one row per unique posting
ever seen, with `first_seen`/`last_seen`/`times_seen`:

```bash
$PY -m pipeline history new      # what's NEW today vs yesterday
$PY -m pipeline history search "systemintegration"   # full-text search
$PY -m pipeline history gone     # likely expired (not re-seen today)
```

Push a daily digest through any of 100+ services with **apprise** — one env var:

```bash
APPRISE_URL="tgram://<bot-token>/<chat-id>" $PY -m pipeline digest
# or ntfy://ntfy.sh/<secret-topic> (zero-signup ntfy app) or mailtos://…
```

`scripts/daily_jobpull.sh` chains everything: proxies → fetch (+ memory) →
site mirror → digest → healthchecks ping (`HC_PING_URL` = dead-man's switch:
silence means the cron broke). Interactive browsing of the memory:
`datasette data/jobs_history.db` → search/facet in the browser.

Dedupe now has three layers: exact title/company/city key → **canonical-URL**
(catches agency re-titling under the same posting URL) → Jaccard near-dupe;
plus rapidfuzz flags same-city look-alikes as `near-dupe-candidate` in notes
(flags only — never auto-merged). Study: `research/legendary-repos/findings.md`.

## Status

- [x] Phase 1: source discovery + live validation (research/2-a…2-f)
- [x] Phase 2: PDF report
- [x] Phase 3: GitHub open-source ecosystem survey (`research/github-repos/findings.md` — 87 repos surveyed, 11 deep-tested; adopt: python-jobspy, ats-scrapers, jutt7/JobHunter)
- [x] Phase 4: aggregator round-2 (kimeta & co — `research/aggregators-round2/findings.md`, 16 entries, live demo CSV) + external backup layer (gofile + surge.sh)
- [x] Phase 5: **unified pipeline CLI** (`pipeline/`) — 55-source catalog, 22 fetchable (RUN_ORDER is fetch-authoritative), hard filters (no Ausbildung / no part-time / no experience / full-time only), dedupe, CSV+JSON+rejected-audit output, typed per-source error handling
- [x] Phase 6: **free-proxy layer** (`pipeline/proxy_pool.py` + `scripts/proxy_tools/`) — 33k candidates tested → 1.2k validated; kimeta unlocked via proxy, stellenanzeigen.de via curl_cffi TLS-impersonation (`research/infra-repos/findings.md`)
- [x] Phase 7: stellenanzeigen.de unlocked (captured JSON API), kimeta 12/57 robots ceiling documented, dedupe upgrade, daily automation — and **round-3 legendary-repo sweep** (`research/legendary-repos/findings.md`): job memory (sqlite-utils), digest push (apprise), dedupe URL-layer + rapidfuzz flagger, healthchecks hook
- [ ] Phase 8 (optional): local LLM layer (ollama + simonw/llm) for ft_unknown classification + German cover-letter drafts; Scrapling hardening per broken parser; changedetection.io for per-employer watching

## Legal note

Research distinguishes GREEN (official APIs/feeds, attribution), YELLOW
(logged-out portal reads at low volume) and RED (blocked portals — use native
email alerts instead). No credential-based automation against portals whose
ToS forbid it. See report ch. 9.
