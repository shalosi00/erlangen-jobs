# Research 2-d — ATS feeds, employer watchlist, automation recipes
Agent: 2-d (research only) · Date: 2026-10-11 (test session) · Target: junior FISI jobs, Nürnberg metro (Erlangen/Fürth/Nürnberg/Herzogenaurach/Forchheim/Bamberg)

---

## PART 1 — ATS-level public job feeds (verified live with curl)

### 1.1 ATS vendor of each major metro employer (live-tested)

| Employer | City | ATS vendor | Feed URL | HTTP | Status |
|---|---|---|---|---|---|
| DATEV eG | Nürnberg | **Workday** (`datev.wd3.myworkdayjobs.com`) | POST `https://datev.wd3.myworkdayjobs.com/wday/cxs/datev/Datev_Careers/jobs` | 200 | ✅ VERIFIED — full JSON job list + search |
| Schaeffler Group | Herzogenaurach | **SAP SuccessFactors (Career Site Builder)** | GET `https://jobs.schaeffler.com/feed.xml` (follow 302, add `-L`) | 200 | ✅ VERIFIED — 5.6 MB RSS/XML all jobs |
| adidas Group | Herzogenaurach | **SAP SuccessFactors (CSB, j2w)** | GET `https://careers.adidas-group.com/jobs/feed.xml` | 200 | ✅ VERIFIED — 5.9 MB XML all jobs |
| GfK / NielsenIQ | Nürnberg | **SmartRecruiters** | GET `https://api.smartrecruiters.com/v1/companies/NielsenIQ/postings?limit=50&country=de` | 200 | ✅ VERIFIED — 13 DE postings, 5 in Nuremberg |
| PUMA Group | Herzogenaurach | **Drupal + Elasticsearch** (in-house `dd_job_search`) | GET `https://about.puma.com/en/dd_job_search?search=&page=0` | 200 | ✅ VERIFIED — raw Elasticsearch JSON, 594 jobs |
| Siemens Healthineers | Erlangen/Forchheim | **Phenom People** | sitemap workaround: `https://careers.siemens-healthineers.com/sitemap.xml` → 303 → `/global/en/sitemap_index.xml` → `sitemap1.xml`,`sitemap2.xml` | 200 | ⚠️ PARTIAL — API blocked, sitemap has ~750 job URLs |
| Siemens AG | Erlangen (HQ) | **Avature** (`avacdn.net` libs confirmed) | none public — `jobs.siemens.com/en_US/externaljobs/searchResults` HTML-only, 302 on direct API | 302 | ❌ BLOCKED — SPA, robots-restricted |
| Hetzner Online | Nürnberg/Franken | **In-house** (`career.hetzner.com`, no ATS signature) | GET `https://career.hetzner.com/sitemap.xml` (142 URLs incl. every job page `/de/jobs/<slug>-j<id>/`) | 200 | ✅ VERIFIED — FISI Ausbildung jobs live (j586, j588, j749, j751) |
| N-ERGIE | Nürnberg | **my-job-shop** (Nuxt SPA + Typesense via `api.my-job-shop.com`) | `https://karriere.n-ergie.de/` (HTML 1.2 MB) + `https://api.my-job-shop.com/api/typesense` (needs runtime key) | 200 / 401 | ⚠️ PARTIAL — key extractable from JS bundle at runtime |
| NürnbergMesse | Nürnberg | **Personio** | GET `https://nuernbergmesse-gmbh.jobs.personio.de/xml` | 200 | ✅ VERIFIED — 56 positions |
| ITONICS GmbH | Erlangen | **Personio** | GET `https://itonics-gmbh.jobs.personio.de/xml` | 200 | ✅ VERIFIED — 15 positions |
| Nerdware | Nürnberg | **Personio** | GET `https://nerdware.jobs.personio.de/xml` | 200 | ✅ VERIFIED — 22 positions |

### 1.2 Generic ATS pattern verification (live curl)

