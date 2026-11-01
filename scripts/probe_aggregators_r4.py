#!/usr/bin/env python3
"""Round-4: run a real FISI/Erlangen query per candidate and extract samples."""
import json, re, requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}

def get(url, **kw):
    try:
        return requests.get(url, headers=H, timeout=22, allow_redirects=True, **kw)
    except Exception as e:
        print("   ERR", type(e).__name__, str(e)[:70]); return None

def save(name, r):
    if r is not None:
        open(f"/home/z/my-project/research/aggregators-round2/probe/r4_{name}.html", "w", errors="ignore").write(r.text)
    return r

print("== 1 ABSOLVEVENTA text/location params ==")
r = get("https://www.absolventa.de/jobs?text=fachinformatiker&location=Erlangen&radius=50")
if r:
    save("absolventa", r)
    h = r.text
    cnt = re.findall(r'(\d[\d\.]{0,9})\s*(?:Jobs?|Stellen|Treffer)', h)[:3]
    jobs = re.findall(r'href="(/jobs/[a-z0-9][a-z0-9\-]{10,110})"', h)
    print("   counts:", cnt, "| detail links:", len(set(jobs)), list(dict.fromkeys(jobs))[:4])

print("== 2 GET-IN-IT fresh buildId data route ==")
r = get("https://www.get-in-it.de/jobsuche?was=fachinformatiker&wo=Erlangen")
if r:
    m = re.search(r'"buildId":"([^"]+)"', r.text)
    if m:
        bid = m.group(1)
        print("   buildId:", bid)
        d = get(f"https://www.get-in-it.de/_next/data/{bid}/jobsuche.json?was=fachinformatiker&wo=Erlangen")
        if d is not None and d.headers.get("content-type", "").startswith("application/json"):
            j = d.json()
            pp = j.get("pageProps", {})
            print("   pageProps keys:", list(pp.keys())[:12])
            save("getinit_json", d)
        else:
            print("   data route status:", d.status_code if d else "ERR", (d.headers.get("content-type") if d else ""))

print("== 3 CONNECTICUM result parse ==")
r = get("https://www.connecticum.de/jobs?searchterm=fachinformatiker&submit=1")
if r:
    save("connecticum", r)
    h = r.text
    print("   treffer:", re.findall(r'(\d+)\s*(?:Treffer|Stellen|Jobs|offene)', h)[:3])
    print("   anchors:", list(dict.fromkeys(re.findall(r'<a[^>]+href="([^"]*(?:stellenangebot|job)[^"]*)"', h)))[:5])

print("== 4 INTERAMT api discovery ==")
r = get("https://interamt.de/stellensuche")
if r:
    save("interamt", r)
    h = r.text
    print("   js bundles:", list(dict.fromkeys(re.findall(r'src="([^"]+\.js[^"]*)"', h)))[:6])
    print("   endpoints:", sorted(set(re.findall(r'"((?:https?:)?//[^"]*(?:api|service)[^"]*)"', h)))[:6])

print("== 5 BERUFSSTART ergebnisliste params ==")
r = get("https://www.berufsstart.de/jobs/")
if r:
    h = r.text
    form = re.search(r'<form[^>]*ergebnisliste\.php.*?</form>', h, re.S)
    if form:
        print("   form inputs:", re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', form.group(0))[:15])
        print("   method/action:", re.findall(r'<form[^>]*>', form.group(0))[:1])
    print("   region links:", list(dict.fromkeys(re.findall(r'href="(/jobs/[a-z\-]+/)"', h)))[:10])

print("== 6 JOBS.INFRANKEN.DE search ==")
r = get("https://jobs.infranken.de/", )
if r:
    h = r.text
    forms = re.findall(r'<form[^>]*>', h)[:3]
    print("   forms:", forms)
    r2 = get("https://jobs.infranken.de/jobs?Searchterm=fachinformatiker")
    if r2:
        save("infranken", r2)
        cnt = re.findall(r'(\d+)\s*(?:Jobs?|Stellen|Treffer|offene)', r2.text)[:3]
        links = list(dict.fromkeys(re.findall(r'href="(/jobdetails?/[^"]+|/jobs/[^"]*\d[^"]*)"', r2.text)))[:5]
        print("   /jobs?Searchterm= status", r2.status_code, "counts:", cnt, "links:", links)

print("== 7 TALENT.COM structure ==")
r = get("https://de.talent.com/jobs?k=fachinformatiker&l=Erlangen")
if r:
    save("talentcom", r)
    h = r.text
    print("   counts:", re.findall(r'([\d\.,]+)\s*(?:Jobs?|Stellen)', h)[:3])
    print("   jsonld:", h.count('ld+json'), "| card class:", list(dict.fromkeys(re.findall(r'class="(card[^"]*)"', h)))[:5])

print("== 8 IT-MITTELSTAND ==")
r = get("https://www.it-mittelstand.de/jobs/?s=fachinformatiker")
if r:
    save("itmittelstand", r)
    print("   links:", list(dict.fromkeys(re.findall(r'href="(https://www\.it-mittelstand\.de/job[^"]*)"', r.text)))[:5])
    print("   wp job mgr:", "wp-job-manager" in r.text)

print("== 9 FAU retry ==")
for u in ["https://www.jobboerse.fau.de/", "https://jobboerse.fau.de/"]:
    r = get(u)
    print("   ", u, r.status_code if r is not None else "ERR")

print("== 10 JOBWARE retry ==")
for u in ["https://www.jobware.de/", "https://www.jobware.de/jobs"]:
    r = get(u)
    print("   ", u, r.status_code if r is not None else "ERR", len(r.text) if r is not None else "")
