# Project Review — full codebase audit (Task 17, 2026-10-14)

**Reviewer:** outgoing/main agent · **Scope:** every pipeline module, sources, scripts,
docs, data outputs, ops practices. **Method:** read all 2,412 pipeline LOC + daily script
+ README; ran live reproductions (2 confirmed filter false-positives, 1 CLI outage);
cross-checked filters against research/2-e GTFS analysis; quantified impact on the
latest 42-row production output; tested the catalog CLI.

**Verdict:** architecture is genuinely strong for a zero-cost personal toolkit — typed
error handling, graceful dependency degradation, audit-first outputs, honest docs. The
weak spots are **drift between research findings and filters**, **filter
false-positives**, and **environment volatility outpacing the tooling**.

---

## What is already excellent (keep as-is)

1. **Typed per-source errors** (`SourceError` kinds: auth/waf/http/parse/shape/timeout/net)
   with pinpoint URL+snippet — rare quality even in commercial scrapers.
2. **Graceful degradation** — `rapidfuzz` optional in core, `jobspy` lazy with SKIP hint
   (jobspy_src sets HAS_JOBSPY instead of crashing the run).
3. **Audit-first outputs** — every rejected row lands in `*_rejected.csv`; nothing
   silently disappears (one gap: see F5).
4. **ft_unknown philosophy** — ambiguous rows are KEPT + flagged, not dropped. Correct
   for a human-in-the-loop job hunt.
5. **Evidence-carrying catalog** — 55 entries with proven access methods and blocked/dead
   reasons; `sources` command makes it queryable.
6. **Memory as first-class state** — first_seen/last_seen/times_seen + FTS + url-fold
   across re-titled reposts (a real-world problem solved with 100 LOC).
7. **Hard-filter design** — server-side pre-filtering where the API offers it
   (`angebotsart=1`, `pav=false` on BA) before client filters. Saves quota and noise.

---

## P0 — correctness bugs (fix before next production run)

### F1. Geo whitelist `NEAR_RX` contradicts the verified GTFS analysis (both directions)
**Evidence:** `pipeline/__main__.py` lines 21-28 vs `research/2-e/findings.md` §3.1-3.3.
- research line 118 explicitly EXCLUDES **Neumarkt, Feucht, Altdorf, Winkelhaid,
  Postbauer-Heng, Schwabach** (S2/S3 branches, 1 transfer since the 2025-12-14
  "Rücktausch") — `NEAR_RX` accepts all of them.
- research line 114: **Herzogenaurach has no rail at all** — `NEAR_RX` accepts it.
- research line 120: **Zirndorf** 1 transfer — accepted by NEAR_RX.
- research line 116: **Pretzfeld** etc. bus-replaced branch — accepted by NEAR_RX.
- `NEAR_RX` is ALSO MISSING ~20 whitelisted municipalities: Coburg (47 min RE!),
  Lichtenfels/Schney, Haßfurt, Eggolsheim, Buttenheim, Hirschaid, Strullendorf,
  Breitengüßbach, Ebing/Rattelsdorf, Zapfendorf, Ebensfeld, Bad Staffelstein,
  Michelau, Hochstadt a.Main, Redwitz, Küps(borderline), Schwaig(matched via substring
  only), Ottensoos, Henfenfeld, Dörfles-Esbach(borderline), Ebersdorf(borderline).

**Measured impact on production data:** latest 42 rows contain **4 rows in excluded
towns** — Neumarkt in der Oberpfalz ×2, Altdorf bei Nürnberg ×1, Neunkirchen am Brand ×1
(= 10% of output violates the "direct train" requirement). Additionally, these enter via
**BA (geo_scope="query") which bypasses the rail filter entirely** — `geo_keep` returns
True for query-scoped sources, so even a fixed NEAR_RX would not catch them.

**Fix (batch ~90 min):**
1. Generate `data/geo/transit_whitelist.json` from the §3.1 table: per municipality
   `{name, ags, plz_prefixes, minutes, lines, limited:bool}` + the §3.3 exclusions.
2. Build `NEAR_RX` from that file at import time (name regexes generated once — no more
   hand-typing).
3. Apply the whitelist to **ALL** sources as a *classifier*, not just country-scope:
   add column `transit` = `0-xfer (NNmin)` | `1-xfer` | `none` | `limited` — computed
   for every kept row. For radius-scoped sources (BA/EURES/XING) keep rows but the
   column makes them filterable/sortable for Asha; for country-scope sources keep the
   hard filter using the 0-transfer set. Borderline 61-65-min towns flagged `borderline`.
