"""Unit tests for the Task-12 dedupe upgrade (core.py).
Cases come from REAL production evidence:
  A. same canonical URL, different agency titles (BA 12634-BB-64)  -> MERGE
  B. BAVARIAHEADHUNTER 'ID xxx' variants (task-11 regression)      -> MERGE
  C. Brunel 'IT-Spezialist (w/m/d)' vs FERCHAU 'IT-Spezialist Netzwerk & Connectivity'
     (different employers, GmbH-token trap)                        -> NO MERGE + FLAG
  D. rapidfuzz unavailable -> graceful Jaccard-only behavior           -> still works
"""
import sys
sys.path.insert(0, "/home/z/my-project")
from pipeline.core import Job, dedupe, canon_url
import pipeline.core as core

fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)

# --- A: same URL, different titles
a1 = Job(source="BA", title="IT System Engineer (m/w/d) z/OS Netzwerk und Security",
         company="Akkodis Germany Tech Experts", city="Nürnberg, Mittelfranken",
         url="https://www.arbeitsagentur.de/jobsuche/jobdetail/12634-BB-64")
a2 = Job(source="XING", title="System Engineer Netzwerk (m/w/d)",
         company="Akkodis", city="Nürnberg",
         url="https://www.arbeitsagentur.de/jobsuche/jobdetail/12634-BB-64")
r = dedupe([a1, a2])
check("A: same-URL merge -> 1 row", len(r) == 1)
check("A: merged source carries both", len(r) == 1 and "XING" in r[0].source and "BA" in r[0].source)
check("A: canon_url strips www+scheme", canon_url(a1.url) == "arbeitsagentur.de/jobsuche/jobdetail/12634-bb-64")

# --- B: task-11 regression, agency ID variants, no URL
b1 = Job(source="BH", title="IT-Systemelektroniker ID 7285", company="BAVARIAHEADHUNTER GmbH", city="Erlangen")
b2 = Job(source="BH", title="IT-Systemelektroniker ID SW72", company="BAVARIAHEADHUNTER GmbH", city="Erlangen")
b3 = Job(source="BH", title="IT Systemelektroniker ID 441", company="BAVARIAHEADHUNTER GmbH", city="Erlangen")
r = dedupe([b1, b2, b3])
check("B: ID-variant trio still merges -> 1 row", len(r) == 1)

# --- C: different employers, near-identical titles (must NOT merge, must FLAG)
c1 = Job(source="BA", title="IT-Spezialist (w/m/d)", company="Brunel GmbH NL Mannheim",
         city="Erlangen", url="https://www.arbeitsagentur.de/jobsuche/jobdetail/12362-TR-30")
c2 = Job(source="BA", title="IT-Spezialist Netzwerk & Connectivity (m/w/d)",
         company="FERCHAU GmbH Niederlassung N", city="Erlangen",
         url="https://www.arbeitsagentur.de/jobsuche/jobdetail/12265-51630")
r = dedupe([c1, c2])
check("C: distinct employers NOT merged -> 2 rows", len(r) == 2)
check("C: both flagged near-dupe-candidate",
      len(r) == 2 and all("near-dupe-candidate" in (j.notes or "") for j in r))

# --- C2: GmbH-token trap: same title, different companies, no flag (no city match noise)
d1 = Job(source="T", title="IT-Supporter", company="Brunel GmbH", city="Erlangen")
d2 = Job(source="T", title="IT-Supporter", company="FERCHAU GmbH", city="Erlangen")
r = dedupe([d1, d2])
check("C2: legal-form stopword blocks GmbH-only company overlap -> 2 rows", len(r) == 2)

# --- D: graceful degradation without rapidfuzz
core._fuzz = None
r = dedupe([Job(source="BA", title="Fachinformatiker Systemintegration", company="Muster AG", city="Erlangen"),
            Job(source="K", title="Fachinformatiker Systemintegration", company="Muster AG", city="Erlangen")])
check("D: exact-key merge works without rapidfuzz", len(r) == 1)
core._fuzz = __import__("rapidfuzz").fuzz
r = dedupe([c1, c2])
check("D: rapidfuzz flagging restored", all("near-dupe-candidate" in (j.notes or "") for j in r))

print("\n" + ("ALL DEDUPE TESTS PASS" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