| ATS | Endpoint pattern | Verified with | HTTP | Result |
|---|---|---|---|---|
| **Personio** | `https://<slug>.jobs.personio.de/xml` | `personio.jobs.personio.de/xml`, `itonics-gmbh…`, `nuernbergmesse-gmbh…`, `nerdware…` | 200 | XML root `<workzag-jobs>`, `<position>` elements with `<id> <office> <department> <name> <jobDescriptions>` (full HTML description). 404 when feed not enabled or slug wrong. |
| **Recruitee** | `https://<slug>.recruitee.com/api/offers/` | `yourcareer.recruitee.com` (via redirect from `gws.recruitee.com`) | 200 | JSON `{"offers":[…]}` with title/location/requirements. Slugs that moved return 404 (`bitpanda`, `sumup`). |
| **Greenhouse** | `https://boards-api.greenhouse.io/v1/boards/<board>/jobs` | `contentful` (Berlin company) | 200 | JSON `{"jobs":[{"absolute_url","location",…}]}`; append `?content=true` for full descriptions. |
| **Lever** | `https://api.lever.co/v0/postings/<company>?mode=json` | `leverdemo` (demo tenant) | 200 | JSON array with `categories`, `location`, `text`, `hostedUrl`. Real companies 404 (`deepl`, `doctolib`, `taxfix`, `yelp`) — many moved to Lever EU (`jobs.eu.lever.co`), discovery via `site:jobs.eu.lever.co`. |
| **SmartRecruiters** | `https://api.smartrecruiters.com/v1/companies/<company>/postings` | `NielsenIQ` | 200 | JSON with `totalFound`, `content[]` incl. `location.city/country`, `experienceLevel`; filters `?q=`, `?country=de`, `?city=Nuremberg`. |
| **Workable** | POST `https://apply.workable.com/api/v1/widget/accounts/<account>` body `{"query":"","location":[],"department":[],"worktype":[],"remote":[]}` | — | 404 for every guessed slug (`doodle`, `parloa`, `visma`, …) | ⚠️ Pattern documented (Workable readme/docs) but no live slug found this session. Discover real slugs via Google `site:apply.workable.com` or by checking job application URLs of target companies. |
| **Softgarden** | hosted `https://<client>.softgarden.io` (+ `wdteg.softgarden.io`) | `wdteg.softgarden.io` | 200 (HTML job list) | Job URLs `/job/<id>/<slug>?jobDbPVId=…`; `/jobs.xml`, `/xml`, `/rss` → 404. XML feed is per-customer on request; scrape HTML list instead. |
| **Workday (CXS)** | POST `https://<tenant>.wd<1-5>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs` body `{"appliedFacets":{},"limit":20,"offset":0,"searchText":"…"}`; detail: GET `/wday/cxs/<tenant>/<site>/job/<externalPath>` | `datev`/`Datev_Careers` | 200 | Detail returns `jobPostingInfo` (title, location, startDate, externalUrl, full description). Wrong site names → 500. |
| **SuccessFactors (CSB)** | GET `https://<jobs-host>/feed.xml` (Google-base RSS) | `jobs.schaeffler.com`, `careers.adidas-group.com/jobs/feed.xml` | 200 | RSS 2.0 with `referencenumber`, `city`, `country`, `category`, full CDATA description. 302 first hop — use `-L`. Not every CSB tenant enables the feed. |
| **Phenom People** | `https://<host>/api/apply/v2/jobs?domain=<domain>` | `careers.siemens-healthineers.com` | 200-but `{"status":"failure","errorMsg":"Tenant not identified"}`; POST `/widgets` also `{"status":"failure"}` | ❌ API locked down for this tenant. **Workaround:** SEO sitemaps (`/global/en/sitemap1.xml`, `sitemap2.xml`) list every `/global/en/job/R-xxxxx/...` URL → 200. |
| **Avature** | — | `jobs.siemens.com` | — | ❌ No public JSON; portal JS from `avacdn.net`; only HTML search. |
| **Empfehlungsbund / IT-Mittelstand** | `https://www.it-mittelstand.de/jobs.xml` | — | 200 (but SPA HTML, Angular — not raw XML) | Job data must be pulled from their JSON/HTML app; not a plug-and-play feed. |