4. Unit-test pins: Neumarkt→1-xfer, Feucht→1-xfer, Coburg→0-xfer(47),
   Herzogenaurach→none, Schwaig→0-xfer, Hersbruck→borderline.

### F2. `PARTTIME_RX` bare-450 match rejects valid jobs (CONFIRMED reproduction)
**Evidence:** ran `classify_job` with desc *"Unser Kunde, ein Traditionsbetrieb mit über
450 Mitarbeitern am Standort, sucht Unterstützung für das IT-Team."* → **rejected
`parttime(desc)`**. Root cause: `\b450[ -]?€?` matches any "450" occurrence (headcount,
address numbers, salaries "45000"). Because `has_tz_desc && !has_vz_desc` → reject.
**Fix:** `\b450[ -]?(?:€|eur\b)|auf\s+450` — require a currency marker or the
established "auf 450" idiom. Add regression test with the Mitarbeiter sentence.

### F3. `EXPERIENCE_BODY_RX` has no negation window (CONFIRMED reproduction)
**Evidence:** desc *"Mindestens 3 Jahre Berufserfahrung im 1st Level Support erwartet wir
nicht – Quereinsteiger willkommen."* → **rejected `experience(desc)`** — exactly the
junior-friendly posting Asha wants. Root cause: pattern matches the phrase, ignoring
"nicht/keine/ohne" in the same clause. `JUNIOR_RX` even contains
"erfahrung nicht erforderlich" but experience rejection fires first.
**Fix:** capture a ±90-char window around each match; reject only if the window lacks
`nicht|keine|ohne|egal|not required|no need|must not|don.t need` (DE+EN). Keep a
`negated-experience` note on flagged rows. Regression-test both directions.

### F4. `AUSBILDUNG_RX` on full description = boilerplate bomb (pattern risk, verified by reading)
`\bausbildung\b` anywhere in 6000 chars rejects e.g. *"Wir engagieren uns in Ausbildung
und Weiterbildung. Wir suchen einen IT-Systemadministrator…"* — big employers (Siemens,
Kliniken) mention Ausbildung in boilerplate constantly; a run like Task 11's
"stellenanzeigen raw=40, kept=0" could silently lose real jobs to boilerplate.
**Fix:** title hits stay hard rejects; description hits reject only on role-shaped
patterns (`ausbildung (als|zum|zur)\b|ausbildungsplatz|azubi`), otherwise add note
`mentions-ausbildung` instead of rejecting.

---

## P1 — reliability & consistency

### F5. Post-merge filter hits vanish from the audit
`__main__.py` lines 139-144: rows that gained a description during merge get
re-classified; failures get note `postmerge-filter-hit` and are silently dropped —
they never reach `*_rejected.csv`. **Fix:** collect them into `all_rejected` with
reason `postmerge:<reason>` before filtering. (15 min; keeps the audit promise.)

### F6. `history.py` top-level import makes the WHOLE CLI die when sqlite_utils is wiped
**Evidence (live outage during this review):** after today's sandbox venv wipe,
`python -m pipeline sources` failed with `ModuleNotFoundError: No module named
'sqlite_utils'` — even though `sources` needs no DB at all. jobspy_src does this right
(lazy guard), history.py doesn't. **Fix:** move `from sqlite_utils import Database`
into `_db()` and degrade gracefully ("memory unavailable — pip install sqlite-utils"),
keeping fetch/sources/digest alive. Same treatment in `__main__`'s import. (20 min.)

### F7. `requirements.txt` does not exist — but README, the delivered email, and the
handover doc all instruct `pip install -r requirements.txt`. **Fix:** create it now
(python-jobspy, pysocks, requests[socks], curl_cffi, apprise, sqlite-utils, rapidfuzz;
loose >= pins). (10 min.)

### F8. Catalog/README drift — single source of truth missing
- `catalog.py` still says `stellenanzeigen` status="recipe" + "needs XHR recipe" note —
  but Task 11 unlocked its JSON API, `pipeline/sources/stellenanzeigen.py` exists, and
  `RUN_ORDER` already includes it (fetch uses `RUN_ORDER ∩ SOURCES`, so catalog status
  is doc-only — yet `python -m pipeline sources` prints wrong info).
- README Phase-5 line says "20 fetchable"; reality today: **21** (17 live + 4 key);
  the handover doc says 22. **Fix:** set stellenanzeigen→live with the real note,
  correct counts, document that RUN_ORDER is the fetch-authoritative list. (20 min.)

