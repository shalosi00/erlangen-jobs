# Job Aggregators Round 2 — 24 German Targets Tested, 16 Documented (2026-10-13)

Follow-up to the GitHub-ecosystem survey (`research/github-repos/findings.md`). Goal: find **10+
more job aggregators** (Kimeta-class meta-search engines and niche boards) and figure out how to
make each one **work programmatically** for Asha's FISI junior search (Erlangen + 50 km).

All probes executed live from this workspace (datacenter IP). Raw evidence:
`research/aggregators-round2/probe/` (per-site HTML snapshots, `summary.json`), probe scripts:
`scripts/probe_aggregators_r1.py` … `r5.py`.

**Verdict up front: 5 aggregators work RIGHT NOW with plain `requests`** (no login, no key, no
proxy): **Connecticum, Get-in-IT, Berufsstart.de, Jobs.InFranken.de, Talent.com** — plus a unified
scraper is shipped in `scrapers/aggregator_search.py`. Another 11 are documented with the exact
blocker + the concrete bypass recipe.

---

## A. WORKING TODAY — parse recipes verified live

### 1. Connecticum (connecticum.de) — early-career / student / junior focus ✅
- **Search:** `GET https://www.connecticum.de/jobs?searchterm=fachinformatiker&submit=1`
- **Pagination:** `&page=2` (verified: page-2 link present in SERP)
- **Detail pages:** `/jobs/{slug}-{id}` e.g. `/jobs/quality-assurance-intern-documentation-compliance-1861248`
- **Company pages:** `/jobs/company-141624`
- Filters exist as form fields: `beschaeftigungsarten[]`, `fieldsgruppen[]` (GET-able).
- No JSON-LD; parse HTML anchors. No location param confirmed — filter Erlangen client-side
  (BA v6 API already covers geo; use Connecticum for cross-checking employers).
- **Why it matters:** exactly the target demographic (students, graduates, Berufseinsteiger).

### 2. Get-in-IT (get-in-it.de) — IT-specific job market ✅
- **Search:** `GET https://www.get-in-it.de/jobsuche?was=fachinformatiker&wo=Erlangen`
- **Cards:** server-rendered `<a class="CardJob_jobCard__…" href="/jobsuche/p309914?…" data-job-id="309914">`
- **Detail:** `/jobsuche/p{id}` — extract `data-job-id`, card text = title/company cluster.
- Site is Next.js; `__NEXT_DATA__` exists but pageProps are empty on `/jobsuche` — do NOT rely
  on the JSON data route (`/_next/data/…` resets connection from DC). Parse the HTML cards.
- **Why it matters:** IT-only board → less noise for FISI.

### 3. Berufsstart.de — entry-level job board (PHP classic) ✅
- **Search:** `GET https://www.berufsstart.de/ergebnisliste.php?suchbegriff=fachinformatiker`
  → live test: **1629 listings** platform-wide, detail links
  `appscripts/jobs/anzeigenAusgabe.php?AnzeigenID={id}`
- **City pages:** `/jobs/erlangen/`, `/jobs/nuernberg/`, `/jobs/fuerth/` … (Erlangen page = 200).
- Search form supports only keyword (`suchbegriff`) — filter by city client-side or use city pages.
- **Why it matters:** explicitly aimed at Ausbildungs-/Studienabsolventen = first-job audience.

### 4. Jobs.InFranken.de — **the local Franconia job board (Erlangen goldmine)** ✅
- **Search:** `GET https://jobs.infranken.de/suchergebnisse?Searchterm=fachinformatiker`
  → live test: **204 hits**; query params seen in form: `Searchterm`, `CityId`, `AreaRadius`,
  `JobCategory`, `JobSubCategory`.
- **Detail:** `/jobs/{id}` (e.g. `/jobs/16416872`), cards in `.jobad-container`/`.x-jobad-link`.
- Pagination via `page=` (page size 25, scroll code references it).
- **Why it matters:** regional newspaper portal covering Erlangen/Fürth/Nürnberg SMEs that never
  post on StepStone/Indeed; `AreaRadius` gives km filtering directly.

### 5. Talent.com Germany (de.talent.com) — global meta-aggregator ✅
- **Search:** `GET https://de.talent.com/jobs?k=fachinformatiker&l=Erlangen`
  → live test: 200, 613 KB, **12 result cards** on page 1 (`/view?id={19-digit-id}`).
- Cards are HTML; JSON-LD present but generic (not per-job). Parse `/view?id=` anchors.
- Also exposes a partner API (paid tier) — HTML route is free and sufficient.
- **Why it matters:** aggregates many smaller feeds incl. Kununu-sourced listings.

### 6. Interamt.de (public sector) — ⚠️ partial
- SPA (`interamt.de/stellensuche`, Angular-style bundle `/koop/js_26.0.5/interamt/app.js`);
  REST paths are not extractable from the bundle without deeper RE. Public-sector FISI roles
  (Stadt Erlangen, Landratsamt, TH Nuernberg IT) appear here first. Recipe: use Playwright once,
  record the XHR (likely `oppa-service/api/...`), then replay. Low volume, medium value.

---

