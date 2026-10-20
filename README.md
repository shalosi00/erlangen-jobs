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
bash run.sh --enrich-geo          # full automatic chain, every pass budget-capped & resumable
bash run.sh --enrich-geo --geo-budget 600   # more time per pass
```

New columns: `company_address` (resolved street address or town), `lat`, `lon`
(WGS84, map-ready), `geo_precision` (`street` | `poi` | `city`), `geo_source`.

Stage 6 tries, in order, until every record has a place:

| pass | source | key needed | notes |
|------|--------|------------|-------|
| 6a | row-level: address in description, zippopotam, gazetteer | — | 100% coverage floor |
| 6b | Photon by **company name** (location-biased) | — | proxy pool |
| 6c | geocode.maps.co by company name | `GEOCODE_MAPS_API_KEY` | Nominatim-grade, ~4.5 req/s |
| 6d | **Google Maps via headless browser** | — | `agent-browser` CLI; resumable; no API key |
| 6e | street lines mined from job descriptions | — | house-number + ≤12 km gates |

Every later pass only touches employers still at town-centroid precision;
results are sanity-gated (distance to the town, name match, no highways) so a
wrong pin never replaces an honest one. Caches live in `data/work/` — reruns
are incremental. Current snapshot: **1,257 / 1,413 rows (89%) at a real
address**, the rest carry an honest "≈ town centre" badge on the map.

## Interactive map (stage 7)

![map overview](map/screenshot.png)

```bash
bash run.sh --build-map           # or: .venv/bin/python scripts/build_map.py
# -> map/index.html  (self-contained: double-click to open, no server needed)
# -> map/jobs.geojson (1 feature per job, for GIS reuse)
```

Self-contained **Leaflet** map of every job in the final CSV: 1,413 jobs
collapse into employer pins (one pin per company+location, popup lists ALL of
that employer's postings with direct clickable links), marker color = source
portal, no clustering — every company is its own dot (stacked pins fan out in
a sunflower spiral), live search (title/employer), per-portal filters, top-25
employer fly-to, dark Esri basemap. The geocoded dataset is embedded inline —
the HTML renders offline from `file://`; only Leaflet/JS libs and map tiles
come from CDNs. Includes a real-browser screenshot; a GitHub Actions workflow
(`.github/workflows/ci.yml`) rebuilds and smoke-tests the map on every push.

| column | example | meaning |
|---|---|---|
| `company_address` | `Nürnberg (Korridor-Gemeinde)` | resolved address / town |
| `lat`, `lon` | `49.589157, 10.981207` | WGS84 workplace coords |
| `geo_precision` | `city` | `street` (25 rows) or `city` centroid |
| `geo_source` | `gazetteer` | `google\|photon\|zippopotam\|gazetteer\|cache` |

### Hosting the map

`map/index.html` is fully self-contained — open it directly from `file://`
(double-click), no server needed. GitHub Pages is not available for private
repos on the free plan (verified via API); if you make the repo public:
Settings → Pages → *Deploy from a branch* → `main` / `/(root)` → map served
at `https://shalosi00.github.io/erlangen-jobs/map/`.

