# Free-Proxy Repos & Utility Repos — Search, Test, Adopt (Task 10)

Date: 2026-10-13 · Tester environment: datacenter IP (WAF-blocked by most German commercial
boards — the exact bottleneck this task attacks) · Verdicts are empirical, not theoretical.

## 1. Why proxies

Round-2/7 probes established: kimeta = nginx-503 on DC IPs, stellenanzeigen/jobvector/jobrapido =
Cloudflare/WAF, monster/meinestadt/jobscout24 = 403. The 55-source catalog had 16 live sources;
everything Kimeta-class needed a "residential IP". Free proxy lists are the only zero-cost route.
User directive: search free-proxy repos, TEST, adopt only usable ones.

## 2. Proxy list repos — probed, fetched, measured

| Repo | ★ | Updated | Candidates fetched | Verdict |
|---|---|---|---|---|
| monosans/proxy-list | 1.5k | hourly | 999 + JSON metadata (latency, exit_ip, ASN, country) | **ADOPT — primary** (highest quality/hour, richest metadata; proxies.json at main/proxies.json) |
| proxifly/free-proxy-list | 6.9k | 5 min | 6.6k + 12k socks5 sample | **ADOPT — volume** (biggest live pool; unvalidated upstream) |
| TheSpeedX/PROXY-List | 5.9k | daily | 7.9k | **ADOPT — volume** |
| zloi-user/hideip.me | — | active | 2.5k with country suffix | **ADOPT — metadata** (free country tags) |
| roosterkid/openproxylist | 0.9k | hourly | 283 | ADOPT (small but fresh) |
| Zaeem20/FREE_PROXIES_LIST | 0.4k | 10 min | 169 | ADOPT (marginal) |
| clarketm/proxy-list | 2.4k | 2026-03 | 400 | ADOPT (stale but nonzero yield) |
| MuRongPIG/Proxy-Master | 0.4k | 2025-08 | 290k dump, sampled 2.5k/proto | MARGINAL — same IP listed under all 3 protocols, unvalidated firehose |
| mmpx12/proxy-list | 0.4k | hourly | returns "error code: 502/1015" text | REJECT (upstream CF-rate-limited) |
| hookzof/socks5_list | — | — | 404 | REJECT (dead path) |
| gfpcom/free-proxy-list | 0.4k | — | 404 (master+main) | REJECT |
| jetkai/proxy-list | 0.7k | 2023 | empty JSON | REJECT (stale) |
| ShiftyTR/Proxy-List | 0.6k | 2023 | 40 lines | REJECT (stale) |

## 3. Empirical test results (scripts/proxy_tools/fetch_and_test.py)

- Pool: 33,015 unique (proto, host, port) after dedupe across 8 live repos.
- Phase 1 (generic HTTPS via gstatic-204, 700 threads, 4s): **1,255 alive (3.8%)** — typical for
  free lists. Error taxonomy: ConnectTimeout 16.7k, ProxyError 7.6k, ConnectionError 6.2k,
  SSLError 716, ReadTimeout 539.
- Phase 2 (survivors vs REAL targets):
  - **BA API: 610 usable (48.6%)** — BA already works direct; proxies = free rotation to stay
    under rate limits.
  - **Kimeta: 248 usable (19.8%)** — board that 503'd us directly. UNLOCKED.
  - **stellenanzeigen.de: 361 usable (28.8%)** — CF board. UNLOCKED (200 + 539KB HTML).
  - jobvector: 3 usable (0.2%) — CF cookie challenge resists even via proxies. Still recipe.
- Artifacts: `data/proxies/validated_proxies.{json,csv}` (latency, country, ASN, per-target flags),
  `fetch_stats.json`, `kimeta_sample.html`.

## 4. Bypass libraries — tested head-to-head

| Repo | ★ | Result | Verdict |
|---|---|---|---|
| curl-cffi (lib, not repo) | — | **stellenanzeigen.de 200 in 77ms DIRECT, no proxy** (TLS fingerprint = the actual WAF trigger); kimeta still 503 (IP-level), jobvector 403, jobrapido 403 | **ADOPT** — cheapest unlock for TLS-fingerprint WAFs; installed in venv |
| VeNoMouS/cloudscraper | 6.8k | kimeta 503, jobvector 403 | REJECT (defeated by modern CF) |
| FlareSolverr | 15.9k | not deployed (needs Docker) | DEFER — last resort for cookie challenges (jobvector-class) |
| feder-cr/invisible_playwright | 3.1k | browser-based, heavy | DEFER (same trigger condition as FlareSolverr) |
| sarperavci/CloudflareBypassForScraping | 2.6k | browser-based | DEFER |
| sardanioss/httpcloak | 1.3k | Go client | REJECT (stack is Python) |

## 5. Proxy pool tooling — evaluated, not adopted

| Repo | ★ | Why rejected |
|---|---|---|
| jhao104/proxy_pool | 23.8k | Redis + Flask service + scheduler — over-engineered vs our 120-line file-backed `pipeline/proxy_pool.py` (user rule: no over-engineering) |
| Python3WebSpider/ProxyPool | 6.3k | same service shape (getter/tester/server) |
| SpiderClub/haipproxy | 5.5k | distributed crawler framework, stale 2022 |
| MikeChongCan/scylla | 4.0k | web-UI pool, stale-ish |
| Resinat/Resin | 2.4k | Rust gateway, wrong stack |
| monosans/proxy-scraper-checker | 1.3k | the tool that BUILDS monosans list; Rust build; we consume its output directly instead |