## B. BLOCKED FROM THIS DATACENTER IP — concrete bypass recipes

### 7. Kimeta.de (the big German meta-search, ~1M listings) 🚫→proxy
- Probe: plain nginx **503** from DC, and later full connection reset → IP-range block.
- SEO URL pattern (works from residential): `https://www.kimeta.de/{keyword}-jobs-{city}`
  e.g. `https://www.kimeta.de/fachinformatiker-jobs-erlangen`; search endpoint `/suche?q=…&l=…`.
- Recipe: run through a **residential proxy** (e.g. one German residential exit) or local machine
  with requests + browser UA; results are server-rendered HTML (no JS needed).

### 8. Jobvector.de (science + IT) 🚫→Cloudflare
- Probe: 403 + `cf_challenge`. Bypass: **FlareSolverr** container or Playwright with stealth;
  alternatively use its white-label partners: jobs.sueddeutsche.de (same data).

### 9. Gigajob.com (free classifieds board) 🚫→Cloudflare
- Probe: **401 + cf_challenge** (both URLs). Bypass: FlareSolverr. Historic RSS feeds died.

### 10. Yourfirm.de (Mittelstand jobs) 🚫→Cloudflare
- Probe: 403 cf_challenge. Same bypass class as jobvector.

### 11. Stellenanzeigen.de (ZEIT-format board, 300k+ ads) 🚫→CF JS challenge
- Probe: 404/200 mix, but every page ships the CF challenge payload (510 KB challenge HTML).
- Bypass: FlareSolverr / Playwright; SERP URL: `/suche/?what=…&where=…`.

### 12. Jobrapido.de 🚫
- Probe: 403 with 93-byte body — hard IP block. Only viable via residential proxy.

### 13. Jobware.de ⚠️ flaky
- Homepage loads (200, 812 KB → later 338 KB), but `/jobs` and `/jo?jw_jobname=…` **timeout**
  intermittently — path-level rate limiting of DC IPs. Search UI is JS (`jobsearch-filter`
  widget, no server form). Recipe: Playwright + long timeouts + 1 req/30 s. Low priority.

### 14. Absolventa.de (entry-level IT/engineering) ⚠️ params verified, JS-rendered results
- Search param format extracted from turbo-frames:
  `/jobs?query[keywords][]=fachinformatiker&query[cities][]=erlangen-de-by`
  (`cities` slug = `{city}-de-{region}`; `fields[]=it` filter available).
- Infinite scroll loads `/jobs.turbo_stream?page=2&query[…]=…` (verified 200, but list itself is
  hydrated client-side). Recipe: **Playwright** headless with those exact params; or scrape the
  turbo_stream fragments. Autocomplete API works keyless:
  `/api/p/autocompletes/absolventa?q=fachinf`.

### 15. Careerjet Germany — 📡 API (free key), network-blocked from this DC
- `GET https://public.careerjet.com/search/jobs?v=2&locale_code=de_DE&keywords=fachinformatiker&location=Erlangen&affid={FREE_KEY}`
- Both hosts unreachable from this datacenter (connection reset) — but the **free affiliate API**
  is the cleanest legal route of all aggregators; register once, run from Asha's home IP.
- Companion: Jooble & Adzuna APIs (already covered in the PDF report, phase 1).

### 16. FAU Jobbörse (jobboerse.fau.de — university Erlangen-Nürnberg) 📡
- Connection refused/timeout from DC. From any German residential line it is a plain
  server-rendered board (student/HiWi/graduate jobs in Erlangen). Recipe: run from home IP.

---

## C. Dead ends (verified so you never waste time again)
- **trovit.de** — connection timeout (service effectively gone from DE).
- **meinefirma.de** — broken TLS chain (SSLError), site semi-maintained.
- **t3n.de/jobs** — 503 from DC (same WAF class as Kimeta).
- **jobs.de** — `botchallenge.html` redirect = actively bot-walled.
- **staufenbiel.de** — connection timeout.
- **it-mittelstand.de** — not actually a job board (marketing site).
- **germantechjobs.de** — gates job data behind signup (redirects `/jobs` → `/signup`); API is
  auth-only. Skip.
- Also re-confirmed blocked: jobvector, gigajob, yourfirm, stellenanzeigen (see above).

## D. Operational notes
1. **Network reality:** this workspace's datacenter IP is blocked/rate-limited by most German
   commercial boards (Cloudflare + nginx 503 patterns). The 5 working ones are the ones WITHOUT
   aggressive WAFs. For the rest: FlareSolverr container or a cheap German residential proxy
   unlocks kimeta, jobvector, gigajob, yourfirm, stellenanzeigen, jobrapido in one shot.
2. **Legality reminder:** all 5 working boards were accessed like a normal browser; keep ≤1 req/s,
   cache results, respect robots.txt drift. No login-circumvention anywhere.
3. **Coverage strategy for Asha:** BA v6 (geo+date authoritative) → InFranken (local SMEs) →
   Connecticum/Get-in-IT/Berufsstart (junior/IT niche) → Talent.com (long tail) → proxy tier
   (kimeta etc.) as stretch.
4. Probe artifacts: `probe/summary.json` + ~40 saved HTML snapshots for regression testing.
