"""Persistent job memory — the pipeline's cross-run state.

Every `fetch` produces a snapshot; this module is the *memory*: it keeps one
row per unique posting ever seen, with first_seen / last_seen / times_seen.
That turns the daily pull from "a pile of CSVs" into answers to real questions:
  - what is NEW today vs yesterday?        (`python -m pipeline history new`)
  - has Asha seen this posting before?     (first_seen)
  - full-text search over everything seen  (`python -m pipeline history search ...`)

Storage: SQLite via sqlite-utils (file: data/jobs_history.db, zero service,
FTS5 full-text index with triggers). Primary key = dedupe key, so re-seen
postings update last_seen instead of duplicating.

F6: sqlite_utils is imported LAZILY — a wiped dependency must not take the
whole CLI down (fetch/sources/digest keep working without the memory).
"""
from __future__ import annotations
import json, os, sqlite3
from datetime import datetime, timezone

from pathlib import Path
from pipeline.core import Job, title_key, norm_txt, canon_url

BASE = str(Path(__file__).resolve().parent.parent)  # repo root (clone-safe)
DB_PATH = os.path.join(BASE, "data", "jobs_history.db")

SCHEMA = {
    "pk": str,              # dedupe key (title|company|city)
    "url_key": str,         # canonical URL, "" if none
    "title": str,
    "company": str,
    "city": str,
    "plz": str,             # F13
    "url": str,
    "source": str,
    "date_posted": str,
    "junior_signal": str,
    "ft_unknown": int,      # 0/1
    "is_remote": int,       # F13: 0/1
    "salary_min": float,    # F13
    "salary_max": float,    # F13
    "currency": str,        # F13
    "first_seen": str,      # ISO date
    "last_seen": str,       # ISO date
    "times_seen": int,
}

# columns added after the initial schema (F13) — created on demand for old DBs
LATE_COLUMNS = [("plz", "TEXT"), ("is_remote", "INTEGER"), ("salary_min", "REAL"),
                ("salary_max", "REAL"), ("currency", "TEXT")]


class MemoryUnavailable(RuntimeError):
    """Raised when sqlite_utils is missing — callers degrade gracefully."""


def _db():
    global Database
    if "Database" not in globals() or Database is None:
        try:
            from sqlite_utils import Database as _D   # F6: lazy import
        except ImportError:
            raise MemoryUnavailable(
                "sqlite-utils missing — job memory unavailable; "
                "fix: /home/z/.venv/bin/pip install -r requirements.txt")
        Database = _D
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = Database(DB_PATH)
    t = db["postings"]
    if not t.exists():
        t.create(SCHEMA, pk="pk")
        t.enable_fts(["title", "company", "city"], create_triggers=True)
    else:
        # F13: cheap alter for memories created before the schema extension
        have = set(t.columns_dict)
        for name, typ in LATE_COLUMNS:
            if name not in have:
                t.add_column(name, typ)
    # F13: index on url_key (the URL-fold branch scans on it every update)
    db.execute("CREATE INDEX IF NOT EXISTS idx_postings_url_key ON postings(url_key)")
    return db


def _record(j: Job, today: str) -> dict:
    return {
        "pk": (title_key(j.title)[:70] + "|" + norm_txt(j.company)[:40]
               + "|" + norm_txt(j.city)[:20]),
        "url_key": canon_url(j.url)[:200],
        "title": j.title,
        "company": j.company,
        "city": j.city,
        "plz": j.plz or "",
        "url": j.url,
        "source": j.source,
        "date_posted": j.date_posted or "",
        "junior_signal": j.junior_signal or "",
        "ft_unknown": 1 if j.ft_unknown else 0,
        "is_remote": 1 if j.is_remote else 0,
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "currency": j.currency or "",
        "first_seen": today,
        "last_seen": today,
        "times_seen": 1,
    }


