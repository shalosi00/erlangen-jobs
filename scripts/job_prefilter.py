#!/usr/bin/env python3
"""
job_prefilter.py — Negativ-Filterliste + Frische-Check (FAST, stdlib-only).

Wird VOR dem Schreiben einer Zeile in die CSV/Master ausgeführt
(von merge_erlangen.py importiert) und kann auch als CLI laufen.

Filter (Reihenfolge = First-match-wins, billigste zuerst):
  F1 ausbildung_student   Regex auf title:
      (?i)(Werkstudent|Praktik|Praktikant|Auszubildend|Azubi|Duales Studium|
           Masterarbeit|Bachelorarbeit|FOS|Schüler)
  F2 senior_management    Regex auf title:
      (?i)(Senior|Lead|Principal|Director|Head of|Leitung|Leiter|Partner|
           Manager|Vorarbeiter|Chef)
      AUSNAHMEN:
        a) "Junior" explizit VOR dem Treffer im Titel  -> behalten
        b) FP-Guard: Treffer steckt nur in Pflege-/Begleit-Komposita
           (Seniorenhaus, Schulbegleiter, Alltagsbegleiter, ...) -> behalten.
           Echte Management-Titel (Teamleitung, Projektleiter, Senior Engineer)
           werden weiterhin ausgeschlossen, weil das Kompositum nach dem
           Entfernen der FP-Wörter immer noch matchen muss.
  F3 fremdberuf           Regex auf title:
      (?i)(Arzt|Ärztin|Pflege|Steuerberater|Volkswirt|Jurist|Bauingenieur|
           Architekt|Kältetechniker|Dachdecker|Maler|Schlosser)
  F4 frische_check        date_posted darf nicht älter als --fresh-days
      (default 30) Tage sein. Fehlendes/unparsbares Datum -> Ausschluss
      (streng: "nur Stellen aufnehmen, deren date_posted nicht älter ...").

Nutzung als Modul:
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

# ------------------------------------------------------------------ Filter-Regeln
RE_AUSBILDUNG = re.compile(
    r"(?i)(Werkstudent|Praktik|Praktikant|Auszubildend|Azubi|Duales Studium|"
    r"Masterarbeit|Bachelorarbeit|FOS|Schüler)")

RE_MGMT = re.compile(
    r"(?i)(Senior|Lead|Principal|Director|Head of|Leitung|Leiter|Partner|"
    r"Manager|Vorarbeiter|Chef)")

RE_JUNIOR = re.compile(r"(?i)junior")

# Fehltreffer-Schutz für F2: Komposita, in denen Senior/Leiter/Leitung nur
# Bestandteil eines Pflege-/Begleit-/Betreuungs-Worts sind (keine Karriere-
# level-Bedeutung). Match zählt nur, wenn der Titel AUCH nach Entfernen
# dieser Wörter noch matcht.
RE_FP_COMPOUNDS = re.compile(
    r"(?i)(senioren\w*|schulbegleit\w*|\w*begleiter|\w*begleitung|"
    r"hauswirtschafter\w*|heimleitung?|aushilfs\w*|praktikumsbegleit\w*)")

RE_FREMDBERUF = re.compile(
    r"(?i)(Arzt|Ärztin|Pflege|Steuerberater|Volkswirt|Jurist|Bauingenieur|"
    r"Architekt|Kältetechniker|Dachdecker|Maler|Schlosser)")

RULES = [
    ("ausbildung_student", RE_AUSBILDUNG,
     "Ausbildung/Duales Studium/Praktikum/Werkstudent/Abschlussarbeit"),
    ("senior_management", RE_MGMT,
     "Senior-/Lead-/Principal-/Management-Position (Junior-Ausnahme + FP-Guard)"),
    ("fremdberuf", RE_FREMDBERUF,
     "Fremdberuf/Approbation (Medizin, Pflege, Recht, Bau, Handwerk)"),
]

# ------------------------------------------------------------------ Datums-Logik
def parse_date(val):
    """ISO date_posted parsen (YYYY-MM-DD[ HH:MM:SS]). None wenn unbrauchbar."""
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

# ------------------------------------------------------------------ Kernfilter
def mgmt_match(title, fp_guard=True):
    """F2 mit Junior-Ausnahme + FP-Guard. Gibt Treffer-Keyword oder None."""
    m = RE_MGMT.search(title)
    if not m:
        return None
    if RE_JUNIOR.search(title[:m.start()]):   # Junior explizit davor -> behalten
        return None
    if fp_guard and not RE_MGMT.search(RE_FP_COMPOUNDS.sub(" ", title)):
        return None                            # nur FP-Kompositum -> behalten
    return m.group(0)

def check_row(row, cutoff, fresh_days, fp_guard=True):
    """Liefert (ok, reason, detail). ok=True -> Zeile bleibt."""
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
        return False, "stale_date", f"date_posted={d} ({age}d alt, >{fresh_days}d)"
    return True, None, None

def prefilter_jobs(rows, today=None, fresh_days=30, fp_guard=True):
    """Filtert Job-Liste. Returns (kept, rejected, stats)."""
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
    # Junior-Ausnahme / FP-Guard Statistik (wie viele dadurch gerettet wurden)
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
    ap = argparse.ArgumentParser(description="Job Pre-Filter (Negativ-Liste + Frische-Check)")
    ap.add_argument("--input", required=True, help="Job-Liste als JSON")
    ap.add_argument("--prefix", default="erlangen_prefiltered")
    ap.add_argument("--fresh-days", type=int, default=30,
                    help="max. Alter von date_posted in Tagen (default 30)")
    ap.add_argument("--today", default=None, help=" Override heutiges Datum YYYY-MM-DD")
    ap.add_argument("--no-fp-guard", action="store_true",
                    help="F2 ohne Fehltreffer-Schutz (rohe Regex, strenger)")
    ap.add_argument("--save-rejected", action="store_true",
                    help="abgelehnte Zeilen als *_rejected.json mitschreiben")
    args = ap.parse_args()

    rows = json.load(open(args.input))
    today = date.fromisoformat(args.today) if args.today else date.today()
    fp_guard = not args.no_fp_guard
    print(f"loaded {len(rows)} rows from {os.path.basename(args.input)}")
    print(f"regeln: F1 ausbildung_student | F2 senior_management "
          f"(junior-ausnahme=an, fp-guard={'an' if fp_guard else 'aus'}) "
          f"| F3 fremdberuf | F4 frische <= {args.fresh_days}d "
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

    # ---------------- Report
    pct = lambda n: f"{n / max(1, stats['input']) * 100:.1f}%"
    rep = [f"# Job Pre-Filter — Report {ts}\n"]
    rep.append(f"**Input**: {os.path.basename(args.input)} ({stats['input']} rows)  ")
    rep.append(f"**Datum**: heute {stats['today']}, cutoff {stats['cutoff']} "
               f"({stats['fresh_days']} Tage Frische)  ")
    rep.append("**Reihenfolge**: F1 Ausbildung/Student -> F2 Senior/Mgmt -> "
               "F3 Fremdberuf -> F4 Frische (first-match-wins)\n")
    rep.append("## Ergebnis\n")
    rep.append("| | rows |")
    rep.append("|---|---|")
    rep.append(f"| **PASS (behalten)** | **{stats['kept']}** ({pct(stats['kept'])}) |")
    rep.append(f"| entfernt gesamt | {stats['rejected']} ({pct(stats['rejected'])}) |")
    rep.append(f"| Laufzeit | {dt:.2f}s |\n")
    rep.append("## Entfernt nach Regel\n")
    rep.append("| Regel | rows | Anteil am Input | Beschreibung |")
    rep.append("|---|---|---|---|")
    descs = {n: d for n, _rx, d in RULES}
    descs.update({"stale_date": "date_posted älter als Frische-Fenster",
                  "no_valid_date": "kein parsbares date_posted"})
    for reason, n in sorted(stats["by_rule"].items(), key=lambda x: -x[1]):
        rep.append(f"| {reason} | {n} | {pct(n)} | {descs.get(reason.replace('prefilter:', ''), '')} |")
    rep.append(f"\n*F2-Rettungen: {stats['kept_by_junior_exception']}x Junior-Ausnahme, "
               f"{stats['kept_by_fp_guard']}x FP-Guard (Senioren*/Begleiter-Komposita)*\n")
    rep.append("## Beispiele pro Regel\n")
    for reason, exs in stats["examples"].items():
        rep.append(f"**{reason}** ({stats['by_rule'][reason]} rows)")
        for e in exs[:5]:
            rep.append(f"- {e}")
        rep.append("")
    # Altersverteilung der behaltenen Jobs
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
        rep.append("## Frische der behaltenen Jobs\n")
        rep.append("| Alter | rows |")
        rep.append("|---|---|")
        for b, n in buckets.items():
            rep.append(f"| {b} | {n} |")
        oldest = max(ages)
        rep.append(f"\nÄltester behaltener Job: {oldest} Tage\n")
    open(out + "_report.md", "w").write("\n".join(rep))

    print(f"\n=== ERGEBNIS ===")
    print(f"PASS: {stats['kept']} ({pct(stats['kept'])}) | "
          f"entfernt: {stats['rejected']} ({pct(stats['rejected'])})")
    for reason, n in sorted(stats["by_rule"].items(), key=lambda x: -x[1]):
        print(f"   - {reason}: {n}")
    print(f"Laufzeit: {dt:.2f}s")
    print(f"Output: {out}.json/.csv/_report.md"
          + (" + _rejected.json" if args.save_rejected else ""))

if __name__ == "__main__":
    main()
