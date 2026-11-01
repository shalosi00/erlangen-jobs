#!/usr/bin/env python3
"""split_final_5.py - split a date-sorted final CSV (incl. descriptions) into N parts.

Usage: python3 scripts/split_final_5.py [--src download/erlangen_jobs_final_20261018.csv] [--parts 5]
Writes: <src>_part{1..N}.{csv,json} next to the source (same directory).
Order preserved (date_posted desc). Stdlib-only, record-aware (handles embedded newlines).
"""
import csv, json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

OUT = _arg("--outdir", os.path.join(BASE, "download"))
SRC = _arg("--src", os.path.join(OUT, "erlangen_jobs_final_20261018.csv"))
PARTS = int(_arg("--parts", 5))

if not os.path.exists(SRC):
    sys.exit(f"source not found: {SRC}\nHint: run the pipeline first, or pass --src <csv>")

with open(SRC, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

n = len(rows)
size = (n + PARTS - 1) // PARTS
print(f"rows: {n} -> {PARTS} parts of ~{size}  (order preserved: date_posted desc)")

written = []
for i in range(PARTS):
    lo, hi = i * size, min((i + 1) * size, n)
    part = rows[lo:hi]
    if not part:
        continue
    csv_p = f"{OUT}/{os.path.splitext(os.path.basename(SRC))[0]}_part{i+1}_of_{PARTS}.csv"
    json_p = f"{OUT}/{os.path.splitext(os.path.basename(SRC))[0]}_part{i+1}_of_{PARTS}.json"
    with open(csv_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(part)
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(part, f, ensure_ascii=False)
    dates = [r.get("date_posted", "") for r in part if r.get("date_posted")]
    span = f"{max(dates)} .. {min(dates)}" if dates else "n/a"
    print(f"  part{i+1}: rows {lo}-{hi-1} ({hi-lo})  dates {span}")
    print(f"           -> {os.path.basename(csv_p)} ({os.path.getsize(csv_p)//1024}KB) + .json ({os.path.getsize(json_p)//1024}KB)")
    written.append(csv_p)

# integrity: re-read all parts, count records
total = 0
for p in written:
    with open(p, newline="", encoding="utf-8") as f:
        total += sum(1 for _ in csv.DictReader(f))
print(f"integrity: {total} == {n} -> {'OK' if total == n else 'MISMATCH!'}")
