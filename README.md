# erlangen-jobs 🚆

**Find software/AI jobs within commuting distance of Erlangen, Germany — automatically.**

One script. One output CSV. Every job comes with its **full job description**.
Your **own IP is never used** for any portal traffic — everything runs through an
auto-managed, self-healing proxy pool (fail-fast if no proxy is available; direct
connections are opt-in only).

```
scrape Indeed + LinkedIn + Google  →  merge & dedupe  →  pre-filter
(no Ausbildung / wrong-role / stale postings)  →  rail-corridor geo filter
(S1 Nuremberg–Bamberg corridor, ≤50 km)  →  fetch every job's full description
→  ONE final CSV, sorted by date (+ optional N part files)
```

---

## Quickstart (3 commands)

Works on Linux & macOS, in **any directory** — nothing is hardcoded:

```bash
bash setup.sh                                   # 1. venv + 3 deps + offline self-test
bash run.sh --sweep                             # 2. first run: scrape the portals (~10–20 min)
bash run.sh --fetch-desc --parts 5              # 3. descriptions for every job → final CSV + 5 parts
```

Result: `download/erlangen_jobs_final_<date>.csv` (plus `_part{i}_of_5` files).

> **Offline demo?** A real seed sweep is bundled in `data/raw/`, so step 2 can be
> skipped: `bash run.sh --fetch-desc --parts 5` works immediately (merge → filter →
> CSV from the bundled data; descriptions need internet).

### Already ran it before? (sweeps exist in `data/raw/`)

```bash
bash run.sh                                     # re-filter the newest sweep (fast, ~seconds)
bash run.sh --fetch-desc --parts 5              # full refresh incl. descriptions
```

---

## Parameters (all optional)

| Parameter | Default | Meaning |
|---|---|---|
| `--sweep [N]` | off | **Stage 0**: scrape Indeed/LinkedIn/Google first. `--sweep 3` = smoke (first 3 queries/site) |
| `--fresh-days N` | `30` | max age of `date_posted` (pre-filter) |
| `--max-km X` | `50` | max distance job-town ↔ Erlangen |
| `--station-km X` | `3.0` | max distance job ↔ nearest rail-corridor station |
| `--include-remote` | off | keep remote jobs that fail the corridor test |
| `--input FILE` | – | start from a master JSON (skips sweep/merge) |
| `--no-prefilter` | off | skip text/date pre-filter (geo filter only) |
| `--no-fp-guard` | off | disable senior/management false-positive guard |
| `--fetch-desc` | off | stage 4: visit every job page → full descriptions, CSV sorted by date |
| `--limit-desc N` | all | only first N missing descriptions (smoke) |
| `--desc-phase li\|direct\|indeed\|csv\|all` | `all` | restrict fetch phase (li = fast) |
| `--parts N` | off | also write `…_part{i}_of_N.csv/.json` (record-aware split, integrity-checked) |
| `--out PATH` | auto | custom final CSV path |
| `--workdir PATH` | `data/work` | intermediate files |
| `--no-network` | off | pure offline run (no geocode fetches) |
| `--proxy-refresh` | auto | force proxy harvest+validate now (also auto when pool is low) |
| `--allow-direct` | **off** | ⚠️ opt-out of the IP guarantee: permit your IP as last resort |

Exit codes: `0` success · `1` honest failure (e.g. no proxies available and
`--allow-direct` not set — nothing ever falls back to your IP silently).

## What you get

```
download/
├── erlangen_jobs_final_<date>.csv          ← THE output (one row per job, full description)
│     columns: title, company, location, city, direction, station, station_km,
│              erlangen_km, line, date_posted, age_days, is_remote,
│              source_portal, job_url, job_url_direct[, description]
└── erlangen_jobs_final_<date>_part{i}_of_N.{csv,json}   ← optional split (with --parts N)

data/work/                                   ← intermediates (safe to delete)
├── erlangen_master_*.json                   merged + pre-filtered (audit file: *_prefilter_rejected.json)
├── erlangen_commute_filtered_*.json/.csv/_report.md   geo-filtered + report
├── desc_checkpoint.json                     description fetch progress (resumable — rerun anytime)
└── proxy_pool.json                          proxy pool health state
data/raw/                                    ← immutable portal sweeps (JSON)
```

