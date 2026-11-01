# AI HANDOVER — Proxied Web Fetching Stack ("proxy browser")

> Written 2026-10-29 (Task 24c) for ANY successor AI agent working in
> `/home/z/my-project`. Every command below was verified working on the day
> of writing. Follow it exactly; the gotchas at the end are all scars from
> real failures.

---

## UPDATE 2026-11-02 — proxyfetch v0.4.0: Lightpanda render engine

proxyfetch is now at **v0.4.0** (private repo, main `bc1cc2a`, tag `v0.4.0`).
The browser tier defaults to a **self-healing Lightpanda CDP engine**
(`proxyfetch/lightpanda.py`, pure stdlib, external ~35 MB binary):

- servers start on demand, one per (proxy, locale, timezone), and route
  through `lightpanda serve --http-proxy` — **proxied renders stay proxied**
  (strict no-direct invariant untouched; verified live through a pool proxy);
- self-healing on every call: healthy reuse / dead restart / hung reaping /
  dynamic ports 9222–9230; binary absent → honest fallback (cloakbrowser /
  plain HTTP); servers are cleaned up at process exit;
- cookie-consent walls auto-accepted, JS dialogs auto-dismissed, all
  timeouts bounded;
- new flags `--browser-engine {auto,lightpanda,cloakbrowser}` and
  `--lightpanda-bin`; env `LIGHTPANDA_BIN`, `LIGHTPANDA_CDP` (external CDP
  server URL, or `off`), `PROXYFETCH_BROWSER_ENGINE`;
  `meta.browser_proof.engine` names the renderer in `--json` payloads.

§2's rebuild recipe is unchanged but now installs 0.4.0 from the tarball.
The binary lives at `tools/lightpanda` in the main project sandbox
(set `LIGHTPANDA_BIN=/home/z/my-project/tools/lightpanda` if not on $PATH).
Full story: worklog.md 2026-11-02; tests 114/114 with binary.

---

## 0. What this stack is (30-second orientation)

Two cooperating tools fetch web data through rotating free proxies:

1. **proxyfetch** — self-healing scraper CLI (Python, `~/.venv`).
   Harvest → verify → rotate → self-heal → stealth-browser fallback.
   Repo: `github.com/shalosi00/proxyfetch` (**private**, needs the PAT).
2. **pipeline proxy pool** — the job-pipeline's own validated pool
   (`data/proxies/validated_proxies.csv`), maintained by
   `python3 -m pipeline.proxy_pool`. Feeds proxyfetch via seeding.

Rule of thumb: **proxyfetch for everything; kimeta is the one exception**
(see §5 — TLS fingerprinting).

---

## 1. Credentials (user-authorized to include, 2026-10-29: "its all ok")

**GitHub PAT — account `shalosi00`:**

```
ghp_<REDACTED-for-public-repo — full key: state/github_token (0600) and state/AI_HANDOVER_PROXY_BROWSER_full.md; if wiped, ask the user>
```

- Store it at `state/github_token` (chmod 600) — **already gitignored**;
  NEVER commit it, NEVER put it in a bundle/mirror. It can push to public repos.
- Restore command after a wipe:

```bash
printf 'ghp_<REDACTED-for-public-repo — full key: state/github_token (0600) and state/AI_HANDOVER_PROXY_BROWSER_full.md; if wiped, ask the user>' > state/github_token
chmod 600 state/github_token
git check-ignore state/github_token   # must output the path = safe
```

- Validate: `curl -sS -H "Authorization: token $(cat state/github_token)" https://api.github.com/repos/shalosi00/proxyfetch -o /dev/null -w "%{http_code}\n"` → expect `200`.
- If GitHub answers 401: the key was rotated — ask the user for a fresh one.

**Email (atomicmail):** never send before running `python3 scripts/atomicmail_recover.py`
(re-register only on 401/403). Channel: `asha.jobtoolkit3@atomicmail.ai`
→ recipients `skorry@atomicmail.io` + `feebee231@outlook.com`.
Send recipe: see `scripts/atomicmail_send_daily.py` (ops JSON + `npx atomicmail jmap_request`).

---

