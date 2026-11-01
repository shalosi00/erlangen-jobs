# EURES Job Search API Documentation

[![OpenAPI 3.1.0](https://img.shields.io/badge/OpenAPI-3.1.0-6BA539?logo=openapiinitiative&logoColor=white)](openapi.yaml)
[![Documentation](https://img.shields.io/badge/docs-live-003399?logo=githubpages&logoColor=white)](https://rorar.github.io/EURES-API-Documentation/)
[![Deploy Docs](https://github.com/rorar/EURES-API-Documentation/actions/workflows/deploy-docs.yml/badge.svg)](https://github.com/rorar/EURES-API-Documentation/actions/workflows/deploy-docs.yml)
[![Endpoints](https://img.shields.io/badge/endpoints-20-informational)](#endpoints)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

Reverse-engineered OpenAPI 3.1.0 specification for the [EURES](https://eures.europa.eu) (European Employment Services) Job Search API.

> **This is an unofficial, community-maintained documentation project.** It is not affiliated with or endorsed by the European Commission or the EURES network.

## Quick Links

| Resource | URL |
|----------|-----|
| Interactive docs | [rorar.github.io/EURES-API-Documentation](https://rorar.github.io/EURES-API-Documentation/) |
| OpenAPI spec | [`openapi.yaml`](openapi.yaml) |
| Raw download | [openapi.yaml (raw)](https://raw.githubusercontent.com/rorar/EURES-API-Documentation/main/openapi.yaml) |

## Base URL

```
https://europa.eu/eures/api
```

## Endpoints

The specification documents **20 endpoints** across **3 API services**:

### jv-searchengine — Job Search & Statistics

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/jv-searchengine/public/jv-search/search` | Search job vacancies with filters |
| `GET` | `/jv-searchengine/public/jv/id/{id}` | Get full vacancy detail by ID |
| `GET` | `/jv-searchengine/public/statistics/getNumberOfJobs` | Total active vacancy count |
| `GET` | `/jv-searchengine/public/statistics/getCountryStats` | Vacancies by country/region |
| `GET` | `/jv-searchengine/public/statistics/getSectorStats` | Vacancies by NACE sector |
| `GET` | `/jv-searchengine/public/statistics/getOccupationStats` | Vacancies by ESCO occupation |
| `GET` | `/jv-searchengine/public/properties` | Search engine configuration |
| `GET` | `/jv-searchengine/public/translation/enabled` | Translation feature status |
| `GET` | `/jv-searchengine/public/translation/languages` | Supported translation languages |

### shared-data-rest-api — Reference Data & ESCO

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/shared-data-rest-api/public/reference/languages` | Portal-supported languages (26) |
| `GET` | `/shared-data-rest-api/public/reference/isoLanguages` | All ISO 639-1 languages (185) |
| `GET` | `/shared-data-rest-api/public/reference/countries` | Covered countries (31) |
| `GET` | `/shared-data-rest-api/public/reference/nace` | NACE sector classifications |
| `GET` | `/shared-data-rest-api/public/esco/supportedLanguages` | ESCO-supported language codes |
| `POST` | `/shared-data-rest-api/public/esco/label/{lang}` | Resolve ESCO URIs to labels |
| `GET` | `/shared-data-rest-api/public/esco/occupation/tree` | Full ESCO/ISCO occupation hierarchy |
| `GET` | `/shared-data-rest-api/public/properties/public` | Portal configuration |
| `GET` | `/shared-data-rest-api/public/menu/{section}` | Navigation menu entries |

### autocomplete-repository-rest-api — Suggestions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/autocomplete-repository-rest-api/public/v2.0/occupations` | Occupation name autocomplete |

### Other

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/public/security/profile` | Current user profile (null when anonymous) |

## Quick Start

### Search for jobs

```bash
curl -X POST https://europa.eu/eures/api/jv-searchengine/public/jv-search/search \
  -H 'Content-Type: application/json' \
  -d '{
    "resultsPerPage": 5,
    "page": 1,
    "sortSearch": "MOST_RECENT",
    "keywords": [{"keyword": "software engineer", "specificSearchCode": "EVERYWHERE"}],
    "publicationPeriod": null,
    "occupationUris": [],
    "skillUris": [],
    "requiredExperienceCodes": [],
    "positionScheduleCodes": [],
    "sectorCodes": [],
    "educationAndQualificationLevelCodes": [],
    "positionOfferingCodes": [],
    "locationCodes": ["de"],
    "euresFlagCodes": [],
    "otherBenefitsCodes": [],
    "requiredLanguages": [],
    "minNumberPost": null,
    "sessionId": "my-session-1",
    "requestLanguage": "en"
  }'
```

### Advanced search with field-specific keywords

The `specificSearchCode` controls which fields a keyword matches against:

| Code | Searches in |
|------|-------------|
| `EVERYWHERE` | All fields |
| `TITLE` | Job title only |
| `DESCRIPTION` | Job description only |
| `EMPLOYER` | Employer name only |
| `LEGAL_ID` | Employer legal identifier |
| `JOB_VACANCY_ID` | Vacancy ID |

```bash
# Search for "Developer" in title AND "SAP" in employer name
curl -X POST https://europa.eu/eures/api/jv-searchengine/public/jv-search/search \
  -H 'Content-Type: application/json' \
  -d '{
    "resultsPerPage": 10,
    "page": 1,
    "sortSearch": "BEST_MATCH",
    "keywords": [
      {"keyword": "Developer", "specificSearchCode": "TITLE"},
      {"keyword": "SAP", "specificSearchCode": "EMPLOYER"}
    ],
    "occupationUris": [], "skillUris": [], "requiredExperienceCodes": [],
    "positionScheduleCodes": [], "sectorCodes": [],
    "educationAndQualificationLevelCodes": [], "positionOfferingCodes": [],
    "locationCodes": [], "euresFlagCodes": [], "otherBenefitsCodes": [],
    "requiredLanguages": [], "minNumberPost": null,
    "publicationPeriod": null, "sessionId": "my-session-2",
    "requestLanguage": "de"
  }'
```

### Get vacancy detail

```bash
# Use the base64-encoded ID from search results
curl https://europa.eu/eures/api/jv-searchengine/public/jv/id/MTAwMDEtMTAwMTEzOTMxMS1TIDE?requestLang=en
```

### Autocomplete occupations

```bash
curl 'https://europa.eu/eures/api/autocomplete-repository-rest-api/public/v2.0/occupations?language=en&keyword=Software&nbResults=10'
```

### Get labor market statistics

```bash
# Total job count
curl https://europa.eu/eures/api/jv-searchengine/public/statistics/getNumberOfJobs

# Jobs by country (with NUTS sub-regions)
curl https://europa.eu/eures/api/jv-searchengine/public/statistics/getCountryStats
```

## Classification Systems

The API uses several EU classification standards:

| System | Used for | Example |
|--------|----------|---------|
| [ESCO](https://esco.ec.europa.eu) | Occupations & skills | `http://data.europa.eu/esco/occupation/...` |
| [ISCO](https://www.ilo.org/public/english/bureau/stat/isco/) | Occupation groups | `http://data.europa.eu/esco/isco/C2511` |
| [NACE](https://ec.europa.eu/eurostat/web/nace) | Economic sectors | `a` through `u` (lowercase) |
| [NUTS](https://ec.europa.eu/eurostat/web/nuts) | Geographic regions | `de` (country), `de1` (region), `DE12B` (district) |
| [CEFR](https://www.coe.int/en/web/common-european-framework-reference-languages) | Language proficiency | `en(B2)`, `de(C1)` |
| [EQF](https://europa.eu/europass/en/europass-tools/european-qualifications-framework) | Education levels | `basic`, `bachelor`, `doctoral` |

### NUTS revision timeline

The EURES API uses [NUTS](https://ec.europa.eu/eurostat/web/nuts) (Nomenclature of Territorial Units for Statistics) codes for geographic regions in `locationCodes` filters and `locationMap` response fields. NUTS revisions follow a three-year cycle:

| Revision | Applicable period | Regions (NUTS 1 / 2 / 3) |
|----------|-------------------|---------------------------|
| NUTS 2021 | 2021–2023 | 92 / 242 / 1166 |
| **NUTS 2024** | **2024–2026 (current)** | **92 / 244 / 1165** |
| NUTS 2027 | 2027 onward | TBD |

**Current status (as of April 2026):**
- The EURES API currently uses **NUTS 2024** codes. No action is needed until the end of 2026.
- The [NUTS 2027 delegated regulation](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=PI_COM:Ares(2025)6622463) was published in 2025 and takes effect **1 January 2027**. It may change, split, or merge some region codes.
- Eurostat publishes [correspondence tables](https://ec.europa.eu/eurostat/web/nuts/correspondence-tables) for mapping between revisions (available via the [TERCET tool](https://gisco-services.ec.europa.eu/tercet/)).
- When the EURES portal transitions to NUTS 2027, consumers should expect location code changes in search filters, statistics, and vacancy detail responses.

### Eurostat SDMX API status

The EURES API itself does not use [SDMX](https://ec.europa.eu/eurostat/web/sdmx-infospace) directly, but Eurostat's SDMX APIs are relevant for consumers enriching EURES data with labor market statistics:

| API | Base URL | Status |
|-----|----------|--------|
| Statistics API (JSON-stat 2.0) | `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/` | Active |
| SDMX 2.1 | `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/` | Active |
| SDMX 3.0 | `https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/` | Active |
| Catalogue API | `https://ec.europa.eu/eurostat/api/dissemination/catalogue/` | Active |

**Current status (as of April 2026):**
- No deprecations announced. SDMX 2.1 and 3.0 are supported side-by-side with no sunset dates.
- The old bulk download facility was decommissioned in October 2023; the transition to the current dissemination API is complete.
- For new integrations, SDMX 3.0 is the forward-looking choice, but SDMX 2.1 remains fully supported.

## Development

### Generate documentation site locally

```bash
bash scripts/generate-docs.sh -o _site
# Open _site/index.html in a browser
```

### GitHub Pages deployment

The documentation site is built and deployed automatically via GitHub Actions when `openapi.yaml` or `scripts/generate-docs.sh` change on `main`. To enable:

1. Go to **Settings > Pages**
2. Set source to **GitHub Actions**

### Use with code generators

Generate API clients from the OpenAPI spec using tools like [openapi-generator](https://openapi-generator.tech):

```bash
# TypeScript client
npx @openapitools/openapi-generator-cli generate \
  -i openapi.yaml -g typescript-fetch -o ./client

# Python client
openapi-generator generate -i openapi.yaml -g python -o ./client
```

### Import into tools

The `openapi.yaml` file can be imported directly into:

- [Postman](https://www.postman.com) — Import > File > `openapi.yaml`
- [Insomnia](https://insomnia.rest) — Import/Export > From File
- [Swagger Editor](https://editor.swagger.io) — File > Import file
- [Bruno](https://www.usebruno.com) — Import Collection > OpenAPI

## Disclaimer

This documentation is provided "as-is" based on observed behavior of the public EURES portal API. It is **not an official API** and has no guaranteed stability, rate limits, or support.

Usage is subject to the [EURES portal terms of use](https://europa.eu/eures/portal/jv-se/home?lang=en&pageCode=find_a_job#openDisclaimerQualityDialog). It is your responsibility to ensure compliance with applicable laws and regulations.

Neither the maintainers of this project nor the EURES portal accept liability for damages or losses arising from use of this API or its documentation.

## License

[MIT](LICENSE)
