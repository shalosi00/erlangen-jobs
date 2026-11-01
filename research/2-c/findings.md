# Research 2-c — Job aggregators & tech job boards with real APIs/RSS covering Germany

Agent: 2-c (research only). Scope: providers with programmatic access (API/RSS) usable for Asha (first FISI junior job, Erlangen/Nürnberg metro, DE-wide fallback).
Method: live curl tests from sandbox (HTTP codes recorded), plus web searches (some blocked by API rate limits — noted where unverified).
Date of tests: 2026-10-11/12 (sandbox clock).

## Legend
- ✅ = verified live in this session (HTTP 200 + sample payload captured)
- ⚠️ = alive but blocked/challenged from this sandbox (Cloudflare/bot wall) — treat as "reachable from a residential/normal IP, unverified here"
- ❌ = dead or discontinued

## Master table

| # | Provider | DE coverage | API/RSS type | Endpoint | Auth | Free tier | Freshness field | Notes |
|---|----------|-------------|--------------|----------|------|-----------|-----------------|-------|
| 1 | Arbeitnow | YES — German job board (Berlin-based, DE jobs incl. visa/remote) | REST JSON, PUBLIC, NO KEY | `GET https://www.arbeitnow.com/api/job-board-api?page=N` | none | free public API, "do not abuse, link back" | `created_at` (unix epoch), updated hourly, sorted by created_at | ✅ KEY FIND. 325 items/page; fields: `slug, company_name, title, url, location, description(html), tags, job_types, remote, created_at`. No server-side search param (API ignores `?search=`) → paginate + client-side filter. Terms in `meta.terms`. |
| 2 | Adzuna | YES — dedicated DE endpoint (`jobs/de/`) | REST JSON | `GET https://api.adzuna.com/v1/api/jobs/de/search/1?app_id=X&app_key=Y&what=…&where=…` | app_id + app_key | free tier: 25 calls/min, 250/day, 1,000/week, 2,500/month (default limits, per jobspipe.dev 2026-09) | `created` (ISO), plus `redirect_url`, `salary_min/max`, `description`, `location`, `company`, `title` | ✅ alive (fake key → 401 `AUTH_FAIL` with doc link). Registration: https://developer.adzuna.com (register app → instant app_id/app_key). DE data confirmed by dedicated `/jobs/de/` route. Best-structured results incl. salary. Free tier is ample for a 30-min cron (≈43 calls/day at 30-min interval). |
| 3 | Careerjet | YES (`locale=de_DE`, DE locations) | REST JSON — NEW v4 partner API | legacy `GET http://public.api.careerjet.net/search?keywords=&location=&locale=de_DE&affid=` (now locked); new: https://www.careerjet.com/partners/api | v4: partner key (registration); legacy needs user_ip + user_agent + Referer AND legacy auth | new users: registration required (affiliate/partner) | n/a (legacy blocked for new users) | ✅ tested: legacy endpoint WITHOUT key returns `{"error":"missing param user_ip or user_agent"}` (200), with params → 403 `Undeclared referrer`, with Referer → 401 `"The legacy Job Search API is only accessible for authenticated legacy users. Please use the new API (v4) instead: https://www.careerjet.com/partners/api"`. Partner portal page alive (200). |
| 4 | Jooble | YES — DE is a core country (jooble.org has .de) | REST, POST JSON | `POST https://jooble.org/api/{API-KEY}` body `{"keywords":"…","location":"…","page":1}` | API key | free key via registration; cited ~500 requests/key free (unverified) | n/a | ⚠️ endpoint live; fake key → 403 (HTML error page). Docs at help.jooble.org (REST API guide) — Cloudflare-challenged from sandbox. Registration: via jooble.org/api (key generation). |
| 5 | WhatJobs | YES — WhatJobs has whatjobs.de / DE data | REST JSON | `GET https://api.whatjobs.com/api/v1/jobs.json` (+ publisher key, `user_ip` etc.) | publisher key | affiliate/publisher program (registration) | n/a | ✅ tested: `HTTP 410` with `{"publisher":"Unknown publisher","user_ip":"Please fill in the required field."}` → endpoint alive, requires publisher identity + user_ip. Registration via WhatJobs affiliate/publisher program. |
| 6 | Talent.com | YES — large DE aggregator (talent.com/de) | XML/CSV feeds + API | partner program (feed push, CPC) | partner contract | NOT free self-serve; CPC/revenue model, contact required | n/a | Realistic for individuals: NO. Search shows "Self-serve API / XML feeds, CPC, contact required" (cavuno aggregator pricing table). Skip for personal pipeline. |
| 7 | Jobrapido | YES (de.jobrapido.com) | none public (B2B data licensing) | — | — | — | — | ⚠️ alive, 403 bot-wall on site. API is B2B/partner only. Not usable individually. |
| 8 | kimeta.de | YES — major German meta-search | RSS historically per search query | (historically `kimeta.de/jobrss?…`) | — | — | — | ⚠️ HTTP 503 bot-wall from sandbox (DNS fine → server-side block). Web search yields zero public evidence of a current RSS → treat as NO API. Crawler-partner integration only (logistics-jobs.com lists kimeta among its crawlers). |
| 9 | JOBworld (jobworld.de) | YES — German meta-search | no public API/RSS (probed `/rss`, `/jobs.rss` → 404) | — | — | — | — | ✅ site alive (200), HTML-only. |
| 10 | jobs.de | YES | no public API found; site behind bot-check | — | — | — | — | ⚠️ alive, "Bot Check" page. |
| 11 | Joblift | was DE aggregator | — | — | — | — | — | ❌ joblift.de returns CloudFront-style "ERROR: The request could not be satisfied" → service defunct/broken. Avoid. |
| 12 | Jobisite | claims DE RSS | RSS (unverified URL shape) | unknown (probes hit their OpenSearch-Dashboard app) | — | — | — | ❓ probe URLs returned wrong app page; RSS URL pattern unverified. Low quality board anyway. |
| 13 | GermanTechJobs.de | YES — DE tech jobs | API existed; now redirects | `GET https://germantechjobs.de/api/jobs` → 302 → `https://devitjobs.jobcopilot.com/signup?utm_source=dot_de_old` | signup wall now | — | — | ✅ tested: public API route redirects to JobCopilot signup → old public API effectively discontinued/paywalled. (GermanTechJobs = rebranded DevITjobs.) |
| 14 | jobtensor.com | YES — DE AI/IT job board, has **Ausbildung Hub** & Beruf Hub (entry-level!) | no public API found (`/API` → 404); site Cloudflare-protected | — | — | — | — | ⚠️ alive; scraping/API not available publicly; partner page exists. Useful manually, not programmatically. |
| 15 | Get-in-IT.de | YES | no API found | (`/jobboerse-jobs` → "Pacman ate this Page" 404) | — | — | — | ⚠️ alive; no programmatic access found. |
| 16 | heise.de/jobs | YES | RSS unverified — 503 bot-wall from sandbox | — | — | — | — | ⚠️ DNS fine, server 503s our IP. Unverified. |
| 17 | t3n.de/jobs | YES | RSS unverified — 503 bot-wall | — | — | — | — | ⚠️ same as above. |
| 18 | Munich-startups jobs | DE startup board | jobs subdomain DNS GONE (`jobs.munich-startup.de` → NXDOMAIN); `munich-startup.de/jobs` alive (HTML) | — | — | — | — | ❌ dedicated jobs subdomain dead; fallback page has no feed found. |
| 19 | Remotive | remote/global (EN jobs, some DE-remote) | REST JSON PUBLIC no key + RSS | `GET https://remotive.com/api/remote-jobs?limit=N&category=…` | none (attribution required, 24h delay) | free | `publication_date`, `created` | ✅ JSON API live (200) incl. legal notice: link back + don't re-post to aggregators; private paid API from $5k/mo. RSS `/remote-jobs/rss-feed` Cloudflare-challenged from sandbox. |
| 20 | RemoteOK | remote/global | REST JSON PUBLIC no key | `GET https://remoteok.com/api` (first element = legal notice) | none (attribution required) | free | `epoch`, `date` (ISO), `tags` incl. `junior`, `sysadmin` | ✅ live (200). `/remote-jobs.rss` → **410 Gone** (RSS discontinued; JSON is the way). |
| 21 | We Work Remotely | remote/global | RSS (multiple category feeds) | `https://weworkremotely.com/categories/remote-programming-jobs.rss`, `remote-devops-sysadmin-jobs.rss` | none | free | `pubDate` | ✅ live (200, XML RSS, 25 items). ⚠️ some old slugs (e.g. `remote-it-and-support-jobs.rss`) now 301→empty; `/feeds/…` variant Cloudflare-challenged. DevOps/Sysadmin feed is the FISI-relevant one. |
| 22 | Jobicy | global (eng/design/marketing) | RSS | `jobicy.com/gf-feed?feed=…` — ALL params now 404/301; `/rss`, `/feed` 404 | — | — | — | ❌/❓ legacy feed endpoint dead as tested; needs re-discovery of current feed URL (search blocked by rate limit). |
| 23 | Himalayas | remote/global | RSS PUBLIC no key | `GET https://himalayas.app/jobs/rss` | none | free | `pubDate` + custom ns `himalayasJobs` | ✅ live (200, proper RSS XML). |
| 24 | Berlin Startup Jobs | DE (Berlin-heavy) | RSS exists — Cloudflare-challenged from sandbox | `https://www.berlinstartupjobs.com/feed/` | none | free | pubDate | ⚠️ CF "Just a moment…" from sandbox. Likely works from normal IP. |
| 25 | azubi.de / ausbildung.de | YES — Ausbildung entry-level (Übernahme/first-job adjacent) | no public API found (`/api/` → HTML SPA) | — | — | — | — | ⚠️ both sites alive; no programmatic interface verified. |