### 1.3 Sample snippets (proof)

**DATEV — Workday CXS** (POST `/wday/cxs/datev/Datev_Careers/jobs`, body `{"appliedFacets":{},"limit":5,"offset":0,"searchText":"Fachinformatiker"}` → HTTP 200):
```json
{"total":4,"jobPostings":[{"title":"Ausbildung Fachinformatiker Systemintegration (m/w/d), ab 09/2027",
"externalPath":"/job/Nuremberg/Ausbildung-Fachinformatiker-Systemintegration--m-w-d---ab-09-2027_ID15218",
"locationsText":"Nuremberg","postedOn":"Posted 30+ Days Ago","bulletFields":["ID15218"]}]}
```
Detail (GET `/wday/cxs/datev/Datev_Careers/job/Nuremberg/Ausbildung-Fachinformatiker-Systemintegration--m-w-d---ab-09-2027_ID15218` → 200): `title: "Ausbildung Fachinformatiker Systemintegration (m/w/d), ab 09/2027"`, `location: Nuremberg`, `startDate: 2026-07-02`.

**PUMA — dd_job_search** (GET `/en/dd_job_search?search=&page=0` → 200, Elasticsearch JSON):
```json
{"took":1,"hits":{"total":{"value":594,"relation":"eq"},"hits":[{"_source":{"bundle":"dd_job",
"title":"Fitting Model für Passform Anproben (Candidate Pool)",
"body":"Home Product Development, Herzogenaurach, Germany …"}}]}}
```

**Personio — ITONICS** (`https://itonics-gmbh.jobs.personio.de/xml` → 200):
```xml
<?xml version="1.0" encoding="UTF-8"?><workzag-jobs>
<position><id>2834689</id><office>Hybrid Nürnberg</office><additionalOffices><office>Hybrid Berlin</office></additionalOffices>
<department>Marketing</department><recruitingCategory>Senior/Mid-level Employee</recruitingCategory>
<name>Business Development Manager (m/f/x) R&amp;D and Innovation</name> …</position></workzag-jobs>
```

**SmartRecruiters — NielsenIQ** (`?limit=3&country=de` → 200):
```json
{"offset":0,"limit":3,"totalFound":13,"content":[{"id":"744000153721859","name":"NIQ Early Career Program: Werkstudent Sales Support (w/m/d)","refNumber":"R26_0018004|DE","company":{"identifier":"NielsenIQ"},"location":{"city":"Frankfurt","country":"de"},"experienceLevel":{"id":"entry_level"}}]}
```

**SuccessFactors — Schaeffler** (`https://jobs.schaeffler.com/feed.xml`, needs `-L` → 200, 5.6 MB):
```xml
<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
<channel><title>Jobs at Schaeffler</title><description>Apply online for jobs at Schaeffler – … IT Jobs, Engineering Jobs, Trainee Positions …</description>
```

**adidas** (`https://careers.adidas-group.com/jobs/feed.xml` → 200, 5.9 MB): `<source><publisher>adidas Group careers</publisher><job><title><![CDATA[Sales associate …]]>…<referencenumber>332172</referencenumber><url><![CDATA[https://jobs.adidas-group.com/adidas/job/…/?feedId=301201&utm_source=j2w]]>` (j2w = Jobs2Web/SAP).

**Hetzner** (`career.hetzner.com/sitemap.xml` → 200): `<loc>https://career.hetzner.com/de/jobs/Ausbildung-Fachinformatiker-Systemintegration-mwd-de-j586/</loc>` — four FISI/IT Ausbildung pages live at test time. Job pages have `/apply/` sub-path (`/de/jobs/<slug>/apply/`).

