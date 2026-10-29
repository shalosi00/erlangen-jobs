"""Smoke test 6: scrapling core parser on REAL saved evidence HTML
(kimeta SERP captured in round-2 probes). Question: can scrapling's Selector
replace/backup our regex+html.parser extraction, and does its API hold up?"""
import glob, time
t0 = time.time()
from scrapling import Selector

# find a real kimeta SERP capture
candidates = [c for c in glob.glob("/home/z/my-project/research/aggregators-round2/probe/*kimeta*.html")
              if "503" not in c]
print("evidence files:", candidates)
html = open(candidates[0], encoding="utf-8", errors="ignore").read()
print(f"file: {candidates[0].split('/')[-1]}  size={len(html)//1024}KB")

sel = Selector(html)
title = sel.css("title::text").get()
print("page <title>:", (title or "").strip()[:70])

# job cards on kimeta SERP use article/job elements; probe generically
cards = sel.css("a[href*='/job/'], a[href*='jobdisplay'], h2 a, h3 a")
print(f"anchor candidates found: {len(cards)}")
for a in cards[:5]:
    href = a.attrib.get("href", "")[:60]
    txt = (a.css("::text").get() or "").strip()[:50]
    print(f"  {txt!r} -> {href}")

# headline features: find_similar (locate repeated card structures) +
# generate_css_selector (self-documenting selectors for parser maintenance)
anchors = sel.css("a[href*='/job/']")
if anchors:
    print("find_similar on first job anchor:", len(anchors[0].find_similar()))
    print("auto-generated selector:", anchors[0].generate_css_selector()[:80])

# XPath + attribute chaining demo (adaptive matching is the headline feature)
h2s = sel.xpath("//h2//text()").getall()
print("h2 texts:", [t.strip() for t in h2s[:3] if t.strip()][:3])
print(f"parse time: {time.time()-t0:.2f}s (incl. import)")
print("SCRAPLING CORE", "PASS" if title else "FAIL")