## Verified test evidence (commands + HTTP codes + excerpts)

### 1. Arbeitnow (KEY FIND — free public DE job API, no key)
```
curl -s "https://www.arbeitnow.com/api/job-board-api"
→ HTTP 200 JSON
{"data":[{"slug":"social-media-content-manager-...-kevelaer-205313","company_name":"Sivara GmbH",
"title":"Social Media & Content Manager (m/w/d)...","description":"<p>...","location":...,"remote":...,
"tags":[...],"job_types":[],"created_at":...}],"links":{"next":"...?page=2"},"meta":{"current_page":1,"per_page":325,
"terms":"This is a free public API for jobs, please do not abuse. I would appreciate linking back to the site...",
"info":"Jobs are updated every hour and order by the `created_at` timestamp. Use `?page=` to paginate.
Read more: https://www.arbeitnow.com/blog/job-board-api"}}
```
Field list (verified): `company_name, created_at, description, job_types, location, remote, slug, tags, title, url`.
Pagination verified: `?page=2` → 200, 325 items, meta.current_page=2.
Caveat: `?search=systemintegration` is IGNORED by the API (still returns unfiltered 325 items; 2 of them contained "systemintegration" in title/description on a fresh page — good keyword incidence for FISI). Strategy: hourly pull page 1..N, filter client-side on title/tags/description for Nürnberg/Fürth/Erlangen + remote.
"Systemintegration" test: on the unfiltered first pages, matches found in description text (e.g. via client-side grep) — server-side filtering not available.

