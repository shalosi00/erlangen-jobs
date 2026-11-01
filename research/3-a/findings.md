# Research 3-a — Job-Search Methodology & Organizing Results into "Perfect Files"

Task 21 · 2026-10-15 · Raw evidence in `raw/` (10 web searches r1–r10, 3 full-page reads d1–d3).

Research question, verbatim from the tasking: *"Internet research knowledge on how to do job search and
organizing results for saving to make perfect files."* Two halves: (A) what proven methodology says a job
search should look like, (B) how to organize and save results so the files themselves are an asset.
Every claim below carries its source. Final section maps findings onto this repo (FISI toolkit).

---

## A. Job-search methodology (what the evidence says)

### A1. The funnel/pipeline model is the standard frame

- A job search funnel is "a structured system that tracks every stage of your search, from the moment you
  first discover a company to the moment you sign an offer" — modeled like a sales pipeline, many in at the
  top, best ones convert at the bottom (Cruit/askcruit, d1_funnel.json).
- Three macro-stages: **visibility** (getting in front of hiring managers) → **engagement** (turning interest
  into conversations) → **closing** (converting interviews into offers). The point of stage tracking: "knowing
  which stage is leaking lets you fix the right problem" (d1).
- Recruiting-side funnels mirror it: sourced → contacted → responded → screened → submitted → interviewed →
  offer → accepted; "keep the funnel simple but track conversion by stage" (r/recruiting, r2_funnel.json).
- Candidate-side stage vocabulary used by the popular trackers (Teal/Huntr): bookmarked/saved → applied →
  interview → offer → rejected/withdrawn (r10_tools.json cross-read).

### A2. The base rates (why tracking beats intuition)

| Metric | Value | Source |
|---|---|---|
| Applications per interview | ~32 applications → 4 interviews → 1 offer (2025 avg) | The Interview Guys, cited in d1 |
| Median time to first offer | 68.5 days (2025, grew vs prior years) | same |
| Resumes per posting | ~250 average | same |
| ATS filtering | 97.4% of Fortune 500 use an ATS; most applicants filtered before a human reads anything | Select Software Reviews 2025, cited in d1 |
| Applications to land a job (market consensus) | 100–200 not unusual | eztrackr, d2 |
| Germany, junior IT, real log | 11 months, 12.5 applications/month (~40–60 min each), 5 interviews (7.1%), 3 of 5 killed at HR stage | r/Germany_Jobs case study, r7 |
| Germany overall | 3–6 months is NORMAL; quality-centric German application takes 3–5 h each (tailoring expected) | niv-now.com + germanycareercoach.com, r7 |

Takeaway: the funnel is long, slow, and mostly silent. Without a tracker the searcher cannot even compute
their own conversion rates — and conversion *by stage* is exactly what tells you whether to fix the resume
(top of funnel) or the interview performance (bottom).

### A3. Timing: freshness is a measurable edge

- **41% of all applications arrive within the first 48 h of a posting; 56% within 96 h** (St. Louis Fed
  analysis of application timing, r6_timing.json). Everyone competes in the same fresh window.
- Claims of an edge inside the window: "apply within 48 h → 4–5× more likely to receive an interview request"
  (LinkedIn/injobalerts), "30% higher response rate in first 48 h" (resumerefiner), "within 24 h → +32%
  callback chance" (geckohospitality). Effect sizes are vendor-grade, direction is consistent across 5 sources.
- Day-of-week: **Tue–Thu mornings 8–11 AM show ~30% higher response** (metaintro 2026); multiple sources
  agree mid-week beats Friday/weekend (r6, r9).
- Direct mapping to this repo: our 14-day pull window and daily cadence are correct but the *sorting* should
  surface freshness (new-since-yesterday) first — see B4.

### A4. Follow-up cadence (consensus numbers)

- Application follow-up: **wait ~1 week (5–7 business days), then one polite follow-up**; 10–14 days still
  acceptable; mid-week best (Indeed r9; LinkedIn/erinkennedy; frontlinesourcegroup; joinhandshake all converge).
