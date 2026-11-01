# Research 2-b — BIG commercial German job portals: programmatic access status (as of late 2025 / 2026)

Scope slice: XING Jobs (deep), StepStone, Indeed Germany, LinkedIn Jobs, meinestadt.de, Jobware.de,
Stellenanzeigen.de, glassdoor.de, Monster.de, kalaydo.de, Praktikum.de / AZUBIYO.
Use case: Asha — first junior FISI job, Erlangen (Nürnberg metro), fast search in a weak market.
All "verified" claims are live curl / page_reader tests run during this research session (see §15 test log).

---

## 1. XING Jobs (xing.com/jobs) — DEEP DIVE

### 1.1 Official public API
- **Job-seeker public API: DOES NOT EXIST.** The old XING public REST API (`https://dev.xing.com/api/v1/...`,
  OAuth1) was **closed in 2017** ("the XING public API has been closed. This developer group will no longer be
  operated in 2017" — XING GitHub issue, Jan 2017).
- `https://dev.xing.com/` is still ONLINE (verified via page_reader, HTTP 200) but now only hosts
  **"XING plugins"** and the **XING E-Recruiting API** — employer/partner only: "The XING API enables you to
  publish job advertisements on XING Jobs and monitor their status and performance" (help.xing.com, verified
  snippet dated Dec 3, 2025). No job-search endpoints for candidates; requires OAuth partner credentials.
- Bottom line: nothing official for a job seeker.

### 1.2 RSS / XML feeds
- None known today; none referenced anywhere in current XING properties. Not tested further (no candidate URL).

