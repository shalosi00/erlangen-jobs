# AGENTS.md — machine contract for AI agents

Compact, deterministic integration guide. Humans: see README.md.

## What it is

`proxyfetch URL` fetches a URL through a self-managed free-proxy pool
(harvest → verify → rotate → self-heal → stealth browser fallback) and
returns structured items. Use it when a target blocks datacenter IPs.

## Invocation

```bash
proxyfetch URL [--pages N] [--json] [--no-save] [--fresh] [--budget S] ...
proxyfetch URL --css 'item_selector' --field name='sub::text' [--page-template '...{n}...']
proxyfetch URL --json-key data.items | --table 2      # JSON endpoints / HTML tables
proxyfetch config set|get|unset|list [key] [value]     # persistent defaults
# or: python -m proxyfetch ...     (identical)
```

## I/O contract (DO NOT violate assumptions)

1. **stdout** carries exactly one machine payload when `--json` is set:
   JSON object, schema `proxyfetch.result/v1`, ends with a newline.
   Without `--json`, stdout is not stable — don't parse it.
2. **stderr** carries human logs; with `--json-logs` it is NDJSON
   (`{"ts","level","msg"}` per line).
3. Artifacts (unless `--no-save`): `<out>/<name>_live_<date>.json|csv`,
   paths also present in `payload.files`.

## Exit codes

| code | meaning | agent action |
|---|---|---|
| 0 | ok, `payload.ok == true` | consume `items` |
| 1 | zero items extracted | loosen URL/filters, try `--recipe generic`, add `--pages` |
| 2 | usage/config error | fix arguments (see `payload.error.hint`) |
| 3 | no working proxy | transient — retry once; if repeated, add `--fresh --budget 600` |
| 4 | internal error | re-run with `--debug`, inspect stderr |
| 130 | interrupted | partial results may exist in `out/` |

With `--json`, failures still print a valid payload on stdout with
`ok:false` and `error:{code,message,hint}` — parse stdout first, then check
the exit code.

## Key payload fields

```
schema            "proxyfetch.result/v1"
ok                boolean
count             len(items)
items[]           recipe-specific; autoscout24: id,title,version,price_eur,
                  year,km,ps,fuel,gear,seller,city,url
meta.pages_fetched / meta.proxies_used / meta.browser_proof
meta.browser_proof.engine   "lightpanda" | "cloakbrowser" (which engine rendered)
meta.engine         "aiohttp" (default) or "threads"
meta.mode           "direct" (fast path, no proxy) or "proxy"
files.json / files.csv   (null when --no-save)
interrupted       true when SIGINT was received
error             {code,message,hint} or null
```

`error.hint` is actionable: for bot-protected targets it names the WAF
vendor seen (aws-waf, datadome, cloudflare, perimeterx) and states that
free public proxies cannot pass — a residential proxy is required. Do not
retry such targets with `--fresh`; the wall is the IP reputation, not
churn.

## Flags that matter for agents

- `--json` — always use it when consuming programmatically.
- `--no-save` — skip file artifacts when you only want the payload.
- `--budget 420` — wall-clock cap; raise for many pages (`600–900`).
- `--fresh` — bypass winner cache (after exit 3, or stale-looking data).
- `--engine threads` — force the thread engine for one run (default aiohttp).
- `--css/--field/--json-key/--table` — universal extraction; items have
  arbitrary keys, CSV columns adapt automatically.
- `--no-direct` — force proxy-only (default tries a direct fetch first;
  `meta.mode` reports what was used).
- `--browser-engine lightpanda|cloakbrowser|auto` — render engine for the
  browser tier. Default `auto`: Lightpanda (self-healing CDP; starts its own
  server, routes through the pool proxy, accepts cookie walls, dismisses JS
  dialogs), falling back to CloakBrowser. `--headed` forces CloakBrowser.
- `--no-browser` — only when neither engine is installed; HTTP path still works.
- `--quiet` — suppress non-error logs on stderr.

## Persistent defaults (`proxyfetch config`)

`config set <key> <value>` writes `~/.proxyfetch/config.json` and every
future run uses it. Keys: `engine` (`aiohttp`|`threads`), `concurrency`
(integer). Resolution: CLI flag > env > saved config > default.
`proxyfetch config --json list` prints the effective values as one JSON
object on stdout (machine-safe).

## Environment variables (prefix `PROXYFETCH_`)

`PROXYFETCH_OUT` (out dir) · `PROXYFETCH_STATE_DIR` (winner cache + config) ·
`PROXYFETCH_BUDGET` (seconds) · `PROXYFETCH_ENGINE` (`aiohttp`|`threads`) ·
`PROXYFETCH_CONCURRENCY` (int) · `PROXYFETCH_NO_DIRECT` (`1` = always proxy) ·
`PROXYFETCH_NO_BROWSER` (`1` = disable) · `PROXYFETCH_BROWSER_ENGINE`
(`lightpanda`|`cloakbrowser`|`auto`).

Lightpanda engine (no prefix): `LIGHTPANDA_BIN` (binary path; else `$PATH` /
common locations), `LIGHTPANDA_CDP` (external CDP server URL to use instead of
managing one, or `off` to disable). Servers are reused while healthy,
restarted when dead, and cleaned up at process exit.

## Timing expectations

- unblocked target (direct fast path): seconds
- warm cache: ~40–60s for 3 pages
- cold start, blocked target: ~1–3 min (harvest → aiohttp verify funnel)
- browser proof adds ~2–5s when a Lightpanda server is already warm; a cold
  server start is ~1s
- budget default 420s bounds everything; partial results returned on timeout.

## Anti-patterns

- Don't pipe stdout of a non-`--json` run into a parser.
- Don't send authenticated/credential-bearing URLs — public proxies MITM.
- Don't interpret "datadome" in HTML as blocking; trust `payload.ok`.
- Don't retry exit 3 more than once with identical flags — vary `--fresh`.
