# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `scripts/seed_from_csv.py` -- seed the winner cache from an external
  pre-validated proxy CSV (`protocol,host,port` [+ per-site boolean columns]);
  with `--map COL=HOST` (repeatable) or a single `--site`. Lets users who
  already benchmark proxies against their target sites reuse that work
  instead of relying on public-list harvests.

## [0.3.1] - 2026-08-30

### Fixed
- **Challenge pages can no longer verify proxies.** Immobilienscout24's AWS-WAF
  interstitial ("Ich bin kein Roboter") parsed as a valid generic item, which
  let 14/19 proxies "pass" against a wall and made a run spin until timeout.
  WAF/captcha interstitials (AWS WAF, DataDome, Cloudflare, PerimeterX,
  generic robot/captcha titles) are now fingerprinted (`challenge_kind`) and
  rejected by every recipe's verifier.
- **Async probe engine now rejects HTTP >= 400** like the threads engine
  (urllib raises HTTPError) -- a 401 challenge body can no longer count as a
  pass on the aiohttp path.

### Added
- `immobilienscout24` recipe (host auto-detected): defensive `__NEXT_DATA__`
  deep-harvest parser for IS24 search pages, de-DE/Europe-Berlin.
- Honest bot-protection reporting: the direct probe sniffs challenge pages
  from HTTP error bodies, stage2 counts them, and both `no_proxies` and
  `no_results` failures now carry a hint naming the vendor and the fix
  (residential proxy) instead of a generic layout message.

## [0.3.0] - 2026-08-30

### Added
- **Universal extraction -- scrape any site, not just AutoScout24:**
  - `--css SEL --field name=SEL::text|::attr(x)` -- CSS selectors with
    Scrapy-style suffixes (BeautifulSoup); relative href/src auto-resolved.
  - `--json-key data.items` -- JSON endpoints/REST APIs; dot-path with list
    indices, or auto-find the largest array of objects.
  - `--table N` -- HTML tables; header row becomes the keys.
  - `auto` is now a structured-first chain: table -> page meta/JSON-LD ->
    embedded JSON. Library mode accepts `Config(parser=my_fn)`.
  - CSV columns adapt automatically to whatever fields extraction produces.
- **Direct-fetch fast path**: unblocked targets are fetched without proxies
  (seconds instead of minutes); the proxy pool engages automatically when a
  site blocks/refuses/hides content, and self-heals back if direct dies
  mid-run. `meta.mode` reports `direct`|`proxy`; `--no-direct` forces
  always-proxy.
- **`--page-template`**: path-style pagination via `{n}` (e.g.
  `.../page-{n}.html`), alongside the default `?page=N` convention.
- Browser proof now also works for direct runs (render without proxy) and
  falls back to generic verification for custom recipes.

### Changed
- beautifulsoup4 is a core dependency (CSS/table extraction).
- Duplicate suppression now also works for items without id/url
  (whole-row comparison).

## [0.2.0] - 2026-08-30

### Added
- **aiohttp async probe engine (now the default)**: high-concurrency
  checking (cap 300) plus a 3s TCP prescan for large harvest batches.
  Measured on the same 600-proxy pool: ~16s vs ~24s (threads x300) and
  ~40s (threads x100) for a full stage-1 round.
- **`proxyfetch config` subcommand** -- persistent user defaults:
  `config set/get/unset/list` for `engine` and `concurrency`.
  Set once, remembered across runs (atomic `~/.proxyfetch/config.json`,
  corrupt files quarantined, values validated).
- `--engine` / `--concurrency` one-run overrides and
  `PROXYFETCH_ENGINE` / `PROXYFETCH_CONCURRENCY` environment variables.
  Resolution: CLI flag > env > saved config > built-in default.
- Transparent fallback to the stdlib thread pool when aiohttp is missing
  or errors mid-run; `meta.engine` in the JSON payload reports what ran.

### Changed
- aiohttp is a core dependency now; probing defaults to the async engine.
- README rewritten in a compact form.

## [0.1.0] - 2026-08-30

### Added
- Autonomous pipeline: harvest free proxies from 6 public GitHub lists,
  two-stage verification (liveness -> target-specific), winner cache with TTL.
- Per-request proxy rotation with 2-strike eviction and live mid-run
  self-healing (automatic re-harvest when the pool dies).
- Watchdog-guarded stealth-browser escalation via optional CloakBrowser
  (`[browser]` extra); hard 110s kill per attempt, spawn-isolated process.
- Pluggable extraction recipes: `generic` (any URL) and `autoscout24`
  (Next.js `__NEXT_DATA__` listings), auto-detected by host.
- Human CLI: colored stage banners, results table, JSON + CSV outputs.
- Agent CLI: `--json` machine payload on stdout, logs on stderr, documented
  exit codes (0/1/2/3/4/130), SIGINT-safe partial results.
- Unit test suite (offline) and GitHub Actions CI.
