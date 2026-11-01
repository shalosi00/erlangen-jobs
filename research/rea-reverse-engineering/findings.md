# REA (morluto/rea) — evaluation for the Asha job-toolkit

Date: 2026-10-14 · Evaluator: main agent · Request: user ("visit the repo and see if its useful")

## Identity & health (verified live)

- https://github.com/morluto/rea — "Reverse engineer anything with agents, from app
  behavior down to native binaries."
- 208,562 stars / 50,994 forks · MIT · TypeScript · created 2026-04, **pushed today**
  (2026-10-14) · npm `rea-agents` v6.4.0 · 529 open issues · 17-language README,
  trendshift badge, active Discord. Legendary-tier by every health metric.
- Smoke test in sandbox: `npx -y rea-agents@latest --help` runs clean on Node 24.21
  (v24.21.0 ≥ requirement). ~40 commands: native (Ghidra/IDA/Hopper), JS/Electron
  static analysis, `analyze-web-bundle` (CDP capture + static bundle analysis +
  source-map fetch), browser scenarios (Playwright), HAR/pcap/APK/APKtool/Flutter,
  Evidence-bundle comparisons.

## What it could theoretically give this project

1. `analyze-web-bundle` — attach CDP → capture a page's scripts → static analysis
   with **source locations** linking observed network requests back into the bundle.
2. HAR/SAZ capture digestion — "requests, responses, exposed payloads, source
   locations".
3. APK route (JADX headless) — decompile a job-board Android app to surface its API.

## Verdict: DEFER (not adopted now, not rejected)

### Why not now
- **Overlap, not gap.** The one RE-shaped problem we already solved — "find the real
  API behind a job-board frontend" — was cracked with agent-browser passive network
  capture in minutes (stellenanzeigen `/api/jobs`, Task 11). REA's browser analysis
  covers the same ground with nicer evidence bookkeeping, at the cost of wiring its
  CDP endpoint requirement into our tooling.
- **Policy, not capability, is our ceiling.** Remaining blocked sources are blocked
  by design, not by ignorance: kimeta pagination (robots `Disallow: /api/, /search`
  — documented green-zone boundary, Task 11), jobvector/jobrapido (CF + WAF),
  Adzuna/Jooble keys (captcha-gated signup, not automatable per policy). REA cannot
  — and must not — be used to drill past robots-disallowed zones or ToS walls.
- **No backlog item matches.** Current queue: cron/Telegram digest polish, proxy
  refresh scheduling, Asha-facing resume tooling. None is a reverse-engineering
  problem. Installing a 208k★ RE framework to "maybe find hidden endpoints" is
  exactly the jhao104/proxy_pool-class over-engineering we reject.

### Trigger conditions to revisit (write these down, then forget it)
1. **New SPA source** (#23+) whose XHR API is not discoverable by passive
   agent-browser observation within ~30 min → run `analyze-web-bundle` via a
   loopback CDP Chrome with `--fetch-source-maps` to map requests → bundle code.
2. A job-board **Android app** becomes the only policy-clean channel for a region
   source (own account, official app traffic observed, robots n/a) → `decode-android-resources`
   + JADX route.
3. Any future "how does feature X of site Y work" question where Evidence-linked
   static analysis beats manual bundle-mining.

### Cost of deferral
Zero. `npx rea-agents@latest` on demand; nothing installed, nothing configured,
no venv additions (no repeat of the pip-corruption incident class).

## Evidence
- GitHub API metadata snapshot: scripts/rea_api.json (stars/push dates as of 2026-10-14)
- README snapshot: scripts/rea_readme.md (390 lines)
- CLI smoke test: `rea@6.4.0 --help` exit 0 on Node v24.21.0
- `analyze-web-bundle --help`: requires loopback CDP HTTP endpoint + target id
  (i.e., integration with a running Chrome — not present, intentionally not built)