- After interview: thank-you within 24 h; checking-in note after ~1 week; second follow-up a few days later
  (TheMuse, r9).
- The tracker is what makes follow-up executable: "who to follow up with" and "date" are the two columns
  Reddit users call out as the ones that changed their search (r1, r10).

### A5. Quality-over-quantity + the weekly review loop

- 2025–2026 consensus: mass-applying is "a lottery ticket"; tailored applications + talking to a human before
  applying beat volume (d1 Focus Rule; Forbes r8 "quality over quantity wins"). Counterweight: in Germany the
  volume expectation is real too (100–200 total), so the working answer is **qualified volume**: filter hard
  (our pipeline does), tailor the shortlist.
- The operational loop that closes the system: **weekly review — export tracker data every Friday, look at
  conversion by stage and by source, adjust keywords/targets accordingly** (resumly r8; LinkedIn r8 "review
  your data each week to spot trends, shift effort toward strategies that lead to more interviews").
- Source attribution matters: "which job boards are actually sending you quality leads" is one of the
  standard insights a tracker unlocks (d2). Our pipeline already tags every row with source — keep it.

---

## B. Organizing results into "perfect files"

### B1. File naming convention (authoritative: CESSDA/UK Data Service, d3_naming.json)

- A file name is the *principal identifier*: it must carry content clues, status/version, and allow sorting.
- Best-practice elements: **date in YYYY-MM-DD** (sorts correctly), version, creator, description of content.
- Rules: meaningful but brief; avoid spaces, dots, special characters (`& ? !`); **separate elements with
  hyphens or underscores**; avoid very long names; 3-letter extension reserved for the format.
- Example pattern from the guide: `FG1_CONS_2010-02-12.rtf` = what/who/when.
- Folder-vs-names: "folder structures are the stronger and more foolproof method of organizing files; naming
  conventions require more effort to maintain" (U. Washington records management, r4). ⇒ Use folders for the
  big partition (by date, by kind), names for order inside.

### B2. Tracker file design (what the columns should be)

Aggregated from eztrackr (d2), beamjobs (r1), Indeed (r1/r5), resumly (r1), Reddit templates (r1/r5):

| Column group | Columns | Why |
|---|---|---|
| Identity | id, company, role, location, url | "Did I already apply here?" — dedupe |
| Provenance | source, first_seen/posted date | source-attribution analytics (B5); freshness |
| **Status (the MVP column)** | discovered → shortlisted → applied → interviewing → offer → closed | one glance command center; funnel stage (A1) |
| Dates | applied_date, followup_due, next_action | makes the A4 cadence executable |
| People | contact name/role | follow-ups, referrals |
| Materials | resume_version, notes | A/B of resume versions (d2 pattern insight) |
| Fit | fit_score/priority | qualified-volume filter (A5) |

Key design points from the sources: the **Status column is the MVP** ("your command center", eztrackr);
keep it *one row per posting* and *never edit history* (append-only status changes with dates — that is what
turns the file into funnel data); a spreadsheet beats a SaaS tool for **portability and longevity** (CSV/XLSX
outlive any subscription; r10 comparison pieces all make the portability point).

### B3. Folder layout for saved results (synthesis of r4 + this repo's reality)

- Partition by **date** at the top (a search is a time series; B1 dates + date folders sort identically),
  by **kind** at the second level (daily runs vs reports vs the tracker itself).
- **Stable pointers for "current"** (`latest/` with fixed names that get overwritten) so humans and scripts
  never chase timestamps; **immutable dated archive** for history; nothing duplicated by hand.
- Every folder gets a README that states the layout — the file equivalent of a runbook (Harvard DMP guide r4:
  documentation is part of the structure, not an afterthought).
- Idempotent tooling: an organizer script re-runnable any time; moving files by hand is the error source
  (r4: conventions "require effort to maintain" — so automate the maintenance).

### B4. What the German/junior case adds

- The Reddit Germany_Jobs log (11 months, monthly counts, per-stage rejections) is precisely the artifact a
  "perfect file" system should make easy to produce: stage dates per application, monthly rollups.
- German tailoring expectation (3–5 h/application when done properly, r7) ⇒ the tracker's `fit_score`/
  `priority` columns carry real weight: tailoring effort is the budget, so it must be spent on shortlisted
  rows only. Pipeline filters hard first (fulltime, no Ausbildung, ≤50 km direct-train) so the human budget
  goes to ~5–10 rows/week, not 100.
- German market norm 3–6 months ⇒ the file system must assume *months* of accumulation: append-only,
  dated, backed up (our git-bundle regime already does this).

### B5. Metrics the files should enable (dashboard spec for the tracker)

From r8 + d2: applications/week, stage conversion (applied→interview, interview→offer), median
days-in-stage, source yield (rows in vs shortlisted per source), follow-ups kept vs overdue. The tracker
XLSX ships a Metrics sheet with formulas over the Tracker sheet so the Friday review (A5) is zero-effort.

---

## C. Gap analysis: what this repo already does vs what the research says

| Research recommendation | Toolkit status today | Action taken in Task 21 |
|---|---|---|
| Track every stage, compute conversion (A1/A2) | job memory tracks *postings seen* (51), not *application funnel* | `download/tracker/` XLSX+CSV tracker with status funnel, pre-seeded from memory |
| Apply inside the 48 h window (A3) | daily cadence ✔ but freshness not surfaced in output files | archiver keeps `latest/` + dated dirs; digest already flags new-since-yesterday |
| Follow-up at 5–7 business days (A4) | nothing | `followup_due` column pre-computed on rows once marked `applied` |
| Weekly Friday review (A5) | nothing scheduled | Metrics sheet + documented Friday checklist in the report |
| YYYY-MM-DD names, no spaces/special chars (B1) | already: `jobs_..._YYYYMMDD-HHMM.csv` ✔ (hyphens) | kept as the canonical convention, documented in README |
| Folders by date/kind + stable pointers (B3) | **gap**: 35 timestamped files flat in `download/`, 1-line README | `download/{daily/YYYY-MM-DD,latest,reports,tracker}` + `scripts/organize_downloads.py` (idempotent) |
| README documenting the layout (B3) | **gap** | full `download/README.md` rewrite |
| Source attribution for yield analytics (B5) | already: `source` column everywhere ✔ | flows into tracker via seed |
| Long-horizon durability (B4) | git bundles v1–v8 ✔ | unchanged; tracker is CSV/XLSX = future-proof formats |

## D. Sources (all in `raw/`)

- d1: askcruit.com — "The Job Search Funnel: A Numbers Game You Can Win" (2026-03) — funnel stages, base rates (Interview Guys 2025, Select Software Reviews 2025).
- d2: eztrackr.app — "Build a Job Search Tracking Spreadsheet" (2025-07) — column design, status-as-MVP, pattern insights.
- d3: CESSDA Data Management Expert Guide / UK Data Service — file naming best practice (YYYY-MM-DD, hyphens, no spaces).
- r1: beamjobs, Indeed, resumly, Reddit r/jobs — tracker column lists.
- r2: askcruit, smartjobhunt, r/recruiting, firsthr — funnel stage vocabularies.
- r4: U. Washington, Harvard DMP, CESSDA, Oregon State Archives — naming/folder conventions.
- r6: St. Louis Fed (2017-11), metaintro, resumerefiner, usesprout — application-timing stats.
- r7: r/Germany_Jobs (11-month IT log), germanycareercoach, niv-now, studyinde — Germany junior reality.
- r8: resumly, LinkedIn — weekly review loop, data-driven search.
- r9: Indeed, TheMuse, joinhandshake, frontlinesourcegroup — follow-up cadence.
- r10: usesprout, prentus, huntr vs teal comparisons — tracker tool landscape, portability argument.
