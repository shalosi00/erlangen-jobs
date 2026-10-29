# Research 2-a: Bundesagentur für Arbeit (BA) Job Board & Official/Semi-Official Sources

**Agent:** 2-a | **Date of live testing:** 2026-10-11 (all timestamps in evidence are real)
**Verdict up front:** The BA "Jobsuche" REST API at `https://rest.arbeitsagentur.de/jobboerse/jobsuche-service` is **ALIVE, free, key-less-registration, no-auth beyond a static public header**, and is the single best programmatic job-posting source in Germany. The older `/jobads/jobs` endpoint + `jobsearch-beta` key widely cited in open-source projects is **DEAD (HTTP 403)**. EURES (EU portal) also has a working, undocumented-but-public JSON API that mirrors BA postings.

All test artifacts saved in `/home/z/my-project/research/2-a/` (filenames referenced inline).

---

## 1. BA Jobsuche REST API — VERIFIED LIVE (HTTP 200)

### 1.1 What is DEAD vs ALIVE (exact test evidence)

| Endpoint | Key | Result | Date |
|---|---|---|---|
| `https://rest.arbeitsagentur.de/jobads/jobs?was=...&wo=...&umkreis=50` | `X-API-Key: jobsearch-beta` | **403 Forbidden** (empty body, `Vary: User-Agent`) | 2026-10-11 |
| same, no key | — | 403 | 2026-10-11 |
| same, wrong key | `X-API-Key: WRONG-KEY-TEST` | 403 | 2026-10-11 |
| same with browser User-Agent / lowercase `x-api-key` | `jobsearch-beta` | 403 | 2026-10-11 |
| `jobboerse-jobsuche` key on `/jobads/jobs` | — | 403 (path dead, not key problem) | 2026-10-11 |
| `.../jobboerse/jobsuche-service/pc/v4/jobs` (search) | `jobboerse-jobsuche` | **403** (v4 search removed) | 2026-10-11 |
| `.../jobboerse/jobsuche-service/pc/v3/jobdetails/{b64}` | `jobboerse-jobsuche` | **403** (v3 detail removed) | 2026-10-11 |
| `.../jobboerse/jobsuche-service/pc/v4/app/jobs` (in official spec!) | `jobboerse-jobsuche` | **403** (spec is stale here) | 2026-10-11 |
| `.../jobboerse/jobsuche-service/pc/v6/jobs` (search) | `jobboerse-jobsuche` | **200 OK** ✅ | 2026-10-11 |
| `.../jobboerse/jobsuche-service/pc/v4/jobdetails/{b64(refnr)}` | `jobboerse-jobsuche` | **200 OK** ✅ | 2026-10-11 |
| `https://rest.arbeitsagentur.de/vermittlung/ag-darstellung-service/ct/v1/arbeitgeberlogo/{hash}` | `jobboerse-jobsuche` | **200 OK, image/webp (5616 bytes)** ✅ | 2026-10-11 |
| `https://jobsuche.api.bundesanbieter.de/` | — | DNS does not resolve (curl error 6) — host does not exist | 2026-10-11 |

**Root cause of the common "BA API is broken" reports:** people still use the retired `X-API-Key: jobsearch-beta` + base path `/jobads/jobs`. Both were replaced by the Jobbörse mobile-app API (`/jobboerse/jobsuche-service/...` + key `jobboerse-jobsuche`).

### 1.2 The exact WORKING curl commands

**Search (verified):**
```bash
curl -sS -m 30 \
  -H "X-API-Key: jobboerse-jobsuche" \
  "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs?was=Systemintegration&wo=Erlangen&umkreis=50&page=1&size=100"
# → HTTP 200, JSON, maxErgebnisse=305
```

**Job detail (verified):** `referenznummer` from search (e.g. `10001-1003832993-S`) → base64 → path:
```bash
curl -sS -m 30 -H "X-API-Key: jobboerse-jobsuche" \
  "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/MTAwMDEtMTAwMzgzMjk5My1T"
# → HTTP 200, full posting incl. stellenangebotsBeschreibung (Markdown-ish text)
```

**Employer logo (verified):**
```bash
curl -sS -m 30 -H "X-API-Key: jobboerse-jobsuche" \
  "https://rest.arbeitsagentur.de/vermittlung/ag-darstellung-service/ct/v1/arbeitgeberlogo/<arbeitgeberKundennummerHash URL-encoded>"
# → 200 image/webp; 404 if no logo (normal case)
```