### 2. Adzuna DE (registration required, structured + salary data)
```
curl -s "https://api.adzuna.com/v1/api/jobs/de/search/1?app_id=test&app_key=test&what=systemintegration&where=n%C3%BCrnberg"
→ HTTP 401
{"display":"Authorisation failed","exception":"AUTH_FAIL","doc":"https://api.adzuna.com/v1/doc","__CLASS__":"Adzuna::API::Response::Exception"}
```
Alive; DE route exists; free registration at https://developer.adzuna.com. Expected result fields per docs: title, company.display_name, location.display_name, redirect_url, created, salary_min/max, description, latitude/longitude (not live-verified — no key in sandbox).

### 3. Careerjet — legacy API LOCKED for new users (important negative finding)
```
curl -s "http://public.api.careerjet.net/search?keywords=systemintegration&location=nuernberg&locale=de_DE&affid=0"
→ HTTP 200 {"error":"missing param user_ip or user_agent","type":"ERROR"}
+ user_ip&user_agent → HTTP 403 {"error":"Undeclared referrer. Please add a Referer header ..."}
+ Referer header → HTTP 401 {"error":"The legacy Job Search API is only accessible for authenticated
   legacy users. Please use the new API (v4) instead: https://www.careerjet.com/partners/api","type":"ERROR"}
```
HTTPS variant of legacy endpoint → connection failure (HTTP 000) from sandbox; HTTP works. New route: partner registration at https://www.careerjet.com/partners/api (page verified 200).

### 4. Jooble (key required, POST)
```
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"keywords":"systemintegration","location":"Nürnberg"}' \
  "https://jooble.org/api/00000000-0000-0000-0000-000000000000"
→ HTTP 403 (HTML error page)   # endpoint live; invalid key rejected
```
Docs: help.jooble.org REST API guide (CF-challenged from sandbox). Key generation via jooble.org registration. POST shape (per docs): `{keywords, location, page, salary, searchPeriod}`. Third-party summaries cite free ~500 requests/key (unverified).