**Siemens Healthineers** (`careers.siemens-healthineers.com/global/en/sitemap1.xml` → 200, 500 URLs; `sitemap2.xml` 252 URLs): job entries like `<loc>…/global/en/job/R-30160/Senior-Consumables-Engineer</loc>`; category pages `/global/en/c/software-engineering-cybersecurity-it-digital-r-d` useful for IT filter.

### 1.4 Key learnings / discovery recipes
- **Personio discovery**: Google/Bing `site:jobs.personio.de <Stadt>` works extremely well (this found NürnbergMesse, ITONICS, Nerdware, ZOLLHOF). Also `site:jobs.personio.de "Fachinformatiker"`. Feed is enabled per customer; 404 means no XML feed or wrong slug. Note ZOLLHOF incubator subdomain exists but `zollhof-betreiber-gmbh.jobs.personio.de/xml` = 404.
- **SuccessFactors discovery**: job links with `utm_source=j2w` = SuccessFactors/Jobs2Web → try `<host>/feed.xml` and `<host>/jobs/feed.xml`.
- **Workday discovery**: career URLs containing `.wd3.myworkdayjobs.com` (or wd1/wd5) → POST CXS JSON API; site name is in the URL path (`/de-DE/Datev_Careers` → tenant `datev`, site `Datev_Careers`).
- **Phenom discovery**: pages with `phApp` + `cdn.phenompeople.com` → try `/api/apply/v2/jobs?domain=…` (often blocked) → fallback: `/sitemap.xml` → `sitemap_index.xml`.
- **German-host blocking from this sandbox**: `www.n-ergie.de`, `noris.de`, `careers.brose.com` (NXDOMAIN), `stepstone.de`, `tealhq.com` timed out or refused plain curl; `z-ai page_reader` worked for most. From a German residential IP all should work.
- **GfK caveat**: `company/GfK` slug has 0 postings — GfK was absorbed into NielsenIQ (`NielsenIQ` slug), 5 of 13 German postings in Nuremberg at test time.

---

## PART 2 — Employer watchlist (FISI / junior IT / IT-Support), Erlangen–Fürth–Nürnberg–Herzogenaurach–Forchheim–Bamberg

Legend: **ATS** = verified live this session; city = company HQ / relevant local site.

### Big IT-active employers (highest posting volume, ATS verified)
| # | Employer | City | Sector / notes | ATS (status) |
|---|---|---|---|---|
| 1 | DATEV eG | Nürnberg | Tax software; 9 000+ employees; classic FISI Ausbildung + junior IT ops | Workday ✅ |
| 2 | Siemens Healthineers | Erlangen + Forchheim | Medtech; IT/OT infrastructure, service desks | Phenom ⚠️ (sitemap) |
| 3 | Siemens AG | Erlangen | Digital Industries, infra automation | Avature ❌ |
| 4 | Schaeffler Group | Herzogenaurach | Auto supplier; strong IT & OT infrastructure | SuccessFactors ✅ RSS |
| 5 | PUMA Group | Herzogenaurach | Sports brand; global IT | Drupal/ES ✅ JSON |
| 6 | adidas Group | Herzogenaurach | Sports brand; retail IT | SuccessFactors ✅ RSS |
| 7 | GfK (NielsenIQ) | Nürnberg | Market research; data center ops | SmartRecruiters ✅ |
| 8 | Hetzner Online | Nürnberg (HQ), Falkenstein | Hosting/data centers; junior-friendly, Ausbildung FISI live | In-house ✅ sitemap |
| 9 | N-ERGIE Gruppe | Nürnberg | Utility; IT, OT, grids | my-job-shop ⚠️ |
| 10 | NürnbergMesse | Nürnberg | Trade fair; event IT, infra | Personio ✅ |
| 11 | ITONICS GmbH | Erlangen | Innovation-management SaaS (FAU spin-off) | Personio ✅ |
| 12 | LEONI AG | Nürnberg | Wiring systems; big IT dept | n.t. (career site timed out from sandbox) |
| 13 | Nürnberger Versicherung | Nürnberg | Insurer; in-house IT, IT-Ausbildung | n.t. (`nuernberger.com/karriere/stellenangebote`) |
| 14 | Brose Fahrzeugteile | Bamberg (HQ) | Auto supplier; global IT | n.t. |
| 15 | Siemens CT / FAU spin-off ecosystem | Erlangen | — | — |

