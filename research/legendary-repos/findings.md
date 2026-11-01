# Legendary GitHub Repos — Round 3: "Every Aspect" Sweep

**Task 12 · 2026-10-13 · scope: every layer of the toolkit, not just scraping**
Question: *"Any other legendary GitHub repos that could improve every aspect of the project?"*

Method: 18 candidates across 10 aspects → verified via shields.io star badges +
PyPI release health (GitHub API was rate-limited from this DC) → hands-on smoke
tests in `/home/z/.venv` with real project data → adopt / document / reject
verdicts, same strict anti-over-engineering bar as rounds 1–2.

---

## 1. Aspect inventory × gaps found

| Aspect | State before | Gap |
|---|---|---|
| Fetch | 22 fetchable sources, curl_cffi, jobspy | OK |
| Proxy | own pool, 1.2k validated | OK |
| Dedupe | title-key + Jaccard near-dupe | missed URL-identical re-titling; GmbH-token company overlap false positives |
| **Memory** | **none — every run a snapshot** | cannot answer "what's NEW today?"; kimeta first-seen was a per-run note |
| **Notification** | **none** | daily pull writes files nobody sees unless opened |
| **Monitoring** | log files only | cron breaks silently |
| Exploration | CSV/Excel | no interactive browsing/search |
| Analysis | stdlib only | ad-hoc SQL awkward |
| Career (Asha-facing) | out of repo scope | CV tooling |
| Backup | bundle+gofile+surge+codeberg | OK (restic noted as upgrade option) |

## 2. Verification table

Stars via shields.io badge JSON; release via PyPI JSON API (both 2026-10-13).

| Repo | Stars | PyPI ver | Released | Deps | Verdict |
|---|---|---|---|---|---|
| caronc/apprise | 18k | 2.0.1 | 2026-10-03 | 28 | **ADOPT** |
| simonw/sqlite-utils | 2.2k | 4.2.1 | 2026-08-13 | 7 | **ADOPT** |
| rapidfuzz/rapidfuzz | 4.2k | 3.14.6 | 2026-08-30 | 1 | **ADOPT** |
| simonw/datasette | 12k | 0.65.5 | 2026-09-17 | 35 | ADOPT-light (tooling) |
| duckdb/duckdb | 42k | 1.5.6 | 2026-09-28 | 6 | ADOPT-light (tooling) |
| D4Vinci/Scrapling | 87k | 0.4.15 | 2026-08-23 | 5 core | DOCUMENT (per-break adoption) |
| dgtlmoon/changedetection.io | 35k | — (service) | — | — | DOCUMENT |
| healthchecks/healthchecks | 10k | — (SaaS ping) | — | — | **ADOPT** (1-line hook) |
| binwiederhier/ntfy | 35k | 2.7.1 | 2025-03-05 | — | via apprise, see below |
| ollama/ollama | 183k | 0.6.3 | 2026-09-29 | 2 | ROADMAP (Phase 8) |
| simonw/llm | 13k | 0.36 | 2026-09-22 | 15 | ROADMAP (Phase 8) |
| AmruthPillai/Reactive-Resume | 44k | — | — | — | DOCUMENT (Asha-facing) |
| xitanggg/open-resume | 8.9k | — | — | — | DOCUMENT (Asha-facing) |
| restic/restic | 37k | — | — | — | DOCUMENT (backup upgrade option) |
| unclecode/crawl4ai | 85k | 0.9.4 | 2026-09-23 | 54 | REJECT (browser tier deferred) |
| stephanlensky/zendriver | 1.5k | 0.17.1 | 2026-10-02 | 6 | REJECT (browser tier deferred) |
| omkarcloud/botasaurus | 5.8k | 4.0.97 | 2026-01-06 | 14 | REJECT (browser tier deferred) |
| seatgeek/thefuzz | 3.7k | 0.22.1 | 2024-01-19 | 1 | REJECT (superseded by rapidfuzz) |
| pandera | ~5k | 0.34.1 | 2026-10-06 | 67 | REJECT (no pandas in stack) |
| requests-cache | ~3k | 1.3.3 | 2026-07-03 | 20 | REJECT (no recurring pain; probes done) |

Also carried over REJECTED from Phase 6, no new evidence: tenacity, dateparser,
fake-useragent, feedparser.

## 3. Smoke-test evidence (all in `/home/z/.venv`, 2026-10-13)

| Test | Script | Result |
|---|---|---|
| apprise URL validation (ntfy/telegram/smtp) | `scripts/test_apprise.py` | PASS (tgram False = fake-token correctly rejected) |
| apprise **real E2E delivery** (local webhook via `json://`) | `scripts/test_apprise_local.py` | **PASS** — HTTP POST received, title+body intact |
| ntfy.sh from datacenter IP | direct POST | **429 quota** — public ntfy.sh throttles DC IPs; fine from home IPs; Telegram is the robust channel |
| sqlite-utils upsert semantics | `scripts/test_sqlite_utils.py` | **PASS** — first_seen preserved, last_seen/times_seen advanced, new-today detection, FTS5 search, 45 KB/43 rows |
| rapidfuzz vs Jaccard on 43 production rows | `scripts/test_rapidfuzz.py` | **Found a real missed dupe**: BA `12634-BB-64` posted under TWO titles, identical URL; also 1 false positive (Brunel≠FERCHAU via "GmbH" token) |
| datasette serve + FTS + objects shape | live curl | PASS (`/smoke_history/postings.json?_search=...` 200) |
| duckdb `read_csv_auto` on production CSV | inline | PASS — per-source aggregates without conversion |
| Scrapling core (Selector/find_similar/generate_css_selector/auto-heal) | inline | PASS — CSS card extraction, `find_similar`=2 siblings, selector regeneration, regex-recovery after simulated redesign |