**Adopted instead:** own `pipeline/proxy_pool.py` (pick/mark_dead/stats/refresh, ~120 lines,
file-backed, zero deps beyond requests+pysocks) + `scripts/proxy_tools/fetch_and_test.py`
(reusable refresher: `python -m pipeline.proxy_pool refresh`).

## 6. Utility repos screened for the pipeline

| Candidate | Purpose | Verdict |
|---|---|---|
| PySocks | SOCKS4/5 for requests | **ADOPT** (required for 52% of alive proxies) |
| curl_cffi | TLS impersonation | **ADOPT** (proven above) |
| tenacity | retries | SKIP — sources already isolate+type errors; a retry loop is 5 lines where needed (kimeta proxy rotation implements it) |
| rapidfuzz | fuzzy near-dupe | SKIP now, BACKLOG — would merge the 3 BAVARIAHEADHUNTER ID-variant rows (title differs only by "ID 7285"/"ID SW72"); strip `ID \w+` pre-token would fix it cheaper |
| dateparser | German relative dates | SKIP — `date_from_text` covers heute/gestern/vor N Tagen |
| fake-useragent | UA rotation | SKIP — static Chrome UA passes everywhere we're unlocked |
| feedparser | RSS | SKIP — rss_apis already parses via xml stdlib |
| cloudscraper | CF bypass | REJECT (see above) |

## 7. What proxies actually changed for the toolkit

1. **New live source: kimeta** (Germany's largest meta-search, 57 FISI/Erlangen at probe) —
   `pipeline/sources/kimeta.py` through the pool; production run: raw=12, kept=5, ~10s.
   Catalog: recipe -> **live** (21st fetchable source).
2. BA API gets a 610-proxy rotation buffer for free.
3. kimeta pagination + stellenanzeigen XHR discovery = remaining backlog (page 1 only ≈ 12 of
   57 kimeta hits; stellenanzeigen reachable via curl_cffi but SERP is CSR).
4. Honest-data convention: kimeta cards carry no dates -> date_posted = first-seen (today),
   flagged in `notes` — keeps "sorted by date" truthful with an explicit audit trail.

## 8. Operational rules (learned the hard way, kept short)

- Free proxies rot in hours: run `python -m pipeline.proxy_pool refresh` before sessions that
  need kimeta; expect ~1k alive from ~33k candidates; kimeta-ok subset ≈ 20-25%.
- Never send credentials through free proxies (we never do — public SERPs only).
- Success ≠ anonymity: some "transparent" proxies leak the DC IP; fine for SERP reads, assume
  no privacy from the exit host.
- kimeta 503 for DC IPs is stable infrastructure, not transient — don't retry direct, go pool.

---

## Task 11 addendum (Phase 7)

### stellenanzeigen.de — full API unlock (the round-2 "recipe" tier is dead)
- Browser-captured recipe: `GET /api/jobs/?...&fulltext={kw}&locationIds={M-DE-xxxx}&perimeterRadius={km}&sort=Datum&skip={n*50}&limit=50`
- GOTCHA: `limit=0` returns ZERO ads (not unlimited); `region`/`keywords` params are legacy no-ops
- `locationIds` from `GET /api/suggest/?value={city}` (flaky 400 from scripts — fallback dict in source); M-DE-2076=Erlangen, M-DE-2214=Nürnberg
- Records: originalStartDate (real date), salaryMin/Max/Unit, geo+zip+state in regions[], isRelevant flag, distance (3500 = national/no-geo sentinel)
- robots: /api/jobs + /api/suggest ALLOWED (only /api/tracking/* disallowed) — green zone
- Needs curl_cffi TLS impersonation; plain requests 403. Validated in-pipeline (raw=40 today, 0 kept — all correctly date/relevance-rejected)

### kimeta ceiling (documented, not a failure)
- ?page=2, /seite-2, RSC headers all return identical 12 cards; buildManifest minified; no public search API; robots DISALLOWS /search, /api, /display-job
- 12 fresh cards per keyword+city is the green-zone yield; deeper extraction would require the disallowed zone — skipped by policy

### Free-API key checklist (user actions, ~2 min each, all free)
1. Adzuna: developer.adzuna.com/signup (reCAPTCHA — must be human) -> create app -> set ADZUNA_APP_ID + ADZUNA_APP_KEY in .env
2. Jooble: jooble.org/api (captcha) -> request key -> JOOBLE_API_KEY
3. Careerjet: careerjet.com/partners/api -> affiliate id -> CAREERJET_AFFID (works only from residential IP)
4. WhatJobs: whatjobs.com affiliate -> WHATJOBS_PUBLISHER_KEY
Pipeline auto-detects env keys on next run (errors already carry exact hints).

### Daily automation
- `bash scripts/daily_jobpull.sh [--with-proxies]` = refresh pool -> full pull (filters ON) -> mirror site/downloads
- Sandbox has no cron daemon; on a persistent host: `17 7 * * * cd /home/z/my-project && bash scripts/daily_jobpull.sh --with-proxies >> logs/cron.log 2>&1`