### Public sector / education (stable junior openings, DBI/Ausbildung)
| # | Employer | City | Notes |
|---|---|---|---|
| 16 | FAU — RRZE (Regional Computer Center) | Erlangen | FISI Ausbildung + IT-Support jobs; own portal (univis/bewerberportal) |
| 17 | Uniklinikum Erlangen | Erlangen | Hospital IT (KIS, infra) |
| 18 | Stadt Nürnberg — IT-Servicecenter | Nürnberg | Public IT, frequently posts FISI |
| 19 | TH Nürnberg (Ohm) | Nürnberg | Rechenzentrum IT jobs |
| 20 | VAG Verkehrs-Aktiengesellschaft | Nürnberg | Transit IT/OT |

### Industry / mid-caps with in-house IT
| # | Employer | City | Notes |
|---|---|---|---|
| 21 | STAEDTLER Mars | Nürnberg | Manufacturer; classic SMB IT |
| 22 | Faber-Castell | Stein (bei Nürnberg) | Manufacturer IT |
| 23 | PLAYMOBIL (geobra Brandstätter) | Zirndorf (bei Fürth) | Toy manufacturer; IT + OT |
| 24 | GfK Panel Services / NIQ Digital | Nürnberg | Panel infra, data centers |
| 25 | noris network AG | Nürnberg | Data center / cloud provider — top MSP-type target (site blocked from sandbox, verify from DE) |
| 26 | netcup GmbH | Nürnberg | Hosting (Anexia group); Linux-heavy junior infra roles |
| 27 | ZOLLHOF Tech Incubator startups | Nürnberg | Many small IT firms; some on Personio (XML feed 404 at test) |
| 28 | OSB AG | Bamberg | IT consulting/software (logistics) |
| 29 | Elektronikfirmen um Forchheim (Healthineers CT site) | Forchheim | Medtech suppliers, service tech + IT |

### MSPs / IT-Systemhäuser (found via search; cities per search snippets — verify before outreach)
| # | Employer | City (per source) | Notes |
|---|---|---|---|
| 30 | ATA Solutions | Nürnberg | IT-Dienstleister (`ata-solutions.de`) |
| 31 | IPExx Systems | Nürnberg | IT systems house (`ipexx-systems.de`) |
| 32 | Lehmann IT-Lösungen | Franken (Erl./Fürth area) | `lehmann-it-loesungen.de` |
| 33 | MSIT GmbH | (DE) | `msit-gmbh.de` — verify city (may be Karlsruhe) |
| 34 | HWS Gruppe | Franken | `hws-gruppe.de` |
| 35 | BES Systemhaus | Franken | `bes-systemhaus.de` |
| 36 | VIA APPIA GmbH | Nürnberg region | `via-appia.de` |
| 37 | B2 Innovations | Franken | `b2-innovations.de` |
| 38 | Bechtle AG — Nürnberg/Fürth branches | Nürnberg/Fürth | Large MSP/reseller; Systemintegration juniors |
| 39 | CANCOM SE — Nürnberg branch | Nürnberg | Large MSP/integrator |
| 40 | Computacenter — Nürnberg presence | Nürnberg | Integrator; junior service desk |
| 41 | Empfehlungsbund "IT-Mittelstand" member firms | Nürnberg+ | Discovery portal: `https://www.it-mittelstand.de/nuernberg` (Angular SPA, no raw XML) |
| 42 | BitMi member firms (Bundesverband IT-Mittelstand) | Bayern | Directory: `https://bitmi.de` |

