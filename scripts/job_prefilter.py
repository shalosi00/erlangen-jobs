#!/usr/bin/env python3
"""
job_prefilter.py — negative keyword list + freshness check (FAST, stdlib-only).

Runs BEFORE any row is written to the CSV/master
(imported by merge_erlangen.py) and can also run as a CLI.

Filters (order = first-match-wins, cheapest first):
  F1 ausbildung_student   regex on title:
      (?i)(Werkstudent|Praktik|Praktikant|Auszubildend|Azubi|Duales Studium|
           Masterarbeit|Bachelorarbeit|FOS|Schüler)
      (German training/internship/student terms — matched against German titles)
  F2 senior_management    regex on title:
      (?i)(Senior|Lead|Principal|Director|Head of|Leitung|Leiter|Partner|
           Manager|Vorarbeiter|Chef)
      EXCEPTIONS:
        a) "Junior" explicitly BEFORE the hit in the title -> keep
        b) FP-guard: the hit lives only inside care/companion compounds
           (Seniorenhaus, Schulbegleiter, Alltagsbegleiter, ...) -> keep.
           Real management titles (Teamleitung, Projektleiter, Senior Engineer)
           stay rejected because the title must still match AFTER the
           FP-guard words are stripped.
  F3 fremdberuf           regex on title:
      (?i)(Arzt|Ärztin|Pflege|Steuerberater|Volkswirt|Jurist|Bauingenieur|
           Architekt|Kältetechniker|Dachdecker|Maler|Schlosser)
      (foreign professions outside the IT training target)
  F4 freshness check      date_posted must not be older than --fresh-days
      (default 30) days. Missing/unparseable date -> reject
      (strict: "only keep postings whose date_posted is not older ...").

Module usage:
    from job_prefilter import prefilter_jobs
    kept, rejected, stats = prefilter_jobs(rows)

CLI:
    python3 scripts/job_prefilter.py --input download/erlangen_master_X.json
    python3 scripts/job_prefilter.py --input ... --fresh-days 30 --save-rejected

Outputs (download/):
    erlangen_prefiltered_<ts>.json/.csv + _report.md (+ _rejected.json)
"""
import csv, json, os, re, sys, time
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD = os.path.join(BASE, "download")

# ------------------------------------------------------------------ filter rules
RE_AUSBILDUNG = re.compile(
    r"(?i)(Werkstudent|Praktik|Praktikant|Auszubildend|Azubi|Duales Studium|"
    r"Masterarbeit|Bachelorarbeit|FOS|Schüler)")

RE_MGMT = re.compile(
    r"(?i)(Senior|Lead|Principal|Director|Head of|Leitung|Leiter|Partner|"
    r"Manager|Vorarbeiter|Chef)")

RE_JUNIOR = re.compile(r"(?i)junior")

# False-positive protection for F2: compounds where Senior/Leiter/Leitung are
# only part of a care/companion word (no career-level meaning). The match
# only counts if the title STILL matches after those words are stripped.
RE_FP_COMPOUNDS = re.compile(
    r"(?i)(senioren\w*|schulbegleit\w*|\w*begleiter|\w*begleitung|"
    r"hauswirtschafter\w*|heimleitung?|aushilfs\w*|praktikumsbegleit\w*)")

RE_FREMDBERUF = re.compile(
    r"(?i)(Arzt|Ärztin|Pflege|Steuerberater|Volkswirt|Jurist|Bauingenieur|"
    r"Architekt|Kältetechniker|Dachdecker|Maler|Schlosser)")

RULES = [
    ("ausbildung_student", RE_AUSBILDUNG,
     "training program / dual studies / internship / working student / thesis"),
    ("senior_management", RE_MGMT,
     "senior/lead/principal/management position (junior exception + FP-guard)"),
    ("fremdberuf", RE_FREMDBERUF,
     "foreign profession (medicine, nursing, law, construction, trades)"),
]