## 2. Verified install state (2026-10-29) + full rebuild recipe

Current working state:

| Piece | Path / check |
|---|---|
| proxyfetch module | `/home/z/.venv` → `python3 -c "import proxyfetch"` (v0.3.1) |
| proxyfetch state | `~/.proxyfetch/winners.json` (schema `proxyfetch.winners/v1`) |
| source snapshot | `tools/proxyfetch-src/` (untarred from private repo) |
| proxy pool | `data/proxies/validated_proxies.csv` (152 alive on 2026-10-29) |
| seeder | `scripts/seed_proxyfetch.py` |

Rebuild from scratch (after sandbox wipe):

```bash
cd /home/z/my-project
# 1. restore PAT (§1)
# 2. reinstall proxyfetch from the private repo
rm -rf tools/proxyfetch-src && mkdir -p tools/proxyfetch-src
curl -sSL -H "Authorization: token $(cat state/github_token)" \
  "https://api.github.com/repos/shalosi00/proxyfetch/tarball/main" \
  | tar xz -C tools/proxyfetch-src --strip-components=1
/home/z/.venv/bin/python3 -m pip install -q ./tools/proxyfetch-src
# 3. seed proxyfetch's cache from the pipeline's validated pool
/home/z/.venv/bin/python3 scripts/seed_proxyfetch.py
# 4. smoke test (expect "20 item(s)" within seconds)
/home/z/.venv/bin/python3 -m proxyfetch \
  "https://books.toscrape.com/catalogue/page-1.html" \
  --css "article.product_pod" --field title="h3 a::attr(title)" \
  --pages 1 --no-save
```

If the venv itself is missing: `python3 -m venv /home/z/.venv && /home/z/.venv/bin/python3 -m pip install -r requirements.txt` (scripts/daily_jobpull.sh does this automatically).

---

## 3. How to fetch (copy-paste recipes)

CLI form: `python3 -m proxyfetch "<url-or-query>" [flags]` (also `proxyfetch` on PATH).

```bash
PYF=/home/z/.venv/bin/python3 -m proxyfetch

# A. arbitrary page, agents output (one JSON payload, nothing saved)
$PYF "https://example.com/whatever" --json --no-save

# B. CSS extraction (Scrapy-style ::text / ::attr suffixes) + pagination
$PYF "https://books.toscrape.com/catalogue/page-1.html" \
  --css "article.product_pod" \
  --field title="h3 a::attr(title)" --field price=".price_color::text" \
  --field url="h3 a::attr(href)" \
  --pages 5 --page-template "https://books.toscrape.com/catalogue/page-{n}.html"

# C. JSON/REST endpoints (dot-path or auto-find items array)
$PYF "https://api.example.com/v1/items" --json-key data.items

# D. HTML tables (header row becomes keys)
$PYF "https://en.wikipedia.org/wiki/List_of_X" --table 1

# E. force the proxy path (skip the direct fast-path)
$PYF "<url>" --no-direct --fresh --budget 600
```

Key flags: `--fresh` (re-harvest proxies), `--no-direct` (proxy-only),
`--engine {aiohttp,threads}`, `--concurrency N`, `--timeout S`, `--budget S`,
`--state-dir DIR`, `--headed/--no-browser` (stealth-browser fallback),
`--recipe {auto,generic,autoscout24}`, `--no-save`.

First attempt is ALWAYS a fast direct fetch; only on failure does it go
through proxies. Add `--no-direct` when a site blocks the sandbox IP.

---

## 4. Pipeline proxy pool (feedstock + standalone use)

```bash
cd /home/z/my-project
/home/z/.venv/bin/python3 -m pipeline.proxy_pool stats    # alive counts per site
/home/z/.venv/bin/python3 -m pipeline.proxy_pool refresh  # re-harvest+validate (~4 min)
```

- Output CSV: `data/proxies/validated_proxies.csv`
  columns `protocol,host,port,latency_ms,country,asn,exit_ip,ba_api_ok,kimeta_ok,stellenanzeigen_ok,jobvector_ok,sources,checked_at`.
- Bridge it into proxyfetch anytime: `/home/z/.venv/bin/python3 scripts/seed_proxyfetch.py`
  (http-protocol rows only; maps `kimeta_ok`→`www.kimeta.de` etc.).