### 1.3 Authentication

- Header: `X-API-Key: jobboerse-jobsuche`
- This is a **public static clientId, not a secret** — no registration, no OAuth, no signup. Documented verbatim in the official OpenAPI spec (`info.description`): *"Die Authentifizierung funktioniert über die clientId: clientId: jobboerse-jobsuche. Bei folgenden GET-requests ist die clientId als Header-Parameter 'X-API-Key' zu übergeben."*
- Key acquisition: **none needed** (copy the string). Free.

### 1.4 Endpoints (official OpenAPI spec v2.1.0 at jobsuche.api.bund.dev + live-verified status)

| Path | Status | Purpose |
|---|---|---|
| `GET /pc/v6/jobs` | ✅ LIVE | Search (the only working search) |
| `GET /pc/v4/jobdetails/{encryptedJobCode}` | ✅ LIVE | Full posting detail (`base64(refnr)`) |
| `GET /ct/v1/arbeitgeberlogo/{kundennummerHash}` | ✅ LIVE | Employer logo (base: `rest.arbeitsagentur.de/vermittlung/ag-darstellung-service`) |
| `GET /pc/v4/app/jobs` | ❌ 403 | documented but dead |
| `GET /pc/v3/jobdetails/{encryptedJobCode}` | ❌ 403 | dead |
| `POST /pc/v3/jobs/{jobid}/bewerbung`, `/pd/v3/...` | (SPA config) | contact/apply endpoints (auth needed; out of scope) |

Production proof: the official www.arbeitsagentur.de Jobsuche SPA itself calls exactly these endpoints — its `config/config.js` (fetched live) contains:
`endpoints__stellenangebote__host: https://rest.arbeitsagentur.de`, prefix `/jobboerse/jobsuche-service`, resource `/pc/v6/jobs`; jobdetails resource `/pc/v4/jobdetails` (file: `spa_config.js`).

### 1.5 Search parameters (v6/jobs) — verified live

| Param | Meaning | Values / notes |
|---|---|---|
| `was` | free-text job title | e.g. `Systemintegration`, `Fachinformatiker Systemintegration` |
| `wo` | free-text location | e.g. `Erlangen`, `Nürnberg` (URL-encode umlauts: `N%C3%BCrnberg`) |
| `umkreis` | radius km around `wo` | 50 verified |
| `page` | page, starts at 1 | `page=999` → **HTTP 400** (validate before deep paging) |
| `size` | page size | up to **100 verified** (size=100 returned 100 items) |
| `veroeffentlichtseit` | published within last N days | 1 verified (freshness filter!); range 0–100 per bundesAPI README; `=200` behaved like unset (no error) |
| `angebotsart` | posting type | `1`=ARBEIT, `2`=SELBSTÄNDIGKEIT, `4`=AUSBILDUNG/Duales Studium, `34`=Praktikum/Trainee (semicolons for multiple) |
| `arbeitszeit` | working time | `vz`=VOLLZEIT, `tz`=TEILZEIT, `snw`=Schicht/Nacht/WE, `ho`=Homeoffice, `mj`=Minijob; semicolon-separated |
| `befristung` | contract duration | `1`=befristet, `2`=unbefristet; semicolon-separated |
| `zeitarbeit` | include temp agencies | true/false (default true) |
| `pav` | include private Arbeitsvermittlungen | true/false |
| `behinderung` | jobs for severely disabled | true/false |
| `arbeitgeber` | employer filter | case-sensitive, exact match (e.g. `Deutsche%20Bahn%20AG`) |
| `berufsfeld` | occupational field free-text | e.g. `Informatik` — broader net than `was` (478 hits Erlangen 50km vs 305 for "Systemintegration") |
| `corona` | legacy | exists in spec, harmless |
| `beherrscheSprache`, `publishedSince` (old `/jobads` names) | — | silently ignored by v6 (HTTP 200, ignored) |

Legacy params from the dead `/jobads/jobs` API that do **not** exist in v6: `art`, `beschaeftigungsjobs`, `beherrscheSprache`, `angebotsart` semantics unchanged.

### 1.6 Response schema — LIVE field reference (ground truth, supersedes the spec!)