### 5. WhatJobs (key required)
```
curl -s "https://api.whatjobs.com/api/v1/jobs.json"
→ HTTP 410 {"publisher":"Unknown publisher","user_ip":"Please fill in the required field."}
```
Endpoint alive; expects publisher key + user_ip. Registration via WhatJobs affiliate/publisher program.

### 6. Remotive (free JSON, remote/global)
```
curl -s "https://remotive.com/api/remote-jobs?limit=3"
→ HTTP 200 {"00-warning":"Remotive main domain moved to remotive.com! ... use remotive.com/api/remote-jobs",
"0-legal-notice":"...API documentation and access is granted so that developers can share our jobs further...
Jobs displayed are delayed by 24 hours... private, paid-for API ... starting budget $5k/mo ...", jobs:[...]}
```

### 7. RemoteOK (free JSON; RSS retired)
```
curl -s -A "Mozilla/5.0 ... research" "https://remoteok.com/api"
→ HTTP 200; element[0] = {"legal":"API Terms of Service: Please link back ... "},
element[1..] jobs: {"slug","id","epoch":1791619208,"date":"2026-10-10T08:00:08+00:00","company":"EDETEK",
"position":"...","tags":["dev","junior","ops","sys admin",...],"description":"<p>...",...}
curl -s "https://remoteok.com/remote-jobs.rss" → HTTP 410 Gone
```

### 8. We Work Remotely (RSS alive, category feeds)
```
curl -s "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"
→ HTTP 200 XML: <rss><channel><title>We Work Remotely: DevOps and Sysadmin Jobs</title>...
items: 25 (programming feed); item fields: title ("Company: Role"), link, guid, pubDate ("Tue, 29 Sep 2026 07:30:41 +0000")
NOTE: /categories/remote-it-and-support-jobs.rss → HTTP 301 with NO location (slug retired);
/categories/remote-programming-jobs.rss → 200.
```

### 9. Himalayas (free RSS)
```
curl -s "https://himalayas.app/jobs/rss"
→ HTTP 200 XML: <rss xmlns:himalayasJobs="https://himalayas.app/ns/jobs" ...>
<channel><title><![CDATA[Remote jobs from Himalayas]]>...
```

### 10. GermanTechJobs.de — public API route discontinued
```
curl -s -D - -o /dev/null "https://germantechjobs.de/api/jobs"
→ HTTP/2 302 ; location: https://devitjobs.jobcopilot.com/signup?utm_source=dot_de_old
```
Old "public API" now funnels to a JobCopilot signup wall → treat as NO free API.

### 10b. WWR feed slug map (verified HTTP codes, this session)
| feed slug | code |
|---|---|
| `remote-programming-jobs.rss` | 200 |
| `remote-devops-sysadmin-jobs.rss` | 200 (FISI-relevant) |
| `remote-customer-support-jobs.rss` | 200 |
| `remote-product-jobs.rss` | 200 |
| `remote-finance-and-legal-jobs.rss` | 301 |
| `remote-marketing-jobs.rss` | 301 |
| `remote-all-other-remote-jobs.rss` | 301 |
| `remote-design-and-ux-jobs.rss` | 301 |
| `remote-it-and-support-jobs.rss` (old slug) | 301, no Location header |

### 11. Dead / blocked / negative probes (recorded failures)
| Probe | Result |
|---|---|
| `https://jobicy.com/gf-feed?feed=it` / `feed=jobicy` (+count/category/industry) | HTTP 404 wp_die "This is not a valid feed template" / 301 empty |
| `https://jobicy.com/rss`, `/feed`, `/jobs-rss-feed` | 404 / weird CDN page |
| `https://www.golem.de/jobs/rss.xml` | HTTP 404 (Golem 404 page) — no job RSS at that path |
| `https://www.kimeta.de/` (+ `/jobrss`) | HTTP 503 bot-wall (DNS OK) — unverified |
| `https://www.heise.de/jobs/`, `t3n.de/jobs/` | HTTP 503 bot-wall from sandbox — unverified |
| `https://jobs.munich-startup.de/` | DNS NXDOMAIN — jobs subdomain dead; `munich-startup.de/jobs` alive HTML |
| `https://www.joblift.de/` | CloudFront-style ERROR page — defunct |
| `https://de.jobrapido.com/` | HTTP 403 Forbidden (bot-wall; B2B-only API) |
| `https://www.jobs.de/` | "Bot Check" page |
| `https://www.jobworld.de/rss`, `/jobs.rss` | HTTP 404 (site alive, no feed) |
| `https://www.get-in-it.de/jobboerse-jobs` | "Pacman ate this Page" 404 (site alive) |
| `https://www.jobisite.com/rss/...` (variants) | returns their OpenSearch-Dashboard app page — RSS URL pattern not found |
| `https://jobtensor.com/API` | 404 (site alive; has Ausbildung Hub; no public API found; CF-protects aggressive clients) |
| `https://www.ausbildung.de/api/` | HTML SPA (no API evidence) |
| `https://weworkremotely.com/feeds/remote-it-and-support-jobs.rss` | Cloudflare challenge |
| `https://www.berlinstartupjobs.com/feed/` | Cloudflare challenge (feed likely alive for normal IPs) |