## 4. What was integrated (all deployed + production-tested)

### 4.1 Dedupe upgrade (`pipeline/core.py`) — driven by rapidfuzz findings
- **Layer 2: exact canonical-URL merge** (`canon_url`: strips scheme/www/trailing-)
  — catches agency re-titling; the `12634-BB-64` case can no longer survive.
- **Legal-form stopwords** in company tokens (gmbh/ag/kg/ug/niederlassung/…)
  — `Brunel GmbH` no longer overlaps `FERCHAU GmbH`.
- **rapidfuzz flagging, not merging**: same city + token_set_ratio ≥95 →
  `near-dupe-candidate` note on both rows. Deliberately NO company gate here:
  staffing agencies re-post the same end-client job under different names, and
  those are exactly the pairs worth one human glance. 8 flagged rows / 4 pairs
  on production = low noise. Lazy import + graceful fallback if rapidfuzz absent.
- Unit tests (`scripts/test_dedupe_upgrade.py`): **9/9 PASS**, incl. task-11
  BAVARIAHEADHUNTER regression and graceful-degradation case.

### 4.2 Job memory (`pipeline/history.py`, new — sqlite-utils)
`data/jobs_history.db` (60 KB for 43 postings): one row per unique posting ever
seen, pk = dedupe key, `url_key` folds re-titled reposts across runs.
- `python -m pipeline history update|new|gone|search|stats`
- `fetch` updates the memory automatically (non-fatal on failure).
- Resilience proven same-day: when kimeta/pysocks broke mid-test, memory kept
  the postings the broken run couldn't fetch.
- kimeta's first-seen convention is now a real column (memory-wide, not a note).

### 4.3 Daily digest (`pipeline/digest.py`, new — apprise)
`python -m pipeline digest` → NEW TODAY + LIKELY EXPIRED + memory stats.
Push channel = one `APPRISE_URL` env var (`tgram://…`, `ntfy://ntfy.sh/<topic>`,
`mailtos://…`); stdout when unset (cron log). Wired as step [4/4] in
`scripts/daily_jobpull.sh`.

### 4.4 Dead-man's switch (healthchecks pattern)
`HC_PING_URL` env → curl'ed on success only; silence = broken cron. Zero deps.
Setup: free check on healthchecks.io, paste URL. (Same pattern works with any
uptime pinger.)

### 4.5 Data bug fixed along the way
XING source double-prefixed full API URLs
(`https://www.xing.comhttps://www.xing.com/...`) → prefix only when the API
returns a path; production CSV now clean, and the fixed URLs let 2 XING rows
dedupe correctly against their Talent.com copies.

## 5. Operational lessons (this round)

1. **venv disturbance strikes again**: installing the test set removed
   python-jobspy AND pysocks from `/home/z/.venv`. Symptom: kimeta
   `InvalidSchema: Missing dependencies for SOCKS support`. Recovery:
   `python -m pip install python-jobspy pysocks requests[socks]`. Rule:
   after ANY pip activity, run the import-integrity check before the next
   production run (jobspy, socks, curl_cffi, pysocks…).
2. **apprise `tag=` is a plugin filter**, not message tags — passing one with
   no tagged plugins yields NOMATCH.
3. **ntfy.sh rate-limits datacenter IPs** (daily visitor quota); from home IPs
   it's zero-signup push; Telegram bot is the channel of record otherwise.
4. datasette 0.65 removed `--silent`; URLs need the db-name segment
   (`/<db>/<table>.json`).

## 6. Deferred / roadmap (evidence kept for later)

- **Scrapling** (87k★): strongest future hardening for HTML parsers —
  `find_similar` + auto-generated selectors + regex recovery survive site
  redesigns. Adopt per-source ONLY when a parser breaks (preemptive adoption
  = over-engineering today). Its stealth fetchers are extras; we already have
  curl_cffi.
- **Browser tier** (crawl4ai 85k★ / botasaurus / zendriver / patchright /
  FlareSolverr): all deferred behind one policy — only if curl_cffi + proxy +
  captured-API paths are exhausted. crawl4ai pulls 54 deps + Playwright.
- **Phase 8 — local LLM layer** (ollama 183k★ + simonw/llm): classify the
  `ft_unknown` rows semantically, German cover-letter drafts from the job
  description. Zero API cost, needs multi-GB model downloads on Asha's machine.
- **changedetection.io** (35k★): per-employer career-page diffing with alerting;
  heavyweight standalone web service — recommend running on the user's own
  machine if per-company watching beyond our 22 sources is wanted.
- **Reactive-Resume (44k★) / OpenResume (8.9k★)**: Asha-facing CV tools,
  outside the pipeline's scope; noted in the report chapter for application
  materials.
- **restic (37k★)**: encrypted incremental backups with prune — upgrade path if
  the bundle+gofile+surge+codeberg scheme ever gets unwieldy.

## 7. Net effect

Adopted 5 (apprise, sqlite-utils, rapidfuzz, healthchecks-hook, + datasette/
duckdb as tooling), integrated 4 new capabilities (dedupe layer-2, job memory,
digest push, dead-man's switch), fixed 1 production data bug, added 9 unit
tests — pipeline output improved from 43 → 42 unique rows with *zero* new
false merges, and the daily chain now answers "what's new for Asha today?"
without opening a spreadsheet.