**Search response top level** (file: `sample_full_v6.json`, 155,832 bytes, 100 items):
`ergebnisliste[]`, `maxErgebnisse` (total count → pagination math), `page`, `size`, `woOutput` (parsed location: `bereinigterOrt`, `suchmodus: "UMKREISSUCHE"`, `koordinaten[{lat,lon}]`), `facetten` (aggregation counts, see 1.8).

**Item fields** (union of 100 live items — complete list):
`aenderungsdatum`, `alleBerufe[]`, `alternativBeruf1`, `alternativBeruf2`, `arbeitgeberKundennummerHash`, `arbeitszeitSchichtNachtWochenende`, `arbeitszeitTeilzeitAbend`, `arbeitszeitTeilzeitFlexibel`, `arbeitszeitTeilzeitNachmittag`, `arbeitszeitTeilzeitVormittag`, `arbeitszeitVollzeit`, `artDerVerguetung`, `ausbildungsart`, `ausbildungsverguetungJahr1..4`, `befristungInMonaten`, `chiffrenummer`, `datumErsteVeroeffentlichung`, `eintrittszeitraum{von,bis}`, `entfernung` (km from `wo` — useful for the 50km filter!), `externeURL`, `firma`, `gehaltsspanneVon`, `gehaltsspanneBis`, `hauptberuf`, `homeofficemoeglich`, `homeofficetyp`, `istGeringfuegigeBeschaeftigung`, `quereinstiegGeeignet`, `referenznummer` (unique key), `stellenangebotsTitel`, `stellenangebotsart` (ARBEIT/AUSBILDUNG/...), `stellenlokationen[]` (`adresse{ort,plz,region,land}`, `breite`, `laenge` = lat/lon), `verguetungsangabe`, `veroeffentlichungszeitraum{von}`, `vertragsdauer`.

**IMPORTANT DRIFT:** the official OpenAPI spec still documents the OLD response shape (`stellenangebote[]` with `hashId`, `refnr`, `beruf`, `arbeitgeber`). The live v6 API returns `ergebnisliste[]` with `referenznummer`, `stellenangebotsTitel`, `firma`. `hashId` does **not exist anymore** (verified by grep over 100-item response: `hashId -> NOT FOUND`). Detail endpoint takes `base64(referenznummer)`, not hashId.

**Detail response fields** (file: `detail_v4.json`): `stellenangebotsart`, `stellenangebotsTitel`, `stellenangebotsBeschreibung` (full text, markdown-ish), `arbeitszeitVollzeit`, `eintrittszeitraum`, `verguetungsangabe`, `vertragsdauer`, `stellenlokationen[]`, `veroeffentlichungszeitraum`, `datumErsteVeroeffentlichung`, `aenderungsdatum`, `istBetreut`, `hauptberuf`, `firma`, `arbeitgeberKundennummerHash`, `allianzpartnerUrl`, `allianzpartnerName`, `referenznummer`.

### 1.7 Verified result counts (live, 2026-10-11) — directly relevant to Asha

| Query (`was`, `wo`, `umkreis`) | Total (`maxErgebnisse`) | of which from external boards (facet) |
|---|---|---|
| Fachinformatiker Systemintegration / Erlangen / 50km | **238** | 14 |
| Fachinformatiker Systemintegration / Nürnberg / 50km | **237** | 16 |
| Systemintegration / Erlangen / 50km (broader) | **305** | 15 |
| Systemintegration / Erlangen / 50km / `angebotsart=1` (jobs only) | **225** | — |
| Systemintegration / Erlangen / 50km / `veroeffentlichtseit=1` (last 24h) | **1** | — |
| Systemintegration / Erlangen / 50km / `veroeffentlichtseit=7` | **56** | — |
| IT-Systemelektroniker / Erlangen / 50km | **35** | 0 |
| IT-Systemelektroniker / Nürnberg / 50km | **32** | 0 |
| IT-Support / Nürnberg / 50km | **316** | — |
| IT-Administrator / Erlangen / 50km | **96** | — |
| berufsfeld=Informatik / Erlangen / 50km | **478** | — |
| Systemintegration / Germany-wide (no `wo`) | **6,755** | 618 |
| Fachinformatiker Systemintegration / Germany-wide | **5,190** | 583 |

