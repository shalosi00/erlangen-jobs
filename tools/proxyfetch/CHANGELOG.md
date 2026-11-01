# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-11-02

### Added
- **Self-healing Lightpanda render engine** (`proxyfetch/lightpanda.py`, pure
  stdlib). The browser tier now defaults to Lightpanda — a ~35 MB headless
  browser speaking CDP — instead of requiring the CloakBrowser extra:
  - servers start on demand, one per (proxy, locale, timezone), and route
    their HTTP through the pool proxy (`lightpanda serve --http-proxy`), so
    proxied renders stay proxied — verified live against a free-proxy pool;
  - self-healing on every call: healthy reuse, dead/hung restart with reaping,
    dynamic ports 9222-9230, honest fallback to CloakBrowser/plain HTTP;
  - raw-WebSocket CDP client (RFC 6455): navigate, wait for load,
    cookie-consent auto-accept (OneTrust, Cookiebot, UserCentrics, CIVIC,
    CookieScript, CookieYes), JS-dialog auto-dismiss, timeout-bounded HTML;
  - servers are cleaned up at process exit (never leaked), warm for the
    process lifetime.
- CLI: `--browser-engine {auto,lightpanda,cloakbrowser}`, `--lightpanda-bin`;
  env `PROXYFETCH_BROWSER_ENGINE`, `LIGHTPANDA_BIN`, `LIGHTPANDA_CDP`
  (external CDP server URL or `off`).
- `meta.browser_proof.engine` in the machine payload names the engine used.
- `scripts/seed_from_csv.py` (previously listed under Unreleased; shipped in
  the 0.3.2 tree) — seed the winner cache from a validated proxy CSV.

### Fixed
- Browser escalation in `_collect` was gated on CloakBrowser being installed;
  a Lightpanda-only install (the new default) never got escalation.
- File modes normalized to 644/755 across the tree (a clone quirk had left
  everything executable).

### Tests
- New `tests/test_lightpanda.py`: offline mock CDP server (fragmented
  WebSocket messages, dialog auto-dismissal, external-endpoint mode) + live
  smoke (skipif no binary). Suite: 113 passed + 1 skipped in CI mode;
  114 passed with the binary present. Live end-to-end: direct fast path +
  CSS extraction + Lightpanda proof render (books.toscrape, 20 items,
  `browser_proof.engine: lightpanda`).

## [0.3.2] - 2026-11-01

### Fixed
- **`--recipe` choices were out of sync with the registry**: the CLI accepted
  only `auto|generic|autoscout24` although the `immobilienscout24` recipe
  exists and is host-auto-detected. The choices are now derived from
  `recipes.RECIPES`, so they can never drift again (README CLI table updated).
- `pyproject.toml` project URLs pointed at the placeholder
  `github.com/OWNER/proxyfetch` -- now `github.com/shalosi00/proxyfetch`.

### Audit (2026-11-01 full repo test)
- 102/102 unit tests pass; live end-to-end verified: direct fast path +
  pagination + CSS extraction (books.toscrape, 40 items), JSON-endpoint mode,
  HTML-table mode, usage exit code 2, honest `no_results` payload + exit 1 on
  blocked targets, and the full blocked-target chain (kimeta.de HTTP 503 ->
  auto pool engagement -> harvest ~13k candidates from 6 public lists ->
  verify -> fetch through working proxy, `mode: proxy` reported).

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