**Discovery playbook (repeatable):**
1. Google: `site:jobs.personio.de Nürnberg` / `Fürth` / `Erlangen` / `Bamberg` / `Forchheim` / `Herzogenaurach` — directly yields Personio-hosted local employers with XML feeds.
2. Google: `site:*.softgarden.io`, `site:*.recruitee.com`, `site:*.myworkdayjobs.com` + city.
3. IHK Mittelfranken Ausbildungsfirmen search ("Fachinformatiker/-in Systemintegration"), `ihk-lehrstellenboerse.de`.
4. XING Suggest / LinkedIn company search "IT-Systemhaus" + 25 km Nürnberg; arbeitsagentur Jobbörse employer list for Systemintegration.
5. Empfehlungsbund regional network (it-mittelstand.de) — many Franconian system houses publish jobs there.

---

## PART 3 — Automation & acceleration recipes (2025/26)

### 3.1 n8n (self-hosted, free community edition) — RECOMMENDED BACKBONE
- Template search API works without auth: `https://api.n8n.io/api/templates/search?search=job%20alert` (verified 200). Job-pipeline templates found (live, with IDs):
  - `9270` — Freelancer.com Job Alert System + Auto Proposal (GPT 4.1)
  - `20408` — Triage Upwork job alert emails with Gmail, OpenAI, Telegram
  - `8173` — Automate LinkedIn Job Alerts with J-Search API + SMTP
  - `9240` — Daily LinkedIn Job Alerts with Apify Scraper, Google Sheets & Gmail
  - `9713` — Upwork Job Alerts → WhatsApp + Google Sheets
  - `5761` — Gmail→Slack AI-scored Upwork alerts (OpenRouter)
  - Template URL pattern: `https://n8n.io/workflows/<id>`
- **Viable local pipeline (all nodes exist in n8n):** Schedule Trigger (cron) → HTTP Request (Part-1 feeds: Workday POST JSON, Personio XML, SF RSS, SR JSON, PUMA JSON, Hetzner/SHS sitemaps) → XML/JSON parse → Code node (keyword filter: `Fachinformatiker|Systemintegration|IT-Support|Junior` + city whitelist Nürnberg/Erlangen/Fürth/Herzogenaurach/Forchheim/Bamberg) → Google Sheets append (dedupe by `referencenumber`/`id`) → Telegram node (chat message). RSS node covers SF RSS feeds directly.
- Raw files from this session: `research/2-d/raw/` (JSON/XML samples for each feed).

### 3.2 RSSHub — NOT usable for German boards
- Checked **all 1561 route namespaces** in RSSHub master (jsDelivr file API): **no routes for StepStone, XING, Indeed, Monster, arbeitsagentur, EURES, or any German job board** (only generic/Chinese boards + Hacker News "who is hiring").
- `rsshub.app` public instance sits behind Cloudflare (403 to curl). Conclusion: skip RSSHub for Germany; the Part-1 ATS feeds ARE the RSS/JSON layer, and SuccessFactors feed.xml gives ready RSS.

### 3.3 Make.com / Zapier
- No native StepStone/XING/Indeed-DE integrations (Zapier app directory: none for StepStone; XING legacy app gone). Both DO have: Gmail/Outlook triggers, Google Sheets, Telegram, RSS, webhooks.
- **Email-Parser trick (works):** StepStone/XING "Suchauftrag"/job-alert emails → Zapier **Email Parser** (parser.zapier.com) extracts title/company/link → Sheets row + Telegram ping. Make.com equivalent: Gmail Watch + Text Parser + Data Store.
- Alternative for same effect without Zapier: n8n Gmail/IMAP trigger (free) — better for volume.