Interpretation: keyword precision matters (`Fachinformatiker Systemintegration` ≈ 238 vs `Systemintegration` 305 in same radius — many of the extra hits are Ausbildung posts; `angebotsart=1` trims those). Note the Erlangen-50km and Nürnberg-50km counts are nearly identical — the radius circles overlap heavily (Erlangen↔Nürnberg ≈ 15km), so ONE query with `wo=Nürnberg&umkreis=50` covers almost the entire target region; Erlangen-50km adds only the northern rim.

### 1.8 Facets (`facetten` in search response) — free analytics

Live facet families observed: `verguetung` (jahr/stunde), `befristung` (1/2/3), **`externestellenboersen`** (false/true counts), `behinderung`, `pav` (private Arbeitsvermittlung), `berufsfeld` (full counts, e.g. "IT-Netzwerktechnik, -Administration, -Organisation": 41, "Informatik": 194 for the Erlangen Systemintegration query), `topberuf` (e.g. "Fachinformatiker/in - Systemintegration": 229, "IT-Systemadministrator/in": 37). Facets are usable as a zero-cost market scanner.

### 1.9 Identifying private-board vs direct-employer postings

- Legacy `externBoersenId` field: **does not exist in v6** (grep: NOT FOUND).
- v6 way: (1) facet `externestellenboersen` true/false counts per query; (2) per-item boolean via presence of `externeURL` field (items carrying `externeURL` = mirrored from an external board); (3) `allianzpartner*` fields in detail response.
- Sample of observed `externeURL` targets: `studyflix.de`, `ausbildung.de`, `get-in-it.de`, `online-stellenmarkt.net`, `bewerbung.jobs`.
- Heuristic: `referenznummer` prefix (digits before first `-`): direct-BA postings cluster at `10000`/`10001` (70/100 in sample), external-board mirrors carry partner prefixes (16818, 11289, 14756, 13644, ...). Prefix alone is NOT a reliable discriminator (15 unique prefixes among internal items) — use `externeURL` presence instead.

### 1.10 Rate limits, blocking, ToS