# ------------------------------------------------------------------ date logic
def parse_date(val):
    """Parse ISO date_posted (YYYY-MM-DD[ HH:MM:SS]); None when unusable."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("", "none", "null", "nan", "nat", "unknown"):
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None

# ------------------------------------------------------------------ core filter
def mgmt_match(title, fp_guard=True):
    """F2 with junior exception + FP-guard. Returns the hit keyword or None."""
    m = RE_MGMT.search(title)
    if not m:
        return None
    if RE_JUNIOR.search(title[:m.start()]):   # explicit junior before the hit -> keep
        return None
    if fp_guard and not RE_MGMT.search(RE_FP_COMPOUNDS.sub(" ", title)):
        return None                            # FP compound only -> keep
    return m.group(0)

def check_row(row, cutoff, fresh_days, fp_guard=True):
    """Returns (ok, reason, detail). ok=True -> row is kept."""
    title = str(row.get("title") or "")
    for name, rx, _desc in RULES:
        if name == "senior_management":
            hit = mgmt_match(title, fp_guard=fp_guard)
            if hit:
                return False, f"prefilter:{name}", f"keyword={hit!r}"
        elif rx.search(title):
            hit = rx.search(title).group(0)
            return False, f"prefilter:{name}", f"keyword={hit!r}"
    d = parse_date(row.get("date_posted"))
    if d is None:
        return False, "no_valid_date", f"date_posted={row.get('date_posted')!r}"
    age = (cutoff + timedelta(days=fresh_days) - d).days
    if age > fresh_days:
        return False, "stale_date", f"date_posted={d} ({age}d old, >{fresh_days}d)"
    return True, None, None

def prefilter_jobs(rows, today=None, fresh_days=30, fp_guard=True):
    """Filter a job list. Returns (kept, rejected, stats)."""
    today = today or date.today()
    cutoff = today - timedelta(days=fresh_days)
    kept, rejected = [], []
    stats = {
        "input": len(rows), "kept": 0, "rejected": 0,
        "by_rule": {}, "kept_by_junior_exception": 0, "kept_by_fp_guard": 0,
        "examples": {}, "today": str(today), "cutoff": str(cutoff),
        "fresh_days": fresh_days,
    }
    for r in rows:
        title = str(r.get("title") or "")
        ok, reason, detail = check_row(r, cutoff, fresh_days, fp_guard=fp_guard)
        if ok:
            kept.append(r)
            continue
        rej = dict(r)
        rej["reject_stage"] = "prefilter"
        rej["reject_reason"] = reason
        rej["reject_detail"] = detail
        rejected.append(rej)
        st = stats["by_rule"].setdefault(reason, 0)
        stats["by_rule"][reason] = st + 1
        ex = stats["examples"].setdefault(reason, [])
        if len(ex) < 8:
            ex.append(f"{title[:90]} [{detail}]")
    # Junior exception / FP-guard statistics (how many were rescued by each)
    for name, rx, _d in RULES:
        if name != "senior_management":
            continue
        for r in rows:
            t = str(r.get("title") or "")
            m = RE_MGMT.search(t)
            if not m:
                continue
            if RE_JUNIOR.search(t[:m.start()]):
                stats["kept_by_junior_exception"] += 1
            elif fp_guard and not RE_MGMT.search(RE_FP_COMPOUNDS.sub(" ", t)):
                stats["kept_by_fp_guard"] += 1
    stats["kept"] = len(kept)
    stats["rejected"] = len(rejected)
    return kept, rejected, stats

# ------------------------------------------------------------------ CLI
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Job pre-filter (negative list + freshness check)")
    ap.add_argument("--input", required=True, help="job list as JSON")
    ap.add_argument("--prefix", default="erlangen_prefiltered")
    ap.add_argument("--fresh-days", type=int, default=30,
                    help="max age of date_posted in days (default 30)")
    ap.add_argument("--today", default=None, help=" override today's date, YYYY-MM-DD")
    ap.add_argument("--no-fp-guard", action="store_true",
                    help="run F2 without the false-positive guard (raw regex, stricter)")
    ap.add_argument("--save-rejected", action="store_true",
                    help="also write rejected rows to *_rejected.json")
    args = ap.parse_args()

    rows = json.load(open(args.input))
    today = date.fromisoformat(args.today) if args.today else date.today()
    fp_guard = not args.no_fp_guard
    print(f"loaded {len(rows)} rows from {os.path.basename(args.input)}")
    print(f"rules: F1 ausbildung_student | F2 senior_management "
          f"(junior-exception=on, fp-guard={'on' if fp_guard else 'off'}) "
          f"| F3 fremdberuf | F4 freshness <= {args.fresh_days}d "
          f"(cutoff {today - timedelta(days=args.fresh_days)})")

    t0 = time.time()
    kept, rejected, stats = prefilter_jobs(
        rows, today=today, fresh_days=args.fresh_days, fp_guard=fp_guard)
    dt = time.time() - t0

    os.makedirs(DOWNLOAD, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M")
    out = os.path.join(DOWNLOAD, f"{args.prefix}_{ts}")
    json.dump(kept, open(out + ".json", "w"), default=str, ensure_ascii=False, indent=1)
    cols = ["title", "company", "location", "date_posted", "is_remote",
            "source_portal", "job_url", "job_url_direct"]
    with open(out + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for j in kept:
            w.writerow([j.get(c) for c in cols])
    if args.save_rejected:
        json.dump(rejected, open(out + "_rejected.json", "w"),
                  default=str, ensure_ascii=False, indent=1)

    # ---------------- report
    pct = lambda n: f"{n / max(1, stats['input']) * 100:.1f}%"
    rep = [f"# Job Pre-Filter — Report {ts}\n"]
    rep.append(f"**Input**: {os.path.basename(args.input)} ({stats['input']} rows)  ")
    rep.append(f"**Date**: today {stats['today']}, cutoff {stats['cutoff']} "
               f"({stats['fresh_days']} day freshness window)  ")
    rep.append("**Order**: F1 training/student -> F2 senior/mgmt -> "
               "F3 foreign profession -> F4 freshness (first-match-wins)\n")
    rep.append("## Result\n")
    rep.append("| | rows |")
    rep.append("|---|---|")
    rep.append(f"| **PASS (kept)** | **{stats['kept']}** ({pct(stats['kept'])}) |")
    rep.append(f"| removed total | {stats['rejected']} ({pct(stats['rejected'])}) |")
    rep.append(f"| runtime | {dt:.2f}s |\n")
    rep.append("## Removed by rule\n")
    rep.append("| Rule | rows | share of input | description |")
    rep.append("|---|---|---|---|")
    descs = {n: d for n, _rx, d in RULES}
    descs.update({"stale_date": "date_posted older than the freshness window",
                  "no_valid_date": "no parseable date_posted"})
    for reason, n in sorted(stats["by_rule"].items(), key=lambda x: -x[1]):
        rep.append(f"| {reason} | {n} | {pct(n)} | {descs.get(reason.replace('prefilter:', ''), '')} |")
    rep.append(f"\n*F2 rescues: {stats['kept_by_junior_exception']}x junior exception, "
               f"{stats['kept_by_fp_guard']}x FP-guard (care/companion compounds)*\n")
    rep.append("## Examples per rule\n")
    for reason, exs in stats["examples"].items():
        rep.append(f"**{reason}** ({stats['by_rule'][reason]} rows)")
        for e in exs[:5]:
            rep.append(f"- {e}")
        rep.append("")
    # age distribution of the kept jobs
    ages = {}
    for j in kept:
        d = parse_date(j.get("date_posted"))
        if d:
            ages[(today - d).days] = ages.get((today - d).days, 0) + 1
    if ages:
        buckets = {"0-7d": 0, "8-14d": 0, "15-21d": 0, "22-30d": 0}
        for a, n in ages.items():
            for lo, hi in ((0, 7), (8, 14), (15, 21), (22, 30)):
                if lo <= a <= hi:
                    buckets[f"{lo}-{hi}d"] += n
                    break
        rep.append("## Freshness of kept jobs\n")
        rep.append("| Age | rows |")
        rep.append("|---|---|")
        for b, n in buckets.items():
            rep.append(f"| {b} | {n} |")
        oldest = max(ages)
        rep.append(f"\nOldest kept posting: {oldest} days\n")
    open(out + "_report.md", "w").write("\n".join(rep))

    print(f"\n=== RESULT ===")
    print(f"PASS: {stats['kept']} ({pct(stats['kept'])}) | "
          f"removed: {stats['rejected']} ({pct(stats['rejected'])})")
    for reason, n in sorted(stats["by_rule"].items(), key=lambda x: -x[1]):
        print(f"   - {reason}: {n}")
    print(f"Runtime: {dt:.2f}s")
    print(f"Output: {out}.json/.csv/_report.md"
          + (" + _rejected.json" if args.save_rejected else ""))

if __name__ == "__main__":
    main()
