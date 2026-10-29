#!/usr/bin/env python3
"""organize_downloads.py — keep download/ in the documented 'perfect files' layout.

Task 21 (research/3-a): folder partitions beat name-only conventions (UW records
management) and file names carry YYYY-MM-DD dates (CESSDA/UK Data Service).

Layout produced (see download/README.md):

    download/
    ├── README.md              this layout's runbook (root, never moved)
    ├── jobs_latest.csv/.json  stable pointers written by the pipeline (root, never moved)
    ├── daily/YYYY-MM-DD/      immutable run artifacts (jobs_*_<ts>[_rejected].csv/json)
    ├── reports/               PDFs, XLSX workbooks, cover sources
    ├── tracker/               application tracker (the funnel file)
    └── archive/               legacy one-off exports

Rules:
- Idempotent: re-running never duplicates or re-moves anything.
- Never overwrites: a conflicting destination aborts that one move, reported at exit.
- --dry-run prints the plan; --quiet for cron.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path("/home/z/my-project/download")

# jobs_fachinformatiker-systemintegration-erlangen-50km-14d_20261014-1505[_rejected].ext
RUNFILE_RX = re.compile(
    r"^jobs_.+_(?P<ts>\d{8}-\d{4})(?P<sfx>_rejected)?\.(?P<ext>csv|json)$"
)
REPORT_SUFFIXES = (".pdf", ".xlsx")
REPORT_PAT = re.compile(r"(cover.*\.html|.*_cover\.html)$", re.I)
LEGACY = {"aggregator_multi_source_FISI_erlangen.csv", "fisi_junior_erlangen50km_last14d.csv"}
KEEP_IN_ROOT = {"README.md", "jobs_latest.csv", "jobs_latest.json"}


def classify(name: str) -> tuple[str, str | None]:
    """Return (bucket, subdir_name_or_None) for a root-level file name."""
    if name in KEEP_IN_ROOT:
        return "keep", None
    m = RUNFILE_RX.match(name)
    if m:
        ts = m.group("ts")
        return "daily", f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"
    if REPORT_PAT.match(name) or name.lower().endswith(REPORT_SUFFIXES):
        return "reports", None
    if name in LEGACY:
        return "archive", None
    return "unknown", None


def main() -> int:
    dry = "--dry-run" in sys.argv
    quiet = "--quiet" in sys.argv
    if not ROOT.is_dir():
        print(f"missing: {ROOT}")
        return 1

    moves: list[tuple[Path, Path]] = []
    unknown: list[str] = []
    for f in sorted(ROOT.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        bucket, sub = classify(f.name)
        if bucket == "keep":
            continue
        dest_dir = ROOT / bucket if sub is None else ROOT / bucket / sub
        if bucket == "unknown":
            unknown.append(f.name)
            continue
        moves.append((f, dest_dir / f.name))

    if unknown and not quiet:
        print(f"UNCLASSIFIED (left in place, review manually): {unknown}")

    moved = 0
    for src, dst in moves:
        if dry:
            print(f"DRY {src.name} -> {dst.relative_to(ROOT)}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if not quiet:
                print(f"SKIP (exists) {dst.relative_to(ROOT)}")
            continue
        shutil.move(str(src), str(dst))
        moved += 1

    if not quiet:
        print(f"organized: {moved} moved, {len(unknown)} unclassified"
              + (" (dry-run)" if dry else ""))
    return 0 if not unknown else 2


if __name__ == "__main__":
    sys.exit(main())
