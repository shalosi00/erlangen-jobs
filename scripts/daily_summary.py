#!/usr/bin/env python3
"""Daily digest for Asha's FISI job search — the 'morning briefing'.

Answers the standing questions in one page:
  WHERE  — which portal every job came from (source breakdown)
  WHEN   — posting-date coverage: how many have real dates, how many are
           first-seen estimates, and which time-filter each source used
  WHAT   — new jobs seen today, entry-level verdicts (Task 22 classes)
  WHO    — direct employers (no mediators) with phone/email/website/URL

Usage:
  python3 scripts/daily_summary.py [--enrich <latest|path.json>] [--out DIR]
Writes download/daily/<date>/daily_summary_<date>.md and prints to stdout.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "jobs_history.db"
DL = ROOT / "download" / "daily"
ENRICH_DIR = ROOT / "data" / "enriched"

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def latest_enriched() -> Path | None:
    files = sorted(ENRICH_DIR.glob("jobs_enriched_*.json"))
    return files[-1] if files else None


def load_db_rows() -> list[dict]:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return [dict(r) for r in db.execute("SELECT * FROM postings")]


def fmt_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|")[:90]
                                     for c in r) + " |")
    return "\n".join(out)


def main() -> None:
    args = sys.argv[1:]
    enrich_path = None
    if "--enrich" in args:
        v = args[args.index("--enrich") + 1]
        enrich_path = latest_enriched() if v == "latest" else Path(v)
    else:
        enrich_path = latest_enriched()

    rows = load_db_rows()
    enr = {}
    if enrich_path and enrich_path.exists():
        for rec in json.loads(enrich_path.read_text()):
            enr[rec.get("url", "")] = rec

    new_today = [r for r in rows if (r.get("first_seen") or "")[:10] == TODAY]
    lines = [
        f"# Tägliches Job-Briefing — {TODAY}",
        f"_{len(rows)} Postings im Bestand, {len(new_today)} neu heute, "
        f"Anreicherung: {enrich_path.name if enrich_path else '—'}_\n",
    ]

    # WHERE
    where = {}
    for r in rows:
        where[r.get("source", "?")] = where.get(r.get("source", "?"), 0) + 1
    lines += ["## WHERE — Quellen-Verteilung (alle Portale)",
              fmt_table(["Portal", "Jobs", "Anteil"],
                        [[k, v, f"{100 * v / len(rows):.0f}%"]
                         for k, v in sorted(where.items(),
                                            key=lambda x: -x[1])]), ""]

    # WHEN — count from enrichment records (cover every row); DB fallback
    if enr:
        real, est, miss = 0, 0, 0
        ages = []
        for r in enr.values():
            ev = r.get("date_evidence", "")
            dp = (r.get("date_posted") or "")[:10]
            if "NOT FETCHED" in ev or r.get("fetch", "").startswith("dead"):
                miss += 1
                continue
            if "first_seen" in ev or "NO POSTING DATE" in ev:
                est += 1
                continue
            real += 1
            try:
                ages.append((datetime.now(timezone.utc).date()
                             - datetime.fromisoformat(dp).date()).days)
            except (ValueError, TypeError):
                pass
    else:
        real, est, miss = 0, 0, 0
        ages = []
        for r in rows:
            dp = (r.get("date_posted") or "")[:10]
            if dp:
                real += 1
                try:
                    ages.append((datetime.now(timezone.utc).date()
                                 - datetime.fromisoformat(dp).date()).days)
                except ValueError:
                    pass
            else:
                est += 1
    lines += ["## WHEN — Veröffentlichungsdaten",
              f"- **{real}** Jobs mit echtem Veröffentlichungsdatum "
              f"(BA-API / JSON-LD / Seiten-Datum)",
              f"- **{est}** Jobs ohne Datum auf der Seite → Stattdessen "
              f"first_seen + dokumentierter Suchfilter",
              f"- **{miss}** nicht mehr abrufbar (expired/bot-wall) — "
              f"Zeitfilter dokumentiert",
              f"- Ältestes Datum: **{max(ages) if ages else '—'} Tage**, "
              f"neuestes: **{min(ages) if ages else '—'} Tage**",
              "", "### Zeitfilter pro Quelle (Garantie-Bereich)",
              fmt_table(["Quelle", "Filter"],
                        sorted({(r.get('source', '?'),
                                 (r.get('time_filter_used', '')
                                  .split(';')[0] if r.get('time_filter_used')
                                  else '—'))
                                for r in enr.values()}) or
                        [["—", "noch nicht angereichert"]]), ""]

    # WHAT — new today + entry verdicts
    if new_today:
        lines += ["## NEU HEUTE",
                  fmt_table(["Titel", "Firma", "Quelle", "Einstieg (T22)"],
                            [[r.get("title", ""), r.get("company", ""),
                              r.get("source", ""),
                              enr.get(r.get("url"), {})
                              .get("experience_class_t22", "—")]
                             for r in new_today[:20]]), ""]
    else:
        lines += ["## NEU HEUTE", "_Keine neuen Jobs heute._", ""]

    # WHO — direct employers with contacts
    gold = [r for r in enr.values()
            if r.get("employer_type") == "direct"
            and (r.get("recruiter_phone") or r.get("recruiter_email"))]
    if gold:
        lines += ["## WHO — Direkt-Arbeitgeber mit Kontaktdaten (keine Zeitarbeit)",
                  fmt_table(["Arbeitgeber", "Titel", "Telefon", "E-Mail",
                             "Website", "Original"],
                            [[g.get("employer_direct", ""),
                              g.get("title", ""), g.get("recruiter_phone", ""),
                              g.get("recruiter_email", ""),
                              g.get("employer_website", "").replace("https://", ""),
                              g.get("original_url", "").replace("https://", "")]
                             for g in gold[:25]]), ""]
    med = sum(1 for r in enr.values() if r.get("employer_type") == "mediator")
    direct = sum(1 for r in enr.values() if r.get("employer_type") == "direct")
    unk = len(enr) - med - direct
    lines += ["## Kennzahlen",
              f"- Direkt: **{direct}** | Vermittler: **{med}** | "
              f"ungeklärt: **{unk}**",
              f"- Telefon gefunden: **{sum(1 for r in enr.values() if r.get('recruiter_phone'))}** "
              f"| E-Mail: **{sum(1 for r in enr.values() if r.get('recruiter_email'))}** "
              f"| Original-URL: **{sum(1 for r in enr.values() if r.get('original_url'))}** "
              f"| Website: **{sum(1 for r in enr.values() if r.get('employer_website'))}**"]

    text = "\n".join(lines) + "\n"
    out_dir = DL / TODAY
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"daily_summary_{TODAY}.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
