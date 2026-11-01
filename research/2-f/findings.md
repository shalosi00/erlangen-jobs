# 2-f Findings: Legal risk matrix + Junior FISI market + Keyword/query lists
Agent 2-f | Lean research (14 searches, 5 page reads; several queries mis-hit budget due to search noise) | Oct 2025/2026 context

## TASK 1 — LEGAL (Germany/EU) — compact

**Baseline rules**
- **§87b UrhG (Datenbankherstellerrecht):** protects substantial investment in obtaining/verifying/presenting a database. Extracting a substantial part — or repeatedly extracting non-substantial parts (accumulation!) — of a job board's database = infringement. Viewing/downloading *individual* postings for personal use is fine; bulk-scraping a whole board is not. Job ad *text* can also be copyrighted (§2 UrhG), but storing title+link+excerpt for personal matching is clearly below the threshold.
- **GDPR:** job ads = business/company data, NOT personal data → scraping/storing ads themselves triggers no GDPR. Caveats: (a) ads containing named contact persons/recruiter emails → store minimally, legitimate interest Art. 6(1)(f), don't republish; (b) OLG Stuttgart 27.11.2023 (via dr-bahr.com): mere scraping ≠ GDPR damages absent concrete loss-of-control risk; (c) BGH 18.11.2024, VI ZR 10/24: *companies* are liable for scraped personal data — irrelevant to Asha's private pipeline, but keep personal data out of the CSV.
- **ToS enforceability:** German courts/CJEU enforce ToS bans on automated access even where copyright/database law fails (contractual claim). For private individuals the practical risk = account/IP ban + cease-and-desist (Abmahnung) cost exposure; §303a StGB (data sabotage) only at interference/overload scale.
- **robots.txt:** not a law; de-facto standard. Ignoring it is strong evidence in UWG (§4 Nr. 4 unfairness) assessments and proves "wissentlicher Verstoß". StepStone serves 403 even for robots.txt = maximum "keep out" signal.
- **Fair-use carve-out that favors Asha:** low-volume, private, non-commercial, non-competitive retrieval of individually published postings (via API or RSS) is at the harmless end of every precedent below.

**Precedents (name + 1 line)**
| Case | 1-line holding |
|---|---|
| BGH "Flugbuchungssystem II", Urt. 30.01.2019 – I ZR 57/17 | Screen scraping of flight booking data not per-se unfair under UWG, BUT ToS clause prohibiting automated access is a generally valid AGB → breach gives injunction/damages claims. |
| CJEU Ryanair v PR Aviation, C-30/14 (15.01.2015) | ToS banning automated access to a database NOT protected by database-maker law are still contractually enforceable (remand: BGH "Flugbuchungssystem" I ZR 46/12, 07.10.2015). |
| CJEU Innoweb v Wegener, C-202/12 (19.12.2013) | Meta-search that re-uses results of a protected search database = unlawful re-utilisation; repeated extraction of many small parts = "substantial part". |
| hiQ v LinkedIn (9th Cir. 2022, US) | US CFAA doesn't cover scraping public pages — persuasive only, NO binding effect in DE/EU (LinkedIn later settled + IP-bans aggressively). |

**Terms of key sources**
- **BA Jobsuche API (jobsuche.api.bund.dev):** official open offer, static key `jobboerse-jobsuche`, no documented rate limit. BUT BA Nutzungsbedingungen (checked live by agent 2-a, version 2026-07-08) prohibit automated use contrary to intended purpose / robots-like operation → personal-use polling with caching = intended use; re-hosting/selling = not. Modest polling (≤1 req/10s, hourly cron) is safe.
- **Adzuna API:** free tier (25 req/min, 250/day — verified by agent 2-c); terms require **attribution** "Jobs by Adzuna" linked to adzuna.de wherever results are displayed; no bulk redistribution. Keep attribution line in the CSV/dashboard → fully compliant. [Verify exact wording on developer.adzuna.com at setup.]
- **Careerjet:** new users must register (v4 partner API, careerjet.com/partners/api — legacy keyless API closed, verified by 2-c); requires `user_ip`/`user_agent`/`Referer` params + "Jobs by Careerjet" attribution.
- **RSS feeds (WWR, Himalayas, ATS feed.xml, Personio /xml etc.):** publishing a feed IS permission to consume; retrieve, cache, link back to source; keep intervals ≥30-60 min. Greenest method of all.
- **Arbeitnow:** meta.terms = free, link back, don't abuse (verified by 2-c).