def update(jobs: list[Job]) -> dict:
    """Upsert a batch of kept postings. Returns stats for the run summary."""
    db = _db()
    today = datetime.now(timezone.utc).date().isoformat()
    fresh = known = 0
    for j in jobs:
        rec = _record(j, today)
        old = list(db["postings"].rows_where("pk = ?", [rec["pk"]]))
        if old:
            o = old[0]
            db["postings"].update(rec["pk"], {
                "last_seen": today,
                "times_seen": (o["times_seen"] or 1) + 1,
                "url": rec["url"] or o["url"],
                "date_posted": rec["date_posted"] or o["date_posted"],
                "junior_signal": rec["junior_signal"] or o["junior_signal"],
                "ft_unknown": min(rec["ft_unknown"], o["ft_unknown"] or 0),
                # F13: fill gaps from the new row instead of freezing stale blanks
                "url_key": rec["url_key"] or o.get("url_key") or "",
                "company": rec["company"] or o.get("company") or "",
                "city": rec["city"] or o.get("city") or "",
                "plz": rec.get("plz") or o.get("plz") or "",
                "is_remote": max(rec["is_remote"], o.get("is_remote") or 0),
                "salary_min": rec["salary_min"] if rec["salary_min"] else o.get("salary_min"),
                "salary_max": rec["salary_max"] if rec["salary_max"] else o.get("salary_max"),
                "currency": rec["currency"] or o.get("currency") or "",
            })
            known += 1
        else:
            # URL collision: same posting re-titled across runs -> fold into
            # the older row instead of creating a second memory entry
            if rec["url_key"]:
                hit = list(db["postings"].rows_where("url_key = ? AND pk != ?",
                                                     [rec["url_key"], rec["pk"]]))
                if hit:
                    h = hit[0]
                    # F13: fold full provenance — multi-source memory used to
                    # lose the second source (+company/city) of re-titled posts
                    srcs = sorted({*(h.get("source") or "").split("+"),
                                   *rec["source"].split("+")} - {""})
                    db["postings"].update(h["pk"], {
                        "last_seen": today,
                        "times_seen": (h["times_seen"] or 1) + 1,
                        "title": rec["title"],  # newest title wins
                        "company": rec["company"] or h.get("company") or "",
                        "city": rec["city"] or h.get("city") or "",
                        "plz": rec.get("plz") or h.get("plz") or "",
                        "url": rec["url"] or h["url"],
                        "source": "+".join(srcs),
                        "date_posted": rec["date_posted"] or h.get("date_posted") or "",
                        "junior_signal": rec["junior_signal"] or h.get("junior_signal") or "",
                        "ft_unknown": min(rec["ft_unknown"], h.get("ft_unknown") or 0),
                        "is_remote": max(rec["is_remote"], h.get("is_remote") or 0),
                        "salary_min": rec["salary_min"] if rec["salary_min"] else h.get("salary_min"),
                        "salary_max": rec["salary_max"] if rec["salary_max"] else h.get("salary_max"),
                        "currency": rec["currency"] or h.get("currency") or "",
                    })
                    known += 1
                    continue
            db["postings"].insert(rec)
            fresh += 1
    return {"fresh": fresh, "known": known, "total": db["postings"].count}


def new_today(limit: int = 15) -> list[dict]:
    """Postings first seen today (the digest's headline section)."""
    today = datetime.now(timezone.utc).date().isoformat()
    return list(_db()["postings"].rows_where(
        "first_seen = ? ORDER BY date_posted DESC, pk LIMIT ?", [today, limit]))


def gone_today(limit: int = 10) -> list[dict]:
    """Postings seen before but NOT re-seen in the latest run (likely expired)."""
    today = datetime.now(timezone.utc).date().isoformat()
    return list(_db()["postings"].rows_where(
        "last_seen < ? ORDER BY last_seen DESC LIMIT ?", [today, limit]))


def search(q: str, limit: int = 20) -> list[dict]:
    """FTS full-text search (title, company, city)."""
    return list(_db()["postings"].search(q, limit=limit))


def stats() -> dict:
    db = _db()
    t = db["postings"]
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "total": t.count,
        "first_seen_ever": (list(t.rows_where("1=1 ORDER BY first_seen LIMIT 1")) or
                            [{}])[0].get("first_seen", ""),
        "seen_today": list(t.rows_where("last_seen = ?", [today], select="count(*) c"))[0]["c"],
        "db_bytes": os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0,
    }


# ------------------------------------------------------------------ CLI ----

def cmd_history(args) -> int:
    try:
        return _cmd_history(args)
    except MemoryUnavailable as e:      # F6: CLI stays alive, message actionable
        print(f"job memory unavailable: {e}", file=__import__('sys').stderr)
        return 1

def _cmd_history(args) -> int:
    if args.history_cmd == "update":
        src = args.infile or os.path.join(BASE, "download", "jobs_latest.json")
        rows = json.load(open(src, encoding="utf-8"))
        jobs = [Job(source=r["source"], title=r["title"], company=r["company"],
                    city=r.get("city") or "", url=r.get("url") or "",
                    date_posted=r.get("date_posted") or "",
                    junior_signal=r.get("junior_signal") or "",
                    ft_unknown=bool(r.get("ft_unknown"))) for r in rows]
        s = update(jobs)
        print(f"history updated from {src}")
        print(f"  fresh: {s['fresh']}  re-seen: {s['known']}  total in memory: {s['total']}")
        return 0
    if args.history_cmd == "new":
        rows = new_today(limit=50)
        print(f"new today: {len(rows)}")
        for r in rows:
            print(f"  {r['date_posted'] or '????-??-??'} | {r['title'][:52]:<52} | "
                  f"{r['company'][:24]:<24} | {r['city'][:14]} | {r['url'][:60]}")
        return 0
    if args.history_cmd == "gone":
        rows = gone_today()
        print(f"likely expired (not re-seen today): {len(rows)}")
        for r in rows:
            print(f"  last_seen={r['last_seen']} | {r['title'][:50]} | {r['company'][:24]}")
        return 0
    if args.history_cmd == "search":
        if not args.q:
            print("usage: pipeline history search <query>", file=__import__('sys').stderr)
            return 1
        rows = search(args.q)
        print(f"FTS '{args.q}': {len(rows)} hits")
        for r in rows:
            print(f"  {r['title'][:52]:<52} | {r['company'][:24]:<24} | {r['url'][:56]}")
        return 0
    if args.history_cmd == "stats":
        s = stats()
        print(f"job memory: {s['total']} postings (since {s['first_seen_ever']}), "
              f"re-seen today: {s['seen_today']}, {s['db_bytes']//1024} KB")
        return 0
    return 1