### 1.3 Undocumented endpoints — VERIFIED, the big finding of this slice
1. **Server-side-rendered job search page (works logged-out with plain curl!)**
   - `GET https://www.xing.com/jobs/search?keywords=Fachinformatiker&location=Erlangen`
     → 301/302 → `https://www.xing.com/jobs/search/ki?keywords=Fachinformatiker&location=Erlangen`
     → **HTTP 200, 363 KB HTML** served by CloudFront. No DataDome, no captcha, no JS needed.
   - The `/ki` page (new AI-driven search) **embeds the complete GraphQL response of the search inside the HTML**
     in `serverData.APOLLO_STATE`. VERIFIED contents for our test query:
     - Operation captured: `jobSearchByQuery({"consumer":"loggedout.web.jobs.conv_search_results.center",
       "limit":20,"offset":0,"query":{"keywords":"Fachinformatiker","location":{"text":"Erlangen"}},
       "returnAggregations":true,"searchMode":"SEMANTIC","trackRecent":true})`
     - **16 jobs returned as `VisibleJob:*` objects** with clean structured fields:
       `title`, `url` (e.g. https://www.xing.com/jobs/erlangen-it-support-mitarbeiter-157154285),
       `slug`, `globalId` (surn:x-xing:jobs:posting:…), `activeUntil`, `refreshedAt` (freshness!),
       `location.city`, `locations[]`, `employmentType`, `companyInfo.companyNameOverride`,
       `salary` (EUR minimum/maximum/median!), `paid`, `topJob`,
       `application.applyUrl` (third-party ATS URL or XING-hosted), `redirectsToThirdPartyUrl`,
       matching highlights (e.g. `job_highlight_early_applicant` = "Zu den Ersten gehören" — a signal to apply early).
     - Titles verified in state: "IT-Support Mitarbeiter (m/w/d)", "Systemadministrator (m/w/d)",
       "IT-Spezialist (w/m/d)", "IT-Administrator (m/w/d)", "Duales Studium Diplom-Verwaltungsinformatiker*in", …
   - **Parse recipe:** regex/JSON-decode the `serverData.APOLLO_STATE` block (it is JS-object syntax with
     `\u002F` escapes — sanitize then `json.loads`), iterate `VisibleJob:*` keys. Plain `curl` + Python = full
     structured feed, no browser, no login. This is the fastest legitimate programmatic XING access for a candidate.
   - Caveats: page text in the *visible* HTML inserts soft hyphens (`\xad`) into words ("Spe­zia­list") — an
     anti-scrape text obfuscation; the Apollo state JSON is NOT obfuscated. `Accept: application/json` on the
     search URL returns the same HTML (no JSON variant).
2. **XING One GraphQL API: `https://www.xing.com/graphql/api`** (found as `xingOneEndpoint` in the SPA config)
   - VERIFIED live: POST with named operation `query TmpQuery { viewer { id } }` + only the cookie pair
     `xing_csrf_token` (set on any www.xing.com response; echoed in `X-XING-CSRF` header)
     → **HTTP 200 `{"data":{"viewer":{"id":"0.22fe30"}}}`** — the transport is NOT auth-walled.
   - VERIFIED limits: introspection disabled ("Introspection is not allowed", HTTP 400 `INTROSPECTION`),
     arbitrary fields rejected ("Cannot query field … on type 'Query'") → **allow-listed/persisted operations
     only**. Real operation names/shapes would have to be lifted from the SPA JS bundle or a browser DevTools
     session. `jobSearchByQuery` (consumer string above) is the obvious candidate to reverse next.
3. robots.txt (verified, HTTP 200): many bot sections `Disallow: /jobs/search/` and `Disallow: /jobs/search?*`;
   also disallows `/jobs/posting_clicks`, `/user-ass/jobs/posting_pdf`. Explicit anti-scrape signal for crawlers.

### 1.4 Alerting speed ("fast" angle)
- XING **Job-Alerts** are keyword+location+radius saved searches with email notification; XING's own recruiting
  blog has an article on preventing "doppelte oder zu häufige Job-Benachrichtigungen" (duplicate/too frequent
  notifications) — i.e. alerts fire promptly and can feel noisy. Practical tactics:
  - create **multiple alerts** (Erlangen 25 km, Nürnberg 25 km, Fürth/Erlangen corridor, remote "Fachinformatiker"),
  - keep radius in km (XING offers radius selection), don't over-filter,
  - enable **mobile push** (fastest channel) + email as fallback,
  - XING "Jobvorschläge" on the home feed surfaces new matches daily.
- **Faster than any alert: poll the SSR endpoint yourself** (e.g. cron every 15–30 min). `refreshedAt` and
  `activeUntil` fields let you detect newly posted/refreshed ads. XING ads visibly show "Zu den Ersten gehören"
  (be among the first) gamification → early application is rewarded → polling beats alerts.

### 1.5 One-click apply
- XING-hosted jobs (ATS "onlyfy one", ex-TalentManager) offer **"Bewerbung in einem Klick"** — application with
  the XING profile data + uploaded CV, minutes not hours. Requires: complete XING profile + CV uploaded once.
- Jobs with `redirectsToThirdPartyUrl: true` (VERIFIED in the state: applyUrl → e.g. `jobs.breitseite.io`)
  jump to the employer ATS — no one-click there; the `application.__typename` field tells you in advance
  (UrlApplication = external; XING-hosted = one-click possible).

### 1.6 Anti-bot & scraping stance
- **No DataDome / no Cloudflare challenge on logged-out jobs pages** (verified: plain curl UA gets 363 KB HTML;
  headers only show CloudFront + Envoy + CSRF cookies). Lightweight personal-use polling of the SSR search page
  = technically trivial, low risk at human-like frequencies.
- robots.txt explicitly disallows `/jobs/search/` for bots (legal/ethical gray zone: disallow targets crawlers,
  not personal saved-search automation; German ToS (AGB) generally forbid automated access — keep volume tiny,
  no republication).
- Logged-in GraphQL via browser session is the next step if needed; endpoint itself is live and unauthenticated
  at transport level (verified).

---

## 2. StepStone (stepstone.de)

### 2.1 Official API
- **No public job-seeker API.** `api.stepstone.com` exists but is **partner/ATS-only** ("Job Details Service"
  testing page, api.stepstone.com, 2020) — for job-posting partners/ATS integrations, not candidates.

### 2.2 RSS
- Historical StepStone RSS job-search feeds no longer referenced; **unverifiable via curl — even robots.txt
  returns HTTP 403** (Akamai "Access Denied" via errors.edgesuite.net). Effectively dead for our purposes.

### 2.3 Undocumented endpoints
- Search pages (`/5/ergebnisliste.html?what=…&where=…`) are Next.js-class React apps; community scrapers parse
  **`__NEXT_DATA__` JSON embedded in HTML** (Apify "Stepstone Jobs Scraper" actor exists and works).
- **Curl CANNOT reach the HTML at all**: HTTP/2 → `INTERNAL_ERROR (err 2)` connection kill; HTTP/1.1 →
  HTTP 000 (connection reset). VERIFIED: StepStone runs **Akamai Bot Manager** with TLS-fingerprint filtering —
  needs a real browser / headless browser with stealth (Playwright + patched TLS) or a scraper API.
- LinkedIn-style guest JSON: none known.

### 2.4 Alerting speed
- **Jobagent** = classic saved-search email robot ("ein System von automatischen E-Mails" — StepStone help
  center). Multiple Jobagents per account; keyword + location + radius. Delivery: digest-style email, in
  practice max ~1×/day — NOT instant. Tactic: several agents (Erlangen, Nürnberg, Bayreuth–Würzburg corridor,
  remote) so nothing is missed between digests; also turn on app push if available.

### 2.5 One-click apply
- **"Schnellbewerbung"** with stored profile + CV; since Aug 16, 2022 guest checkout ("Als Gast fortfahren")
  was removed — >94 % of applications come from registered candidates (stellenanzeigen-treff.de). Registration
  + stored CV is mandatory for the fast path; then ~1–2 min per application.

### 2.6 Anti-bot & scraping stance
- Akamai Bot Manager (verified, aggressive — blocks even robots.txt for curl TLS). ToS forbid scraping.
- Realistic personal-use access: headless browser (Playwright) with realistic fingerprint, very low volume, or
  skip scraping and rely on Jobagent emails + manual browser. Risk: high (Akamai = sophisticated fingerprinting).

---

## 3. Indeed Germany (de.indeed.com)

### 3.1 Official API
- **Job-seeker API: dead.** Publisher/affiliate API retired ~2020; the job-search API deprecated 2023 and
  **switched off in 2024** (jobspipe.dev analysis). docs.indeed.com today offers only: employer **GraphQL posting
  APIs**, the **Publisher JavaScript Plugin** (partner front-end embed, approval required), and
  **Indeed Hiring Platform** products. Nothing for candidates. Indeed also announced policy changes from June
  2025 (anti "single-source" agency rules) and further organic-traffic changes for 2026 — the platform keeps
  closing itself off.

### 3.2 RSS — DEAD (verified)
- `https://rss.indeed.com/rss?q=Fachinformatiker&l=Erlangen` → **HTTP 403** (bot-wall HTML).
- `https://de.indeed.com/rss?q=…` → **HTTP 403**; `https://www.indeed.com/rss?q=…` → **HTTP 403**.
- All historical RSS variants are blocked/retired. Old blog guides still advertise them — outdated.

### 3.3 Undocumented endpoints
- `https://de.indeed.com/jobs?q=Fachinformatiker&l=Erlangen` with plain curl → **HTTP 401 "Authenticating…"
  page redirecting to login** (bot detection → login wall). JView/mobadvanced endpoints inherit the same wall.
- Practical 2025/26 state: Indeed requires a session (cookies + often JS challenge) for search HTML; scraping
  needs a real browser profile. Third-party aggregator APIs (Apify etc.) still sell Indeed scrapers.

### 3.4 Alerting speed
- Email job alerts: digest, **max ~1 email/day per alert** (default daily), multiple alerts allowed; mobile
  app push is faster. To speed up: several narrow alerts (Erlangen 25 km + Nürnberg + remote), turn on push,
  sort "date". Still slower than self-polling XING/LinkedIn.

### 3.5 One-click apply
- **Indeed Apply** (employer-hosted or Indeed-hosted): apply with Indeed profile + uploaded resume, often
  1–2 screens. Works only on jobs using Indeed Apply; otherwise external redirect. Profile completeness
  (resume, work history) is the prerequisite.

### 3.6 Anti-bot & scraping stance
- Cloudflare + login walls (verified 401/403). ToS forbid scraping. Personal-use polling = high breakage risk;
  alerts + browser are the reliable path.

---

## 4. LinkedIn Jobs (linkedin.com/jobs)

### 4.1 Official API
- **Jobs API is partner-only** (LinkedIn Talent Solutions partners / approved integrations). No developer
  self-service for job search. "Easy Apply" data is not exposed to end users.

### 4.2 RSS — none.

### 4.3 Undocumented endpoints — VERIFIED WORKING (the practical "API" for candidates)
- **Guest API (no login):**
  `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=Fachinformatiker&location=Erlangen&start=0`
  → **HTTP 200, 31 KB HTML fragment** of `<li class="…base-search-card…">` job cards.
- **Pagination verified:** `…&keywords=IT-Systemelektroniker&location=Erlangen,+Bayern&start=25` →
  **HTTP 200, 30 KB**, 50 `base-search-card` matches, real job URLs e.g.
  `…/jobs/view/ausbildung-zum-fachinformatiker-für-systemintegration-m-w-d-4470787253`,
  `…/it-specialist-digitalisierung-infrastruktur-m-w-d-at-avl-ditest-4465735338`.
- Parse the fragment with regex/BeautifulSoup (cards contain title, company, location, date, job URL).
  Job detail: `linkedin.com/jobs-guest/jobs/api/jobPosting/{id}` returns JSON-LD (community-documented;
  not re-tested this session — follow-up).
- Limitations: rate-limited (known 429s after bursts; expect ~100–300 req/day/IP tolerance), Cloudflare
  `__cf_bm` cookie present (verified in headers), parameters mirror the normal search (keywords, location,
  geoId, f_TPR for time filter e.g. `r86400` = last 24 h, f_WT for remote).
- **This endpoint + a cron job is the fastest "instant" LinkedIn channel** — faster than LinkedIn's own emails.

### 4.4 Alerting speed
- LinkedIn job alerts: frequency selectable per alert (daily digest standard; push notifications on mobile are
  near-instant), multiple alerts with locations. Fastest native = app push; still batched.

### 4.5 One-click apply
- **Easy Apply**: apply with LinkedIn profile + saved resume inside the site, ~1–2 min per application.
  Needs a reasonably complete profile and a saved resume PDF. Jobs marked "Apply" (external) redirect to ATS.

### 4.6 Anti-bot & scraping stance
- Cloudflare (verified `server: cloudflare`, `__cf_bm`); guest endpoint currently passes plain curl — but ToS
  explicitly forbid scraping (incl. guest pages); hiQ precedent does not help in Germany. Keep to very low,
  human-like rates if polling; prefer the official alert emails alongside.

---

## 5. meinestadt.de

- **API:** none public. meinestadt.de is a regional aggregator (owns some of its own ad inventory); no
  candidate-facing API found.
- **RSS:** candidate URLs tested — `/jobs/rss`, `/rss`, `/erlangen/jobs/rss` → **all HTTP 403**.
- **Page access:** `https://www.meinestadt.de/erlangen/jobs` → **HTTP 403 Akamai "Access Denied"** for curl
  (same Akamai family as StepStone). robots.txt itself was fetchable (HTTP 200) but page-level scraping needs
  a stealth browser.
- **Alerts:** Jobagent/Merkliste emails (daily digest) — standard.
- **Apply:** standard forms / external redirects; no notable one-click.
- **Verdict for Asha:** treat as manual-browsing + email-alert portal; no programmatic path found.

---

## 6. Jobware.de

- Regional job board (East/Westphalia strength — less Erlangen-critical, still useful for Bavaria/North-Bavaria
  scans).
- **Live test:** `https://www.jobware.de/` → plain curl **HTTP 403 "Forbidden"** (Apache-style); with full
  browser headers **HTTP 000 — connection killed**. Host resolves (62.93.211.30). Bot-hostile.
- **Platform note (verified via CDN evidence):** Jobware serves media from `cdn.orchard.prod.tenhil.io` — the
  **same platform as kalaydo.de** (also seen on kalaydo pages). Both are part of the markt.gruppe ecosystem
  (markt.gruppe = stellenanzeigen.de family; markt.gruppe acquired kalaydo in 2014 — online-recruiting.net,
  Eva Zils, article dated 2014-12-02).
- **API/RSS:** none public. **Alerts:** daily Jobagent email. **Apply:** standard.
- **Verdict:** email alerts only; scraping blocked at TLS/HTTP level for simple clients.

---

## 7. Stellenanzeigen.de

- markt.gruppe flagship. **Live tests:** homepage-level pages **HTTP 200 to curl** (205 KB), robots.txt
  **HTTP 200 and permissive** (only `/ajax/*`, tracking, print/bewerbung paths disallowed) — but:
  - guessed search paths return a 404-in-200 page ("Diese Seite wurde nicht gefunden");
  - the AJAX JSON backend `/ajax/jobsearch/?what=…&where=…` → **HTTP 403 (Cloudflare block page)**.
  Real search URLs are JS-driven from the homepage; server-side listing data not exposed without a browser.
- **API/RSS:** none public. **Alerts:** Jobagent-style daily emails. **Apply:** standard forms; "careeasy"
  quick-apply tools exist on the site.
- **Verdict:** browser-only for search; light scraping of static pages possible but listing data needs JS.

---

## 8. Glassdoor Germany (glassdoor.de)

- **Corporate status:** Glassdoor **legally merged into Indeed on July 1, 2026** (unchartedcareer.com; Wikipedia
  lists Glassdoor as Indeed-owned). Site remains live via glassdoor.com; glassdoor.de is the German entry.
- **Live test:** `https://www.glassdoor.de/` → **HTTP 403 with Cloudflare challenge**
  (`cdn-cgi/challenge-platform/h/g/orchestrate/chl_page/...` verified in the 403 page).
- **API:** the old public Glassdoor API was retired years ago; no candidate API.
- **RSS:** none. **Alerts:** job alert emails (daily) exist via glassdoor.com search.
- **Relevance for Asha:** mainly employer reviews/salaries pre-application, not a fast job source. Skip for the
  pipeline; use manually before interviews.

---

## 9. Monster.de — POST-BANKRUPTCY STATUS (explicitly requested)

- **What happened:** CareerBuilder + Monster (merged 2024) filed for **Chapter 11 on June 24, 2025** (Reuters,
  Washington Post, Fox Business). July 21, 2025: bankruptcy auction sold the job boards/brands to
  **Bold Holdings for $28M** (Reuters); sale **completed Sept 18, 2025** (Staffing Industry Analysts);
  Monster Government Solutions went separately to Sherrill-Lubinski/Eti-Net (Partner One Capital) for $13M.
- **Germany:** `https://www.monster.de/` → redirects to **`https://www.monster.com/de/`** → **HTTP 403 with
  DataDome** (`ct.captcha-delivery.com/c.js` verified in the block page). So Monster Germany still exists as a
  page on the international monster.com platform under the new owner, protected by DataDome.
- **API/RSS:** Monster's old APIs/RSS are gone; nothing public for candidates in 2025/26.
- **Alerts/Apply:** monster.com account alerts exist (daily emails); apply is external mostly.
- **Relevance for Asha:** German inventory has shrunk sharply post-2024 (Monster's German market share was
  already marginal); not worth programmatic effort. Keep at most one email alert.

---

## 10. kalaydo.de

- markt.gruppe classifieds/jobs portal (acquired 2014), running on the tenhil.io "Orchard" platform (verified
  via CDN URLs in HTML).
- **Live test:** `https://www.kalaydo.de/jobs/` → **HTTP 200, 218 KB**, but SPA without SSR job data
  (no `__NEXT_DATA__`, no JSON-LD `JobPosting`, no job links in raw HTML).
- **Undocumented JSON API — VERIFIED (partially):**
  `https://www.kalaydo.de/api/jobs/?what=IT&where=Nürnberg` (after 308 → trailing slash) →
  **HTTP 200, `application/json`**, structured response
  `{"jobAdSearchResultModel":{"jobAds":[…],"count":…,"countRelevant":…,"facettes":{…},"offlineJobAds":[]}}`.
  BUT: all tested parameter combos returned **empty jobAds** (count 0) — the GET stub seems to need a session
  or different params than the SPA actually sends (likely POST or cookie-bound). Follow-up: inspect SPA
  network calls in a browser to capture the real payload.
- **robots.txt:** open for Googlebot (only tracking/print/bewerbung paths disallowed) → scraping stance mild.
- **Verdict:** small job inventory, but the JSON structure is a nice-to-have; low priority for Erlangen.

---

## 11. Praktikum.de / AZUBIYO (post-Ausbildung angle)

- **Praktikum.de:** ALIVE (verified via page_reader: "praktikum.de | Praktikumsbörse für Praktikanten,
  Werkstudenten, Volontäre und Schüler"); plain curl from this sandbox **timed out (HTTP 000)** — mild
  bot filtering. Relevance for Asha: low (Praktikum/Werkstudent focus, not first-junior-job).
- **AZUBIYO (azubiyo.de):** ALIVE (search results verified; app with swipe-based Ausbildung search; "10×
  Deutschlands beste Jobbörse für Schüler"). Live test of a deep URL → **HTTP 403 Cloudflare**.
  No API/RSS. Use case: Ausbildungsplätze + **Anschlussübernahme** context — good for monitoring where FISI
  Ausbildungsstellen sit (firms that trained FISIs often hire juniors), but not a first-job API source.
- **Verdict:** manual + email alerts only; minor for the pipeline.

---

## 12. Cross-cutting findings for the report author

1. **The German "big portal" landscape has no candidate APIs.** Everything candidate-facing in 2025/26 is:
   SSR HTML (XING, partially), JSON-in-HTML (XING Apollo state), guest fragments (LinkedIn), or nothing
   (StepStone/Indeed/meinestadt behind Akamai/Cloudflare/logins).
2. **Historical RSS is dead across the board** (Indeed RSS 403 verified ×3 variants; StepStone/meinestadt
   RSS unreachable/blocked; none advertised by portals anymore).
3. **Fastest programmatic stack for Erlangen/Nürnberg:** XING SSR `/ki` Apollo-state parsing (verified) +
   LinkedIn guest API polling (verified) as the two "free real-time" channels; email digests (StepStone
   Jobagent, Indeed, XING Job-Alert, meinestadt, Jobware) as the slow but robust backbone.
4. **Anti-bot tiers observed (verified):** Akamai Bot Manager (stepstone.de, meinestadt.de — kills curl at
   TLS level, even robots.txt 403), DataDome (monster.com/de — captcha-delivery.com), Cloudflare challenge
   (glassdoor.de, azubiyo.de, stellenanzeigen.de /ajax), login walls (de.indeed.com 401), plain
   CloudFront+CSRF (xing.com — passable with curl).
5. **One-click apply prerequisites** (profile completeness) → set up once in week 1: XING profile+CV,
   StepStone profile+CV, Indeed profile+resume, LinkedIn profile+saved resume.

---

## 13. Comparison table

| Portal | Official API (seeker) | RSS | JSON endpoint usable | Alert speed (fastest native) | Apply speed (fastest native) | Scrape risk (personal use) |
|---|---|---|---|---|---|---|
| **XING Jobs** | none (E-Recruiting API = employer-only; public API closed 2017) | none | **YES — VERIFIED**: SSR `/jobs/search/ki` Apollo state (16 jobs w/ salary, applyUrl); GraphQL `www.xing.com/graphql/api` live (200, allow-listed ops) | fast (alerts prompt & frequent; push fastest) | **one-click** with XING profile (onlyfy jobs) | LOW: no DataDome on logged-out pages; robots.txt disallows /jobs/search (keep volume tiny) |
| **StepStone** | none (api.stepstone.com = partner/ATS only) | dead/blocked | **NO via curl** (Akamai TLS kill, HTTP 000/err2); `__NEXT_DATA__` needs stealth browser | daily digest (Jobagent) | Schnellbewerbung ~1–2 min (needs account+CV) | HIGH: Akamai Bot Manager verified |
| **Indeed DE** | none (Publisher API retired 2020; search API off 2024) | **DEAD (403 ×3 variants)** | NO via curl (HTTP 401 login wall) | daily email; app push faster | Indeed Apply (profile+resume) | HIGH: Cloudflare + login wall |
| **LinkedIn Jobs** | partner-only | none | **YES — VERIFIED**: guest `jobs-guest/jobs/api/seeMoreJobPostings/search` HTTP 200 (200+25 offset tested) | daily email; push near-instant | Easy Apply ~1–2 min | MEDIUM: works now, rate-limited (429 risk), ToS forbid |
| **meinestadt.de** | none | blocked (403) | NO (Akamai 403) | daily | standard | HIGH: Akamai verified |
| **Jobware.de** | none | none known | NO (403/000, connection kill) | daily | standard | MEDIUM-HIGH: bot-hostile TLS |
| **Stellenanzeigen.de** | none | none known | static pages 200, but `/ajax/*` JSON 403 (Cloudflare) | daily | standard forms | MEDIUM: Cloudflare on dynamic paths |
| **glassdoor.de** | none (merged into Indeed 07/2026) | none | NO (Cloudflare 403) | daily | standard | HIGH: Cloudflare challenge verified |
| **Monster.de** | none | none | NO → monster.com/de, DataDome 403 | daily | standard | HIGH: DataDome verified; post-bankruptcy (Bold Holdings 2025), shrinking inventory |
| **kalaydo.de** | none | none | **PARTIAL — VERIFIED**: `/api/jobs/` JSON 200 but empty sets (params/session needed) | n/a (small board) | standard | LOW: open robots, SPA |
| **Praktikum.de / AZUBIYO** | none | none | NO (CF 403 / curl timeout) | daily | standard | LOW-MED |

---

## 14. Recommended priority for Asha's pipeline (this slice's conclusion)

1. **XING SSR scraper** (`/jobs/search/ki` → APOLLO_STATE → VisibleJob[]) — verified trivially reachable with
   curl; poll 15–30 min; filter `location.city ∈ {Erlangen, Fürth, Nürnberg}` or radius via query; use
   `refreshedAt` for "new" detection; parse `application.__typename` to flag one-click-apply jobs.
2. **LinkedIn guest API poller** — verified 200 with parseable cards; low frequency (e.g. every 20 min, few
   pages, `f_TPR=r86400` for last-24h filter) to stay under rate limits.
3. **Email alert backbone** (StepStone Jobagent ×4 locations, Indeed alerts ×3, XING Job-Alert ×4, meinestadt,
   Jobware) — daily digests as safety net.
4. **Skip programmatically:** StepStone/Indeed/meinestadt scraping (Akamai/login walls), Monster (DataDome,
   declining), glassdoor (reviews only), kalaydo/stellenanzeigen (small inventory/JS-only).
5. **Reverse next:** XING GraphQL persisted operation `jobSearchByQuery` (consumer
   `loggedout.web.jobs.conv_search_results.center`) from the SPA bundle → then JSON-only polling without HTML
   parsing; LinkedIn `jobs-guest/jobs/api/jobPosting/{id}` JSON-LD detail fetch.

---

## 15. Verified live-test log (HTTP codes recorded this session)

| # | URL | Result |
|---|---|---|
| 1 | linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=Fachinformatiker&location=Erlangen&start=0 | **HTTP 200**, 31,262 B HTML job-card fragment |
| 2 | same, keywords=IT-Systemelektroniker&location=Erlangen,+Bayern&start=25 | **HTTP 200**, 30,542 B, 50 cards, real job URLs |
| 3 | rss.indeed.com/rss?q=Fachinformatiker&l=Erlangen | **HTTP 403** (bot-wall HTML) |
| 4 | de.indeed.com/rss?q=… | **HTTP 403** |
| 5 | www.indeed.com/rss?q=… | **HTTP 403** |
| 6 | de.indeed.com/jobs?q=Fachinformatiker&l=Erlangen | **HTTP 401** "Authenticating…" → login |
| 7 | xing.com/jobs/search?keywords=Fachinformatiker&location=Erlangen | 301 → /ki → **HTTP 200**, 363,521 B SSR, 16 jobs in APOLLO_STATE |
| 8 | xing.com/jobs/search/ki … + Accept: application/json | **HTTP 200 HTML** (no JSON variant) |
| 9 | xing.com/robots.txt | **HTTP 200**; Disallow: /jobs/search/ etc. |
| 10 | POST xing.com/graphql/api (named query, CSRF cookie) | **HTTP 200** {"data":{"viewer":{"id":"0.22fe30"}}} |
| 11 | POST xing.com/graphql/api introspection | **HTTP 400** "Introspection is not allowed" |
| 12 | POST xing.com/graphql/api jobsSearchResults guess | **HTTP 400** semantic error (allow-list only) |
| 13 | stepstone.de/5/ergebnisliste.html | HTTP/2 stream reset (err 2); HTTP/1.1 → **HTTP 000** |
| 14 | stepstone.de/robots.txt | **HTTP 403** Akamai Access Denied (edgesuite) |
| 15 | monster.de/ | 301 → monster.com/de/ → **HTTP 403 DataDome** (captcha-delivery.com) |
| 16 | glassdoor.de/ | **HTTP 403** Cloudflare challenge (challenge-platform) |
| 17 | kalaydo.de/jobs/ | **HTTP 200**, 218,408 B SPA, no SSR job data |
| 18 | kalaydo.de/api/jobs/?what=IT&where=Nürnberg | 308 → **HTTP 200 JSON**, empty result set |
| 19 | jobware.de/ | **HTTP 403** (basic curl) / **HTTP 000** (full headers) |
| 20 | meinestadt.de/erlangen/jobs (+ /jobs/rss, /rss) | **HTTP 403** Akamai Access Denied (×4) |
| 21 | praktikum.de/ | curl **HTTP 000** (timeout); page_reader **HTTP 200** (site alive) |
| 22 | dev.xing.com/ | **HTTP 200** via page_reader ("XING plugins \| XING Developer") |
| 23 | stellenanzeigen.de (static) / robots.txt | **HTTP 200** / **HTTP 200** (permissive) |
| 24 | stellenanzeigen.de/ajax/jobsearch/?… | **HTTP 403** Cloudflare block |
| 25 | azubiyo.de deep URL | **HTTP 403** Cloudflare (site alive per search results) |

**Search notes:** ~19 web searches + 3 page_reader calls; key sources: Reuters/WaPo/HR Dive/Staffing Industry
Analysts (Monster Chapter 11 + Bold Holdings sale), jobspipe.dev + docs.indeed.com (Indeed API timeline),
help.xing.com (Dec 2025: E-Recruiting API scope), online-recruiting.net/Eva Zils (markt.gruppe–kalaydo 2014),
helpcenter.stepstone.com (Jobagent), apify.com (StepStone scraper exists), GitHub (XING public API closed 2017).
