# download/ — Deliverables Layout ("perfect files" standard, Task 21)

Organized per research/3-a (CESSDA/UK-Data-Service naming rules: YYYY-MM-DD dates,
hyphen-separated elements, folders over name-only conventions). Maintained by
`scripts/organize_downloads.py` (idempotent — run any time, wired into `daily_jobpull.sh`).

## Layout

```
download/
├── README.md              ← this runbook (never moved)
├── jobs_latest.csv        ← STABLE POINTERS written fresh by every pipeline run
├── jobs_latest.json         (these two files are what humans/scripts read for "current")
├── daily/YYYY-MM-DD/      ← immutable run artifacts, one dir per pull day
│   └── jobs_<query>_<YYYYMMDD-HHMM>.csv / .json / _rejected.csv
├── reports/               ← PDF reports, XLSX workbooks, cover sources
├── tracker/               ← application tracker (the funnel file — see below)
└── archive/               ← legacy one-off exports (kept for history)
```

## Conventions

1. **Names carry dates**: every generated file embeds `YYYYMMDD-HHMM`; date dirs use
   `YYYY-MM-DD` so lexicographic sort = chronological sort, everywhere.
2. **No spaces, no special characters** in generated names — hyphens and underscores only.
3. **Root stays minimal**: two stable pointers (`jobs_latest.*`) + this README. Everything
   else is partitioned by kind; nothing at root is ever edited in place.
4. **Daily dirs are immutable history** — corrected re-runs land as new timestamped
   files next to the originals; never overwrite.
5. **The tracker is the single source of truth for the application funnel** (statuses:
   discovered → shortlisted → applied → interviewing → offer / closed). Daily CSVs are
   *inputs* to the tracker, not a replacement for it.

## Friday review (10 minutes, per research/3-a A5)

1. Open `tracker/application_tracker_*.xlsx` → Metrics sheet: stage conversion,
   follow-ups overdue, source yield.
2. Any row `applied` with `followup_due` older than today → send the follow-up, log it.
3. Shortlist from the week's new rows (`discovered` → `shortlisted` or `closed`).
4. Update statuses; the funnel numbers only mean something if the file is current.

## Recovery

If the sandbox wipes this tree: `git checkout` restores tracked files; the daily CSVs
are re-derivable from `data/jobs_history.db` (job memory); the tracker must be treated
as precious — it is committed to git on every change (same rule as the escrow).