- In-code use (Python): `from pipeline.proxy_pool import pick, mark_dead`
  → `pick("kimeta") / pick("any")` returns `{"host","port","proxies",...}`,
  call `mark_dead(entry)` on failure.

---

## 5. THE KIMETA EXCEPTION — read before touching kimeta.de

kimeta **TLS-fingerprints clients**: proxyfetch's aiohttp engine gets 503
through proxies where Python-`requests` passes fine. Therefore:

- NEVER fetch kimeta through proxyfetch.
- Use the pipeline source instead:
  `python3 -c "from pipeline.proxy_pool import pick; import requests,sys; sys.path.insert(0,'/home/z/my-project'); ..."`
  or reuse the proven helper `fetch_kimeta(row)` in `scripts/enrich_jobs.py`
  (rotates `pick("kimeta")`, 4 attempts, marks dead proxies).
- Kimeta SERP URL shape: `https://www.kimeta.de/fachinformatiker-systemintegration-jobs-erlangen`
  (NOT `/suche/...` — that 404s).
- Kimeta cards carry NO posting dates → project convention:
  `date_posted = first_seen`, documented in `pipeline/sources/kimeta.py`.
- Run kimeta fetches SEQUENTIALLY (the pool rotation is rate-picky).

---

## 6. Hard-won gotchas (all caused real failures once)

1. **Sandbox kills background processes** between tool calls (nohup/setsid
   included). Run long jobs in the FOREGROUND with generous timeouts and
   checkpoint-resume: `scripts/enrich_jobs.py --resume data/enriched/partial_enrich.json`.
2. **aiohttp engine = HTTP proxies only** (no SOCKS) — seeders must filter.
3. **PEP 668**: system pip refuses installs → always use `/home/z/.venv/bin/python3 -m pip install`.
4. **BA (arbeitsagentur) API**: needs header `X-API-Key: jobboerse-jobsuche`;
   detail endpoint `https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{urlsafe_b64(refnr)}`.
   The JSON gives posting date + employer contact directly — use it.
5. **filebin.net has banned this sandbox IP** (400/403) after v9–v11 uploads.
   Bundle mirrors now go to **gofile**: `curl -F "file=@bundle" https://store-eu-par-8.gofile.io/contents/uploadfile`
   → verify via server-side MD5 (direct downloads are web-challenge-gated).
6. **Never background long scripts**; never commit `state/github_token`;
   never trust `git bundle create --all <file>` — argument order is
   `git bundle create <file> --all`.
7. **Free proxies die fast**: re-seed (`scripts/seed_proxyfetch.py`) or
   `proxyfetch --fresh` when kill-rates spike; refresh the pool if
   `stats()` shows < ~60 alive or older than ~3 days.

---

## 7. Standing rituals (carry these over — user requires them)

- **Backup after EVERY task**: git commit →
  `git bundle create backups/asha-jobtoolkit-vNN.bundle --all` → SHA256 →
  `git bundle verify` → gofile mirror (MD5/size check) → `BACKUPS.md` entry.
  Latest bundle: **see `BACKUPS.md` — its newest entry is always current**
  (do not hardcode bundle numbers in this doc).
- **Email work**: `python3 scripts/atomicmail_recover.py` FIRST, always.
- **Daily job task** is scheduled (platform cron job #485352, 07:00
  Atlantic/Reykjavik): `bash scripts/run_daily_task.sh` =
  recover → jobpull → enrich (`scripts/enrich_jobs.py`: WHERE/WHEN/employer/
  contacts) → summary (`scripts/daily_summary.py`) → email both recipients.
- Keep `worklog.md` updated per task.

## 8. Key repos

- `github.com/shalosi00/proxyfetch` (PRIVATE — PAT required; seed feature
  upstreamed in commit `2e79836`)
- `github.com/shalosi00/erlangen-jobs` (PUBLIC — the job pipeline: sources,
  geo rail-corridor filter, Leaflet map; strict proxy-only networking)

Further background in `CHANNEL.md`, `worklog.md`, `BACKUPS.md`.
