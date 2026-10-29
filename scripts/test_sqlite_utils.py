"""Smoke test 2: sqlite-utils — persistent job memory prototype.
Load jobs_latest.json -> upsert into data/jobs_history.db (pk = dedupe key)
-> simulate a SECOND run with 1 changed + 1 new row -> verify first_seen stays,
last_seen updates, and FTS search works."""
import json, os, sys
sys.path.insert(0, "/home/z/my-project")
from sqlite_utils import Database
from pipeline.core import title_key, norm_txt

DB_PATH = "/tmp/smoke_history.db"   # throwaway; production = data/jobs_history.db
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

rows = json.load(open("/home/z/my-project/download/jobs_latest.json", encoding="utf-8"))
print(f"input postings: {len(rows)}")

def to_record(r, day):
    return {
        "pk": (title_key(r["title"])[:70] + "|" + norm_txt(r["company"])[:40]
               + "|" + norm_txt(r.get("city") or "")[:20]),
        "title": r["title"], "company": r["company"], "city": r.get("city") or "",
        "url": r.get("url") or "", "source": r["source"],
        "date_posted": r.get("date_posted") or "",
        "first_seen": day, "last_seen": day, "times_seen": 1,
    }

db = Database(DB_PATH)
day1 = "2026-10-13"
records = [to_record(r, day1) for r in rows]
db["postings"].upsert_all(records, pk="pk")
db["postings"].enable_fts(["title", "company", "city"], create_triggers=True, replace=True)

# --- simulate run 2: same job re-seen + one brand-new
r2 = dict(records[0]); r2["last_seen"] = "2026-10-14"; r2["times_seen"] = 2
new = dict(records[1]); new["pk"] = "totally|new|job"; new["title"] = "IT-Supporter Neue Stelle"
new["last_seen"] = new["first_seen"] = "2026-10-14"
db["postings"].upsert_all([r2, new], pk="pk", alter=True)

n_total = db["postings"].count
new_today = list(db["postings"].rows_where("first_seen = ?", ["2026-10-14"]))
print(f"after run 2: total={n_total}, new-today={len(new_today)} -> {[r['title'] for r in new_today]}")
r0 = list(db["postings"].rows_where("pk = ?", [records[0]["pk"]]))[0]
print(f"re-seen row: first_seen={r0['first_seen']} last_seen={r0['last_seen']} times_seen={r0['times_seen']}")

# --- FTS search
hits = list(db["postings"].search("systemintegration"))
print(f"FTS 'systemintegration': {len(hits)} hits; top: {hits[0]['title'][:50] if hits else '-'}")
hits2 = list(db["postings"].search("supporter"))
print(f"FTS 'supporter': {len(hits2)} hits")

print("DB size:", os.path.getsize(DB_PATH), "bytes")
print("SQLITE-UTILS", "PASS" if (n_total == len(records) + 1 and new_today and hits) else "FAIL")