- No documented numeric rate limit anywhere (spec, bund.dev, READMEs).
- Live stress: 12 back-to-back requests (1/sec) → all HTTP 200. Response header `X-API-BLOCKED: 0` present on every response (BA-side blocking flag; suggests a blocking mechanism exists).
- Community reports (bundesAPI/jobsuche-api issues #60/#61, cited in wunderfrucht/jobsuche README "Known API Quirks"): **sporadic 403 = rate limiting**; **404 on details = job expired** (postings disappear quickly); results always sorted oldest→newest, no sort parameter (Issue #43).
- BA Nutzungsbedingungen (https://www.arbeitsagentur.de/nutzungsbedingungen, fetched live, Änderungshistorie shows updates through 2026-07-08): prohibits "Robots, Webspider oder ähnliche Technologien" and using "bestehende Kommunikations- bzw. Programmierschnittstellen entgegen dem von der BA beabsichtigten Zweck ... zum Zweck der Datensammlung und -auswertung". Practical reading for the report: the API is the BA's *intended* interface for job-seeker apps (the key is published for exactly that), but bulk/wholesale harvesting for datasets or resale is off-limits. Recommend: poll every 30–60 min, cache by `referenznummer`, keep volumes modest, personal use.

---

## 2. Official documentation / developer portals

| Resource | URL | Status |
|---|---|---|
| Official OpenAPI/Swagger docs "Arbeitsagentur Jobsuche API" v2.1.0 | https://jobsuche.api.bund.dev/ (Swagger UI shell loading `openapi.yaml`) | ✅ live; spec downloaded (723 lines, `bunddev_openapi.yaml`). Docs-only host — the API itself lives on `rest.arbeitsagentur.de`. |
| OpenAPI YAML raw | https://jobsuche.api.bund.dev/openapi.yaml | ✅ 200, 23,428 bytes |
| `jobsuche.api.bundesanbieter.de` | — | ❌ DNS does not resolve (the name in the task brief appears to be a mis-remembering of `*.api.bund.dev` / `rest.arbeitsagentur.de`) |
| BA Nutzungsbedingungen (legal) | https://www.arbeitsagentur.de/nutzungsbedingungen | ✅ live |
| Production config proof (SPA) | https://www.arbeitsagentur.de/jobsuche/config/config.js | ✅ live — confirms `/pc/v6/jobs` + `/pc/v4/jobdetails` as current production API |
| bundAPI org (community-maintained OpenAPI spec hub, NOT official BA) | https://github.com/bundesAPI/jobsuche-api | ✅ active (pushed 2026-05-21) |

---

## 3. GitHub wrapper libraries (verified via GitHub API, 2026-10-11)

| Repo | Lang | ★ | Last push | Notes |
|---|---|---|---|---|
| bundesAPI/jobsuche-api | Python (OpenAPI hub) | 161 | 2026-05-21 | The reference community spec + README documenting clientId `jobboerse-jobsuche`, v6 flow, logo endpoint. |
| wunderfrucht/jobsuche | Rust (crate `jobsuche` 0.4) | 1 | 2026-06-19 | Modern, typed client, auto-pagination, documents API quirks (403 rate limit, 404 expiry, no sorting, base64 refnr). |
| long39ng/jobsuche | R | 1 | 2025-01-23 | R package client for the API. |
| kemdev/jobsuche-api-js | TypeScript | 0 | 2026-07-30 | Minimal JS fetch wrapper. |
| hansdoebel/n8n-nodes-jobsuche | TypeScript | 0 | 2026-05-04 | n8n community node — no-code pipeline option. |
| philippolis/jobsuche-agent | Python | 2 | 2026-03-13 | Fetches + filters postings (agent pattern, similar to Asha's use case). |
| jutt7/JobHunter | Python | 1 | 2026-10-11 (today) | Daily AI job-matching agent on the Arbeitsagentur API — proof the pipeline pattern is current. |
| vlzware/JobSuche-Py | Python | 0 | 2026-03-17 | LLM classification + incremental fetch. |
| a-Datana/Jobscraper | Python | 0 | 2024-08-21 | Scrapes the HTML SPA (older approach, superseded by API). |
| JonasPertschy/Arbeitsagentur2Mongo | Python | 1 | 2023-01-15 | Pulls API → MongoDB (reference ingestion pattern). |
| TrophySecure/arbeitsagentur-scraper | — | 0 | 2026-06-06 | Apify actor (paid scraping alternative). |
| pludoni/ba_upload | Ruby | 9 | 2026-07-24 | NOT a reader: uploads HR-BAXML to BA as an employer (opposite direction). |
| AndreasFischer1985/* family | Python/R | 1–14 | 2023–2026 | Sibling BA APIs: berufene­net-api, weiterbildungssuche-api, ausbildungssuche-api, bewerberboerse-api, entgeltatlas-api, studiensuche-api etc. — useful pointers to BA's other undocumented APIs. |
| fischerscode/AGArbeitsagentur | Dart | (GitHub API rate-limited during check, repo exists in search index) | — | Older Flutter/Dart client; maintenance status unverified this session. |
| rorar/EURES-API-Documentation | Shell/docs | 8 | 2026-04-08 | Reverse-engineered OpenAPI 3.1 spec for EURES (see §4.1). |

PyPI check: packages `jobsuche`, `arbeitsagentur`, `bundesagentur`, `jobsuche-api`, `ba-jobsuche`, `bundesagentur-jobs` → **all 404** (no maintained PyPI package; use raw `requests` or copy from bundesAPI/jobsuche-api).

---

## 4. Other official/semi-official channels

### 4.1 EURES — WORKING JSON API (verified live 2026-10-11) ✅

- No auth at all. Base: `https://europa.eu/eures/api` (community-documented at https://rorar.github.io/EURES-API-Documentation/, OpenAPI 3.1 spec `eures_openapi.yaml`, 70KB).
- `GET /jv-searchengine/public/statistics/getNumberOfJobs` → 200, `{"numberOfJobs": 2605904}`.
- `POST /jv-searchengine/public/jv-search/search` → 200 (105KB body). Request body: `{"resultsPerPage":10,"page":1,"sortSearch":"BEST_MATCH","keywords":[{"keyword":"Fachinformatiker Systemintegration","specificSearchCode":"EVERYWHERE"}],"publicationPeriod":null,"occupationUris":[],"skillUris":[],"requiredExperienceCodes":[],"positionScheduleCodes":[],"sectorCodes":[],"educationAndQualificationLevelCodes":[],"positionOfferingCodes":[],"locationCodes":[],"euresFlagCodes":[],"otherBenefitsCodes":[],"requiredLanguages":[]}` → `"numberRecords": 8499` for that keyword everywhere.
- Response: `numberRecords`, `jvs[]` (title, description, id, creationDate (epoch ms), euresFlag, jobCategoriesCodes, positionScheduleCodes, employer{}, locationMap, score...), `facets`.
- Detail: `GET /jv-searchengine/public/jv/id/{id}` → 200 (id, reference, source, jvProfiles...).
- Key insight: EURES vacancy `id` is base64 of a BA-style refnr (e.g. `MTEwODMtNDY2MzQ5My1TIDE` → `11083-4663493-S I1`) — EURES ingests BA postings, so it partially duplicates the BA API but adds cross-border/EU postings and full text in the search response (no detail call needed). Old endpoints tried and failed: `ec.europa.eu/eures/eures-searchengine/...` (403/404/405, Akamai-style block page "Sorry - 38245544"); the working host is `europa.eu/eures/api`.

### 4.2 Channels tested and declared DEAD or unusable

| Channel | Test | Result |
|---|---|---|
| BA Jobbörse RSS/XML (historical) | `www.arbeitsagentur.de/jobsuche/rss` | 302→200 but serves the HTML SPA (134KB), **not** RSS. `jobboerse.arbeitsagentur.de/vamHB/RSSFeed.xml` → 404. **RSS is dead.** |
| BA web "Schnellsuche" internal JSON | `www.arbeitsagentur.de/jobsuche/jobs`, `/jobsuche/api/jobs`, `/jobsuche/suche` | 302/301 redirects to SPA; SPA JS bundles (main + 7 chunks grepped) contain no other REST host — the SPA itself uses the same `rest.arbeitsagentur.de` API (proven by config.js). **No separate web JSON API worth scraping.** |
| BA open data / statistik portals | (documented) | statistik.arbeitsagentur.de publishes aggregate labour-market statistics only — no individual postings; no postings open-data download exists. |
| BA HR-BAXML | pludoni/ba_upload | Employer→BA upload channel (reverse direction), irrelevant for reading postings. |

---

## 5. Evidence files in /home/z/my-project/research/2-a/

- `test1_basic.json`, `test403_headers.txt` — 403 evidence for legacy endpoint
- `test_v6_erlangen.json` (5 items), `sample_full_v6.json` (100 items, full field inventory) — **primary sample responses**
- `detail_v4.json` — full job detail sample (ncsolution GmbH, FISI, Erlangen)
- `q_fisi_erlangen50.json`, `q_fisi_nuernberg50.json`, `q_itselek_*.json`, `q_sysint_de_all.json`, `q_fisi_de_all.json`, `q_sysint_erlangen50_*.json`, `q_itsupport_nuernberg50.json`, `q_itadmin_erlangen50.json`, `q_berufsfeld_erlangen.json` — count queries
- `bunddev_jobsuche.html`, `bunddev_openapi.yaml` — official docs
- `spa_config.js`, `spa_main.js`, `spa_chunk-*.js` — SPA production-API proof
- `tos_ba.html` — BA Nutzungsbedingungen
- `eures_search4.json`, `eures_detail.json`, `eures_openapi.yaml`, `eures_doc_readme.md` — EURES evidence
- `gh_search*.json`, `gh_eures.json`, READMEs of 4 wrapper repos — library research

## 6. Recommendations for the report (Asha pipeline)

1. **Primary source:** BA v6 API. Poll `was=Fachinformatiker Systemintegration&wo=Nürnberg&umkreis=50` (+ `angebotsart=1`) every 30–60 min with `veroeffentlichtseit=2` for incremental freshness, `size=100`, paginate via `maxErgebnisse`; dedupe on `referenznummer`; fetch `/pc/v4/jobdetails/{b64}` lazily for new postings only.
2. One Nürnberg-50km query ≈ covers Erlangen-50km (overlapping circles); optionally add Erlangen-50km for the north rim and a Germany-wide fallback query.
3. Broaden with `berufsfeld=Informatik` (478 vs 305 in Erlangen radius) and adjacent keywords (`IT-Support`, `IT-Administrator`, `IT-Systemelektroniker`).
4. Flag external-board mirrors via `externeURL` presence to know when a posting links out (and where it came from).
5. EURES as secondary (no key, richer search payload); skip RSS (dead), skip HTML scraping of the SPA (redirect walls, ToS).
6. Rate-limit posture: ~1 req/s, no parallel bursts, `X-API-BLOCKED` header watch, treat sporadic 403 as backoff signal.