**RISK MATRIX (source/method → risk → reasoning → mitigation)**
| Source/Method | Risk | 1-line reasoning | Mitigation |
|---|---|---|---|
| BA Jobsuche API (official, static key) | 🟢 GREEN | Official open offer; ToS allow intended personal use; no scraping needed. | Hourly cron, ≤1 req/10s, cache locally, don't re-publish full DB. |
| EURES API (europa.eu, no key) | 🟢 GREEN | Official EU service for jobseekers. | Cache; cite source "EURES". |
| Arbeitnow API | 🟢 GREEN | Explicit free offer; terms: link back + don't abuse. | Attribution in tracker, 1-2 pages/hour max. |
| Adzuna API | 🟢 GREEN | Registered key, documented limits; only duty = attribution. | Keep "Jobs by Adzuna" link, respect 25/min. |
| RSS feeds (WWR/Himalayas/ATS/Personio XML) | 🟢 GREEN | Publication of a feed = implicit consumption permission. | ≥30 min interval, keep source links, skip dead items. |
| XING SSR parsing (logged-out, personal, low volume) | 🟡 YELLOW | ToS forbid automated access; private low-volume logged-out use = low practical risk (IP ban worst case). | Hourly single query, ~1-2 req/hour, no redistribution, back off on 403. |
| LinkedIn guest endpoints (`jobs-guest/...`) | 🟡 YELLOW | Same ToS issue + aggressive IP throttling; public pages, no login, hiQ non-binding in EU. | ≤100 req/day, jittered delays, never with account cookies; stop on any block. |
| StepStone / Indeed / meinestadt scraping (Akamai/Cloudflare/DataDome) | 🔴 RED | Explicit ToS ban + active anti-bot; bypassing = AGB breach + UWG exposure + ban; robots.txt 403 = clear refusal. | Don't scrape. Use native email alerts + portal search manually; prefer ATS feeds (agent 2-d) instead. |
| Circumventing Cloudflare/Akamai (stealth browsers) | 🔴 RED | Anti-bot circumvention reads as wilful ToS breach; worst case §303a StGB at scale. | Excluded from pipeline. |

**Bottom line:** Asha's pipeline (official APIs + RSS + ATS feeds + light personal-polling of XING/LinkedIn) is legally low-risk; zero red methods needed — the red tier is redundant because agent 2-b/2-d verified legal alternatives covering most of those boards' content.

## TASK 2 — MARKET (compact, with sources)