## Which providers REQUIRE registration (exact URLs)
| Provider | Registration URL | Key shape |
|---|---|---|
| Adzuna | https://developer.adzuna.com (register app) | app_id + app_key query params |
| Careerjet (new v4) | https://www.careerjet.com/partners/api (partner portal) | partner key (affid) |
| Jooble | via https://jooble.org/api (key generation; docs: https://help.jooble.org) | UUID key in URL path, POST JSON |
| WhatJobs | WhatJobs affiliate/publisher program (via whatjobs.com) | publisher key, + user_ip param |
| Talent.com | partner/affiliate contract (CPC) — not self-serve | XML feed push |
| GermanTechJobs | no free API anymore — signup wall (JobCopilot) | — |

## Practical takeaways for the Asha pipeline (2-c slice)
1. **Arbeitnow** is the only confirmed **free, no-key, German** job API with hourly updates → backbone for DE-wide pull; filter client-side for `Systemintegration`, `Fachinformatiker`, Nürnberg/Fürth/Erlangen/Bamberg/Bayreuth, `remote:true`.
2. **Adzuna DE** is the best *queryable* API (keyword+geo server-side, salary fields) but needs a free key from developer.adzuna.com.
3. Careerjet's famously keyless legacy API is **closed to new users** (v4 = partner registration) — don't rely on it in the plan.
4. Remote-facing boards with zero-friction access: Remotive JSON, RemoteOK JSON (RSS 410'd), WWR RSS (DevOps/Sysadmin feed), Himalayas RSS — useful for `Systemintegration`+`remote` overlap; RemoteOK tags even include `junior`/`sysadmin`.
5. Aggregators (Jobrapido, kimeta, Talent.com, WhatJobs, Jooble): all behind registration or B2B walls; Jooble is the most realistic (free key, simple POST) for DE.
6. German tech boards (GermanTechJobs, jobtensor, Get-in-IT, heise, t3n, Golem): **no usable public API/RSS verified**; GermanTechJobs API retired to signup wall. Bot-walls block even page scraping from this sandbox.
7. Ausbildung niche (azubi.de, ausbildung.de, jobtensor Ausbildung Hub): web-only, no API verified.

## Open items (rate limits + bot-walls blocked full verification)
- Current Jobicy feed URL (legacy `gf-feed` dead; their docs page unreachable — sandbox egress proxy intercepts jobicy.com pages)
- Jooble free-tier exact limits (third-party summary cites ~500 requests/key; docs page CF-challenged)
- WhatJobs v1 API full param list (410-message confirms publisher+user_ip required; full docs behind affiliate onboarding)
- kimeta RSS existence (503 bot-wall + no public search evidence)
- heise/t3n jobs RSS paths (503 from sandbox)
- Jobisite correct RSS URL pattern
- Cross-check via API lists (publicapis.io / publicapis.dev "jobs" category, surfaced in searches) matches the DE-capable set found here: Adzuna, Jooble, Arbeitnow, Remotive, WhatJobs, Careerjet, Himalayas — no additional Germany-coverage provider identified in snippets.

## Provider scoring for the Asha pipeline (this slice)
- **Tier 1 (usable today, zero friction):** Arbeitnow JSON API (DE, no key) · Remotive JSON · RemoteOK JSON · WWR RSS (4 live feeds) · Himalayas RSS
- **Tier 2 (usable after free registration):** Adzuna DE (best query + salary fields, 250 calls/day free) · Jooble (POST, DE core market) · Careerjet v4 (partner signup) · WhatJobs (affiliate key)
- **Tier 3 (not realistically usable by an individual):** Talent.com (CPC contract) · Jobrapido/kimeta/JOBworld/jobs.de (B2B or no API) · GermanTechJobs (signup wall) · jobtensor/Get-in-IT/heise/t3n/Golem (no public API verified)
- **Dead:** Joblift · jobs.munich-startup.de · RemoteOK RSS · Jobicy gf-feed (legacy) · WWR legacy slugs
