# proxyfetch

**Fetch and scrape any URL through an auto-managed free-proxy pool — direct first, proxies when blocked, harvest → verify → rotate → self-heal → stealth-browser fallback. One command, zero intervention.**

```
SUPPLY   direct-fetch fast path (unblocked targets finish in seconds) →
         winner cache (TTL 3h) → harvest 6 public lists → stage1 → stage2
         [aiohttp x300 | threads fallback]
COLLECT  per-request rotation · 2-strike benching · mid-run self-heal ·
         stealth-browser escalation
PROOF    best-effort CloakBrowser render (110s hard watchdog)
OUTPUT   JSON + CSV artifacts · console table · machine payload (--json)
EXTRACT  recipes: autoscout24 · generic · css selectors · JSON endpoints ·
         HTML tables · auto chain (table → meta → JSON) · custom parser
```

## Install

```bash
pip install .            # core (aiohttp engine + threads fallback)
pip install ".[browser]" # + stealth-browser escalation (CloakBrowser)
pip install -e ".[dev]"  # development
```

## Use

```bash
proxyfetch "https://www.autoscout24.de/lst/dacia/jogger" --pages 3   # humans: table on stdout
proxyfetch "https://example.com/whatever" --json --no-save           # agents: one JSON payload
proxyfetch <url> --fresh --budget 600 --headed                       # cold restart, visible browser
```

## Scrape anything (universal extraction)

```bash
# CSS selectors (Scrapy-style ::text / ::attr suffixes), path pagination
proxyfetch "https://books.toscrape.com/catalogue/page-1.html" \
  --css "article.product_pod" \
  --field title="h3 a::attr(title)" --field price=".price_color::text" \
  --field url="h3 a::attr(href)" \
  --pages 5 --page-template "https://books.toscrape.com/catalogue/page-{n}.html"

# JSON endpoints (REST APIs) -- dot-path or auto-find the items array
proxyfetch "https://api.example.com/v1/items" --json-key data.items

# HTML tables -- header row becomes the keys
proxyfetch "https://en.wikipedia.org/wiki/List_of_X" --table 1

# no flags at all: auto chain (table -> page meta -> embedded JSON)
proxyfetch "https://any-site.example/list"
```

Unblocked targets are fetched **directly** (fast path, seconds). If the site
blocks, refuses or hides content, the proxy pool engages automatically —
and re-engages if direct dies mid-run. `--no-direct` forces always-proxy.
CSV columns adapt to whatever fields your extraction produces.

Library mode accepts a custom parser: `Config(url=..., parser=my_fn)` where
`my_fn(html, url) -> list[dict]`.

## Seed the pool from an external proxy file

Already maintain a validated proxy pool elsewhere (own harvester, daily
pipeline, corporate exit nodes)? Skip public-list harvesting entirely:

```bash
# one site
python3 scripts/seed_from_csv.py proxies.csv --site www.kimeta.de

# map per-site boolean columns of your CSV to site hosts
python3 scripts/seed_from_csv.py proxies.csv \
    --map kimeta_ok=www.kimeta.de --map stellenanzeigen_ok=www.stellenanzeigen.de
```

CSV needs `protocol,host,port` (http/https only -- the aiohttp engine cannot
speak SOCKS). Entries land in `<state-dir>/winners.json`; proxyfetch
re-verifies every cached entry at run start and drops dead ones, so stale
seeds are harmless.

## Engine (set once, remembered)

The default probe engine is **aiohttp** (async, concurrency 300, TCP prescan
for large batches) — measured ~2.5x faster than thread pools on identical
workloads. The stdlib **threads** engine is a built-in fallback.

```bash
proxyfetch config set engine aiohttp    # persist forever (default)
proxyfetch config set engine threads    # ... or threads, remembered
proxyfetch config set concurrency 300   # parallel probe cap
proxyfetch config list                  # show saved vs default
proxyfetch config get|unset engine      # inspect / reset
```

One run can always override: `--engine threads --concurrency 100`, or
`PROXYFETCH_ENGINE=threads`, `PROXYFETCH_CONCURRENCY=100`.
Resolution: **CLI flag > env > saved config > default**. Saved settings live
in `~/.proxyfetch/config.json` (atomic, validated, corrupt-safe).

## CLI reference

| Flag | Default | Meaning |
|---|---|---|
| `URL` / `--url` | required | target URL (scheme optional, https assumed) |
| `--pages N` | 3 | result pages to fetch |
| `--name NAME` | host-derived | run name for output files |
| `--recipe R` | `auto` | `auto` \| `generic` \| `autoscout24` |
| `--css SEL` / `--field N=SEL` | – | CSS item selector + field map (universal extraction) |
| `--json-key PATH` / `--table N` | – | JSON dot-path / HTML table number |
| `--page-template TPL` | `?page=N` | pagination template with `{n}` |
| `--no-direct` | off | never try the direct-fetch fast path |
| `--engine E` | saved / `aiohttp` | probe engine for this run |
| `--concurrency N` | saved / `300` | max parallel probes |
| `--out DIR` / `--no-save` | `./out` | output dir / skip files |
| `--fresh` | off | ignore cached winners, harvest anew |
| `--state-dir DIR` | `~/.proxyfetch` | winner cache + saved config |
| `--budget S` / `--timeout S` | 420 / 40 | wall-clock budget / per-request timeout |
| `--headed` / `--no-browser` / `--watchdog S` | off / on-proof / 110 | browser escalation |
| `--locale` / `--timezone` | recipe default | browser profile |
| `--json` | off | agent mode: single JSON payload on stdout |
| `--quiet` / `--no-color` / `--json-logs` / `--log-file` / `--debug` | off | logging |

**Exit codes:** `0` ok · `1` ran, zero items · `2` usage/config · `3` no proxy · `4` internal · `130` ^C (partial results saved).

**Contract:** stdout = data, stderr = logs. With `--json`, stdout carries one
`proxyfetch.result/v1` document (`ok`, `count`, `items[]`, `meta.engine`,
`meta.mode` (`direct`\|`proxy`), `meta.proxies_used`, `meta.browser_proof`,
`files`, `error`) — failures also emit a valid payload. Full machine
contract: [AGENTS.md](AGENTS.md).

## Library

```python
from proxyfetch import Config, run

payload = run(Config(url="https://example.com/whatever", pages=1))  # engine="aiohttp"
print(payload["count"], payload["files"])
```

`run()` raises `ProxyFetchError` subclasses (`.exit_code`, `.hint`) on expected failures.

## Notes

- **Target-aware verification**: a proxy only wins if it fetches *your* URL and passes content checks — not just a ping.
- **Extraction recipes**: `autoscout24`, `immobilienscout24`, `generic`, CSS selectors, JSON endpoints, HTML tables and an auto chain; custom parsers in library mode. Never treat embedded tag scripts (`datadome`) as block markers — verify with real content.
- **Bot-protected sites**: WAF/captcha interstitials (AWS WAF, DataDome, Cloudflare, PerimeterX) are detected and never count as content — the run fails fast with an honest `error.hint` (vendor named) instead of spinning. Free public proxies cannot pass WAF challenges; such targets need a residential proxy.
- **Troubleshooting**: exit 3 → retry, lists churn by the minute (`--fresh` forces it). Slow cold start (~1–3 min) is the harvest→verify funnel; warm runs reuse the cache. Never send credentials — public proxies MITM.
- **Ethics**: public free-proxy lists, light personal automation of pages you may access; respect site terms.

MIT — see [LICENSE](LICENSE).