### F9. daily_jobpull.sh has no venv guard — today it would have failed mid-run
Given 4 documented venv wipes in 48 h, the daily entry point should self-check:
`$PY -c "import jobspy, sqlite_utils, rapidfuzz, apprise, socks" || $PY -m pip install
-r requirements.txt` before step 1, with a loud log line. Also: step labels are
inconsistent ([1/3]…[3/4]…[4/4]); add `flock` on a lockfile against overlapping runs.
(20 min.)

### F10. Digest reports false "LIKELY EXPIRED" when a source is down
`digest.build_digest` uses `history.gone_today()` — any posting whose source happened
to fail today (e.g. kimeta pool cold) shows as expired. **Fix:** pass today's
OK-source set from the run manifest (F11) into the digest and annotate gone-rows with
`source-down` instead of implying expiry. (30 min.)

### F11. Run logs are ephemeral — add a persistent run manifest
`logs/` was wiped today alongside backups/; nothing links an output CSV to its run's
per-source stats. **Fix:** run_fetch also writes `data/runs/<ts>.json`:
{ts, git_head, slug, per-source SourceResults, output paths, pool size}. Survives
wipes (data/ persisted), powers F10 and "which run produced this file". (20 min.)

### F12. Proxy pool has no staleness signal
`validated_proxies.json` was 13 h old at review time and kimeta silently degrades as
it rots. **Fix:** `proxy_pool.stats()` gains `age_hours`; daily script warns when
>8 h; fetch log line includes per-target pool size. (15 min.)

### F13. `history.update` misses merge metadata + index
- No index on `url_key` (full scan per insert; trivial to add now).
- URL-fold branch (re-titled reposts) doesn't merge company/source/city from the new
  row; `source` stays the old single value — memory loses multi-source provenance.
- Schema lacks salary/is_remote/plz — JSON has them; memory should too (cheap
  `alter` via sqlite-utils). (30 min total.)

---

## P2 — polish & ergonomics (after P0/P1)

| # | Item | Why | Effort |
|---|------|-----|--------|
| F14 | Optional `--parallel 4` for network-bound JSON/RSS sources (keep WAF/proxy sources sequential) | wall-time 3-5× down; 18 sources × (timeout+sleep) dominate | 45 min |
| F15 | Consolidate scripts/test_*.py into tests/ + `python -m unittest discover` incl. F2/F3/F4 regressions | today's fixes prove the need; stdlib-only | 30 min |
| F16 | CSV: add `snippet` column (first ~200 chars of description) | Asha triages in Excel without opening JSON | 15 min |
| F17 | BA enrichment: log `X-API-BLOCKED` response header; single retry on 429 | early warning if the public key ever gets gated | 15 min |
| F18 | Report PDF v1.1 addendum — stellenanzeigen JSON API, kimeta recipe, proxy layer, train-whitelist correction (F1), legendary-repo integrations | the delivered 30-page PDF predates Tasks 9-12; Asha's reference is stale where it matters most | 60 min |
| F19 | `_jac` stopword list has "den" twice; add umlaut-variant stopword | dedupe hygiene, cosmetic | 5 min |
| F20 | `dedupe` near-layer O(n²); at >300 rows swap to rapidfuzz `process.cdist` | future-proofing only — 42 rows are instant today | defer |

---

## Reviewed and deliberately NOT recommended (anti-over-engineering)

- **No Playwright/browser tier** in the default fetch path — policy-green sources don't
  need it; agent-browser stays a manual unlock tool.
- **No Postgres/Redis** — sqlite-utils + file-backed proxy pool are right-sized.
- **No Docker** — the sandbox wipes volumes anyway; the venv guard (F9) is the honest fix.
- **No pandas** for 42-row CSVs — stdlib csv is fine; duckdb already proven for ad-hoc SQL.
- **No captcha-fighting / robots-disallowed crawling** — policy guardrail, unchanged.
- **No paid-API activation attempts** — user checklist remains the path (Adzuna/Jooble).

## Suggested execution order (3 focused batches)

1. **Correctness batch (~2 h):** F2+F3+F4 regex/negation fixes with regression tests →
   F1 whitelist data file + transit column + tests → F5 audit gap. Then run one full
   production pull and diff against today's 42 rows (expect: Neumarkt/Altdorf rows
   re-labeled; previously-lost valid rows recovered).
2. **Resilience batch (~1.5 h):** F7 requirements.txt → F6 lazy sqlite_utils → F9 venv
   guard + flock → F11 run manifest → F12 pool staleness → F8 catalog/README truth-out.
3. **Ergonomics batch (~2 h):** F10 digest correlation → F13 memory enrich → F16
   snippet column → F17 BA header watch → F18 report addendum (or defer).
F14/F15/F20 after observing real runtimes/row counts.