- **BA Fachkräfteengpassanalyse:** Fachinformatiker/Systemintegration has been an **Engpassberuf (shortage score ≥2.0) continuously since 2018** — the most shortage-hit IT vocational group. In the **2025 edition** shortage eased across IT; ~7 Berufsgattungen dropped off the list incl. **IT-Vertrieb** (summary: frauundberuf-bw.de PDF "Fachkräfteengpassanalyse 2025"); core technical IT professions (incl. FISI) remained in engpass/observation zone. ⚠ Final PDF: cite exact 2025 score from statistik.arbeitsagentur.de → "Engpassanalyse" (my direct URL attempts 404'd; search "Fachkräfteengpassanalyse site:statistik.arbeitsagentur.de"). Practical read: shortage = for experienced profiles; junior slots are the bottleneck (below).
- **Junior slump evidence:** IT postings fell sharply post-2022 peak: **Bitkom: ~149,000 open IT positions (2023) → ~76,000 (2024)** [verify figure in PDF — Bitkom Fachkräftesituation]. dietechrecruiter.de (May 2024): "fast 34.000 Softwareentwickler arbeitslos oder arbeitssuchend" — overhang of laid-off seniors pushes juniors out of entry pipelines. Handelsblatt (Nov 2022) "IT-Fachkräfte fallen in der Krise weich". Practical consequence for Asha: apply broad + fast + certifications to pre-filter out; volume game (40-80 quality applications).
- **FISI entry salary 2025 (brutto/month):** **2.800–3.900 €** (ausbildung.de, updated 2026: "Einstiegsgehalt zwischen 2.800 und 3.900 Euro brutto im Monat"); Lohnspiegel.de: entry ≈ **3.200 €/mo** (vs ~4.600+ after 10 yrs); BA Entgeltatlas (all tenures, full-time): Bayern median ≈ 5.213 € (NRW 5.283, BW 5.322); low-end outliers ~2.250-2.900 € at small Systemhäuser (jobs-regional.de, meingehalt.net). Budget line: first job 2.900–3.600 € realistic in Bavaria, MSPs at the low end, industry/public at the high end.
- **Typical FISI employers:** MSP/Systemhaus (client rollout, 1st/2nd level,ticketing), IT-Abteilung of mid-size manufacturer, public sector (Stadt/Land/Uniklinik), telecommunications/hosting. Examples near Nürnberg/Erlangen: DATEV (Nbg, ~10k staff), Siemens/Siemens Healthineers (Erlangen), noris network, Bechtle/CANCOM/Computacenter branches, regional Systemhäuser (watchlist of 42 verified employers in research/2-d/findings.md).
- **Nürnberg metro IT cluster:** Metropolregion Nürnberg is a top-10 German IT location (~90-100k IT-related employees across the metro region, IT-Region Nürnberg e.V./it-nuernberg.de claims [verify]; strong Siemens/Siemens Healthineers/DATEV/GfK/adidas/PUMA/Schaeffler presence + dense Systemhaus landscape). Verified live by agent 2-a: BA API still returns 237-305 FISI/Systemintegration hits within 50 km of Erlangen — the *posted-volume* proxy that matters for the pipeline.
- **Application timing:** **TalentWorks study (2016, ~1,600 applications): applying within the first ~72 h of posting → up to 8× more interview invitations** (commonly cited 4-8×; talentworks.ca is now defunct — cite as secondary, e.g. via The Ladders/HubSpot roundups). Supported by fresh data: careery.pro (2026 dataset): **median first employer response 6.7 days; 25% respond within 4-5 days, 75% within 8** → early applicants are evaluated first and draw from the least-exhausted reviewer pool; huntr.co 2026: 11.2% interview rate for direct-company applications vs lower for crowded boards. → Pipeline requirement: poll hourly, alert within ≤24 h, apply within 72 h.
- **Certifications that speed up FISI job search (pick 2, not 5):**
  1. **AZ-900 Azure Fundamentals** — 1-2 weekends, ~100 €; opens cloud/onboarding language in MSP postings; most-requested junior cert in DE helpdesk/cloud listings.
  2. **ITIL 4 Foundation** — 1-2 weeks, ~300-500 €; directly matches Servicedesk/First-Level role descriptions and HR keyword filters.
  3. (Stretch) **CCNA** — 2-3 months; strong differentiator for Netzwerkadministrator/Systemhaus field-service track; only if networking is the target. LPIC-1 = alternative for Linux-heavy shops (weaker HR recognition in DE than AZ-900/CCNA).

## TASK 3 — KEYWORD / QUERY LISTS (copy-paste ready)

**DE core (BA `was=`, one string per run — run as multiple queries; no boolean):**
Fachinformatiker Systemintegration · Systemintegration · IT-Systemelektroniker · Systembetreuer · Systemadministrator · IT-Administrator · IT-Support · First-Level-Support · Second-Level-Support · IT-Servicedesk · Servicetechniker IT · IT-Techniker · Client Management · Netzwerkadministrator · Serveradministrator · Cloud-Administrator · Junior DevOps · Anwendungsbetreuer · IT-Service

**DE additional variants (5-10+ plausible in German postings):**
IT-Helpdesk · Helpdesk-Mitarbeiter · IT-Betreuung · IT-Mitarbeiter · IT-Infrastruktur · Infrastruktur-Administrator · Systemadministration · IT-Systemtechniker · IT-Supporter · Support-Techniker · IT-Anwenderbetreuung · Client-Manager · IT-Systemhaus Technik · Junior Systemadministrator · Fachinformatiker Anwendungsentwicklung (adjacent, filter after)

**EN variants (Adzuna `what=`, Arbeitnow client-side, LinkedIn `keywords=`):**
IT Support Specialist · System Administrator · Junior System Engineer · IT Operations · Service Desk · Helpdesk Technician · Junior IT Administrator

**Employer-type keywords (use in employer description/title matching):**
Systemhaus · IT-Dienstleister · IT-Dienstleistungen · Managed Service Provider · MSP · IT-Serviceprovider · IT-Systemhaus · Rechenzentrum

**Exclusions / negatives (drop from results, regex or list filter):**
Senior · Principal · Lead · Head of · Teamleitung · Architekt · 5 Jahre Berufserfahrung · mehrjährige Berufserfahrung · Werkstudent · Praktikum · Praktikant · Ausbildung · Azubi · Vertrieb · Sales · Student · Freelance · freiberuflich · Selbstständig

**Per-source query syntax (from verified agent findings 2-a/2-b/2-c):**
- **BA Jobsuche API** (`/pc/v6/jobs`, X-API-Key: jobboerse-jobsuche): `was=` = ONE string → loop over DE core list; pair with `arbeitsort=` (Erlangen/Nürnberg + `umfeld=2/25` km), `veroeffentlichtseit=` (100 = ≤24h? actually days filter 0/1/7/30/100), `angebotsart=1` (sozialversicherungspflichtig), `size=100`. No boolean OR → one request per keyword.
- **Adzuna** (`/v1/api/jobs/de/search/{page}`): `what=` supports space-separated terms (AND-ish), add `category=` (e.g. it-jobs), `where=Nürnberg`, `max_days_old=7`, `salary_min=2800`.
- **Arbeitnow** (`/api/job-board-api`): `?search=` IGNORED server-side → paginate page 1-2, client-side filter title/tags/description.
- **LinkedIn guest** (`/jobs-guest/jobs/api/seeMoreJobPostings/search`): `keywords=`, `location=Nürnberg%2C%20Bayern`, `start=` paging; keep ≤100 req/day.
- **XING SSR** (`/jobs/search?query=…&location=…`): `query=` free text; parse `serverData.APOLLO_STATE` (VisibleJob nodes) per agent 2-b.
- **EURES** (POST `/jv-searchengine/public/jv-search/search`): `keyword=` + `locationCodes=` (DE); base64 id → BA refnr.
- **Jooble** (POST `jooble.org/api/{key}`): JSON body `{"keywords":"…","location":"Nürnberg","page":1}`.

**Pipeline fit (1 line):** hourly cron → BA(19 queries) + Adzuna(5) + Arbeitnow(2 pages, filtered) + RSS(6 feeds) + LinkedIn/XING (2 queries, yellow tier) → dedupe by URL/title+employer → CSV (date, source, title, employer, city, url, salary-if-any, applied?, status) → apply ≤72 h window.
