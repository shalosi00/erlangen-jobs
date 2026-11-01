# Mega Sweep - insanely large job search, junior-filtered (20261030)

## Funnel
| Stage | n |
|---|---|
| Raw rows fetched (BA bulk + portals + daily) | 4907 |
| **Master unique postings** | **3788** |
| FISI-relevant titles | 470 |
| Junior strong (title-level) | 43 |
| Junior medium (description-level) | 566 |
| Junior weak (vague 'Einstieg') | 23 |
| Excluded (senior/ausbildung/praktikum/manager) | 688 |
| **Junior shortlist (relevant AND strong/medium)** | **78** |

## Sources (master)
- BA: 3025
- Arbeitnow: 300
- EURES: 174
- WWR: 56
- Jobicy: 50
- Get-in-IT: 39
- Stellenanzeigen.de: 36
- InFranken: 25
- Connecticum: 21
- Himalayas: 20
- XING: 13
- Remotive: 12
- Kimeta: 10
- LinkedIn: 4
- Talent.com+XING: 1
- Talent.com: 1
- Indeed: 1

## Junior shortlist by source
- BA: 76
- EURES: 2

## Freshness (master; BA date_posted = FIRST publication)
- 90d+ (long-running, live): 1194
- 0-30d: 1173
- unknown: 744
- 31-90d: 677

NOTE: postings with first publication >90 days ago are still live (BA's 90-day
filter applies to the current publication period, employers keep the same
reference number running). Long-running junior postings usually mean the
employer is genuinely struggling to fill them - prime targets.

## Files
- master_ALL_20261030-1638.csv / .json - every unique posting with junior_class + relevant flags
- junior_shortlist_20261030-1638.csv - 78 rows, ranked (strong first, newest first)

## Method
- BA Jobsuche v6 bulk: 14 IT queries x 2 geo-tiers (Erlangen 50 km,
  Nuernberg 100 km), veroeffentlichtseit=90 days, angebotsart=1 (no Ausbildung),
  pav=false (no agencies), 100/page until exhaustion.
- BA v4 jobdetails deep-fetch for every non-excluded candidate (description-level
  entry signals).
- Wide portal run via pipeline fetch (30-day window, Nuernberg 100 km, 20 sources).
- Dedupe: canonical URL + fuzzy (title/company/city). Classification: the proven
  pull_fisi_junior regexes + description signal scan.