### 3.4 Google Sheets as CSV tracker
- n8n/M Apps Script write directly (best). `IMPORTXML`/`IMPORTFEED` only works for public XML/RSS (SuccessFactors feed.xml CAN be pulled with `IMPORTFEED`, Personio XML with `IMPORTXML` XPaths — verified conceptually; sheets must escape CDATA-heavy cells).
- Structure: `date_added | company | title | city | url | source_feed | score | status | applied_on | followup`.
- Community add-ons ("rssimporter" etc.) exist but are stale/unmaintained; Apps Script `UrlFetchApp` + cron (time-driven trigger) is the robust pattern.

### 3.5 Telegram bots
- No official Arbeitsagentur job bot exists (BA offers the Jobbörse app + email alerts only; their REST API is another workstream). Public German job bots found via search are unofficial/spammy — treat as unreliable.
- **Recommended:** own bot in 10 min: @BotFather token → n8n Telegram node or Python `python-telegram-bot` + cron; push only postings scored ≥ threshold. Zero third-party risk.

### 3.6 LLM-based matching (cheap recipe)
- Any OpenAI-compatible endpoint (OpenAI gpt-4o-mini/5-mini, DeepSeek, GLM-4-flash — all < €0.5 per 1 000 postings). Batch 10 postings per call with strict JSON output.
- Prompt pattern (system): *"You score job postings for a junior Fachinformatiker Systemintegration (Ausbildung, entry-level, Nürnberg metro). Given CV_SUMMARY and JOB_JSON return {score: 0-100, reason: <15 words, German>, blockers: []}. Penalize: 3+ years experience required, only senior, different profession, unreachable city. Bonus: Ausbildung→Übernahme, IT-Support/Client/Server, Windows/AD, Ticketing, Germany DE language."*
- Pipeline: filter in n8n first (cheap), LLM only for survivors → keep `score ≥ 70` → Telegram. Dedupe before scoring (hash of `title+company`).

### 3.7 Auto-apply / autofill tools 2025/26 — tested status
| Tool | Site status | German boards | Verdict |
|---|---|---|---|
| Simplify.jobs | 200 ✅ | Extension autofills generic forms + Workday/SuccessFactors/Greenhouse/Lever HTML; job feed is **US-heavy**, no XING/StepStone integration | Partially useful in DE for ATS forms only; profile mainly US-shaped |
| Teal (tealhq.com) | 403 to sandbox (alive) | Same US focus; tracker fine | OK as tracker, not DE auto-apply |
| LazyApply | 200 ✅ | Claims: "Greenhouse, Dice, Indeed and Ziprecruiter" (read live from lazyapply.com) — **no XING/StepStone** | Poor fit for Germany |
| Sonara | site unreachable (000) | — | Defunct/unreachable |
| MassApply | unreachable (000) | — | Defunct/unreachable |
| JobRight.ai | 200 | US, LinkedIn-centric, invite-only | Not for DE |
| Careerflow.ai | 200 | LinkedIn-focused | Limited DE value |
| **XING "Bewerbung in einem Klick"** | native | Works where employer enables it; requires complete XING profile incl. uploaded CV; sends XING profile data | The real German "1-click" — keep profile complete and CV current; no third-party tool needed |
| **StepStone "1-Klick-Bewerbung"** | native | Profile-based quick apply on StepStone postings | Same principle |
- **Speed gain reality:** autofill/1-click cuts a manual application from ~8–12 min to ~1–3 min (3–5×), but mass-applying without tailoring shows in response rates; ATS bot-detection (Workday/SuccessFactors velocity checks) and GDPR concerns (CV passes through third-party extension servers) are real. Recommendation: automate **detection + scoring + tracking**, apply manually/1-click natively per job.

---

## Raw test artifacts
`research/2-d/raw/` — `ws_*.json` searches, `feedbax_nuernberg.json`, `lazyapply.json`, `simplify.json`, `rsshub_routes.json`; feed samples cached in /tmp during session (`datev_wd.json`, `wd_job.json`, `pv_*.xml`, `adidas_feed.xml`, `schaeffler_feed.xml` 5.6 MB, `niq_de.json`, `puma_dd*.json`, `shs_sm*.xml`, `hetzner_sitemap.xml`).
