"""Smoke test 3: rapidfuzz vs current _jac (token Jaccard) on real titles.
Question: does rapidfuzz catch near-dupes our Jaccard misses, WITHOUT false merges?
Baseline = what dedupe() already merged today (so a match on an already-merged pair
is expected; interesting = pairs Jaccard misses but rapidfuzz catches)."""
import csv, sys
sys.path.insert(0, "/home/z/my-project")
from pipeline.core import title_key, _jac, norm_txt
from rapidfuzz import fuzz

rows = list(csv.DictReader(open("/home/z/my-project/download/jobs_latest.csv", encoding="utf-8-sig")))
titles = [(r["title"], r["company"], r["city"]) for r in rows]
print(f"production rows: {len(titles)}")

keys = [title_key(t[0]) for t in titles]

def company_overlap(a, b):
    ta = set(norm_txt(a).split()); tb = set(norm_txt(b).split())
    return bool(ta & tb)

jac_pairs, rf_pairs = [], []
for i in range(len(titles)):
    for j in range(i + 1, len(titles)):
        if norm_txt(titles[i][2]) != norm_txt(titles[j][2]):  # same city only
            continue
        if not company_overlap(titles[i][1], titles[j][1]):
            continue
        if _jac(keys[i], keys[j]) >= 0.6:
            jac_pairs.append((i, j, _jac(keys[i], keys[j])))
        s = max(fuzz.token_set_ratio(keys[i], keys[j]),
                fuzz.token_sort_ratio(keys[i], keys[j]))
        if s >= 85:
            rf_pairs.append((i, j, s))

print(f"Jaccard >=0.6 candidate merges: {len(jac_pairs)}")
for i, j, s in jac_pairs:
    print(f"  J {s:.2f}  [{titles[i][0][:44]}] vs [{titles[j][0][:44]}]")
print(f"rapidfuzz >=85 candidate merges: {len(rf_pairs)}")
only_rf = [p for p in rf_pairs if (p[0], p[1]) not in {(a, b) for a, b, _ in jac_pairs}]
for i, j, s in only_rf:
    print(f"  RF {s:.0f}  [{titles[i][0][:44]}] vs [{titles[j][0][:44]}]")
print(f"caught ONLY by rapidfuzz: {len(only_rf)}")
# inverse: Jaccard yes, rapidfuzz no
only_jac = [p for p in jac_pairs if (p[0], p[1]) not in {(a, b) for a, b, _ in rf_pairs}]
print(f"caught ONLY by jaccard: {len(only_jac)}")
for i, j, s in only_jac:
    print(f"  J-only {s:.2f} [{titles[i][0][:44]}] vs [{titles[j][0][:44]}]")
