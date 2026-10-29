# Programmatic Job Hunting — Germany (FISI Edition)

Toolkit + research for finding a first IT job (Fachinformatiker Systemintegration & adjacent
junior IT roles) around **Erlangen / Bavaria** using official APIs, ATS feeds and
low-risk scraping — built around the "apply within 72 h" advantage.

## Contents

| Path | What it is |
|------|------------|
| `download/Programmatic_Job_Hunting_Germany_Systemintegration.pdf` | 30-page deep-dive report: data sources, legal risk matrix (green/yellow/red), 4-layer pipeline architecture, 14-day action plan |
| `download/cover_source.html` | Editable cover source for the report |
| `research/2-a` | Bundesagentur für Arbeit Jobsuche v6 API live validation + EURES API + community clients |
| `research/2-b` | XING SSR / LinkedIn guest endpoints feasibility |
| `research/2-c` | Aggregator APIs (Arbeitnow, Adzuna, Careerjet, Jooble) |
| `research/2-d` | ATS direct feeds (Workday, SmartRecruiters, Personio, feed.xml) + Erlangen employer map |
| `research/2-e` | Train-commute analysis (VGN GTFS → 29 zero-transfer towns ≤60 min) |
| `research/2-f` | Legal (§87b UrhG, BGH precedent), market stats, keyword corpus |
| `research/github-repos/` | Survey of open-source GitHub repos for programmatic job search |
| `research/aggregators-round2/` | Round-2: 24 German aggregator boards probed (kimeta & co) — 5 live-working recipes, 11 bypass recipes, probe evidence |
| `scrapers/` | Working scrapers: `aggregator_search.py` = unified 5-board search → date-sorted CSV |
| `scripts/` | Report build + pipeline blueprints + probe scripts |
| `BACKUPS.md` | Where everything is mirrored (gofile, surge.sh) + restore instructions |

## Key validated sources

- **BA Jobsuche API v6** — `rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs`, key `jobboerse-jobsuche` (238 FISI jobs ≤50 km Erlangen)
- **EURES** (no auth, 8.5k DE listings), **Arbeitnow** (no key), **Adzuna/Jooble** (free keys)
- **ATS direct feeds** beat portals: DATEV, Schaeffler, GfK, adidas, PUMA, Hetzner …
- **Round-2 aggregators, working today with plain requests:** Connecticum, Get-in-IT,
  Berufsstart.de, Jobs.InFranken.de (local Franconia!), Talent.com DE → `scrapers/aggregator_search.py`
- **Blocked from DC, recipes documented:** Kimeta (residential proxy), Jobvector/Gigajob/
  Yourfirm/Stellenanzeigen.de (FlareSolverr), Absolventa (Playwright, params reverse-engineered),
  Careerjet (free API key, run from home IP)

## Quick start

```bash
# unified 5-aggregator search, date-sorted CSV
python3 scrapers/aggregator_search.py "Fachinformatiker"
# any keyword works
python3 scrapers/aggregator_search.py "IT-Support"
```

## Status

- [x] Phase 1: source discovery + live validation (research/2-a…2-f)
- [x] Phase 2: PDF report
- [x] Phase 3: GitHub open-source ecosystem survey (`research/github-repos/findings.md` — 87 repos surveyed, 11 deep-tested; adopt: python-jobspy, ats-scrapers, jutt7/JobHunter)
- [x] Phase 4: aggregator round-2 (kimeta & co — `research/aggregators-round2/findings.md`, 16 entries, live demo CSV) + external backup layer (gofile + surge.sh)
- [ ] Phase 5: full pipeline (BA v6 + aggregators + ATS feeds → daily cron → scoring)

## Legal note

Research distinguishes GREEN (official APIs/feeds, attribution), YELLOW
(logged-out portal reads at low volume) and RED (blocked portals — use native
email alerts instead). No credential-based automation against portals whose
ToS forbid it. See report ch. 9.