Rerunning `--fetch-desc` is **resumable**: the checkpoint keeps whatever was
already fetched; only missing descriptions are downloaded.

## Your IP is protected — here is how

1. **Strict proxy pool** (`scripts/net_resilience.py`): proxies come from
   `PROXY_LIST` env var (comma-separated), `data/proxies.txt`, or are
   **auto-harvested** from public proxy lists and validated (concurrency-checked,
   health-scored, retired after 4 consecutive failures, 429/403 bans → cooldown).
2. **Rotation everywhere**: proxy + User-Agent rotate per request; AIMD pacing per
   portal class; honors `Retry-After`.
3. **Fail-fast, never leak**: no healthy proxy ⇒ the run stops with an honest
   error. It will **never** silently touch a job portal with your own IP.
   Only exception: `--allow-direct` (you must type it deliberately).
4. **Circuit state** is persisted (`data/work/proxy_pool.json`), so the pool gets
   smarter across runs. Check it: `python scripts/net_resilience.py status`

Bring your own proxies (recommended for reliability):

```bash
export PROXY_LIST="http://user:pass@host:port,socks5://host:1080"   # or:
echo "http://1.2.3.4:8080" >> data/proxies.txt
```

Tor users: run Tor with `SOCKSPort 9050` and add `socks5h://127.0.0.1:9050`
to `PROXY_LIST` (requires `pip install requests[socks]`).

## Tests

```bash
.venv/bin/python tests/test_net_resilience.py    # 33 offline unit tests (mock HTTP)
.venv/bin/python tests/e2e_test.py               # 19 end-to-end checks (leak audit + full offline chain)
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no portal sweeps found` | run `bash run.sh --sweep` once |
| `no_proxy_strict` / pool empty | `bash run.sh --proxy-refresh --fetch-desc …`, or add own proxies (see above); free proxies are flaky by nature — retry after a few minutes |
| LinkedIn 429s | normal; the pacer auto-cools down and rotates. More proxies = smoother |
| Descriptions incomplete for some rows | rerun `--fetch-desc` (resumable); `job_url_direct` column has the ATS URL if you want to check manually |
| Geocoding skipped (offline) | use `--no-network`; cache fills on next online run |

## Project layout

```
scripts/  erlangen_pipeline.py   ← ONE command (stages 0–5)
          erlangen_all_portals.py, merge_erlangen.py, job_prefilter.py,
          commute_filter.py, fetch_descriptions.py, net_resilience.py,
          de_job_score.py (LLM top-10), de_job_scan.py, split_final_5.py
data/     rail_corridor.json (23 stations / 62 towns wordlist),
          geocode_cache.json (pre-seeded), raw/ (seed sweep), proxies.txt
tests/    test_net_resilience.py, e2e_test.py
download/ your outputs
```

For machine-readable documentation (automation, agents): see **AGENTS.md**.

## Map-ready geo enrichment (stage 6)

```bash
bash run.sh --enrich-geo          # adds 5 columns to the final CSV
# or standalone:
.venv/bin/python scripts/enrich_addresses.py --out download/final.csv
```

New columns: `company_address` (resolved street address or town), `lat`, `lon`
(WGS84, map-ready), `geo_precision` (`street` | `city`), `geo_source`.
Providers: **Google Geocoding** (activates automatically when
`GOOGLE_MAPS_API_KEY` is exported — best quality, $5/1k, 10k free/mo),
then **Photon** + zippopotam through the strict proxy pool, then the bundled
offline gazetteer (62 corridor towns + 457 cached lookups → 100% coverage
offline). Address candidates are extracted from every job description
(Arbeitsort/Standort/street+PLZ patterns). Cached in
`data/work/address_geo_cache.json` — reruns are incremental and fill
street-level precision over time.
