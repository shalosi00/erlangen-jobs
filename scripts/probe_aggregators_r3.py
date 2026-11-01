#!/usr/bin/env python3
"""Round-3: chase real endpoints for each candidate; add 6 fresh targets."""
import json, re, requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}

def get(url, **kw):
    try:
        return requests.get(url, headers=H, timeout=20, allow_redirects=True, **kw)
    except Exception as e:
        return None

def show(tag, r, jp=True):
    if r is None:
        print(f"{tag:44} ERR")
        return None
    t = r.text[:2_000_000]
    n = t.count('"JobPosting"') if jp else 0
    print(f"{tag:44} {r.status_code} {len(t):>8}B jp={n}")
    return r if r.status_code == 200 else None

# --- 1. CONNECTICUM /jobs real search ---
r = show("connecticum /jobs?searchterm=", get("https://www.connecticum.de/jobs?searchterm=fachinformatiker&ort=Erlangen"))
if r:
    h = r.text
    print("   form actions:", list(dict.fromkeys(re.findall(r'action="([^"]+)"', h)))[:4])
    print("   input names:", re.findall(r'<input[^>]*name="([^"]+)"', h)[:12])
    print("   job hrefs:", list(dict.fromkeys(re.findall(r'href="(/jobs/[a-z0-9\-/]{6,100})"', h)))[:5])

# --- 2. INTERAMT /stellensuche ---
r = show("interamt /stellensuche", get("https://interamt.de/stellensuche"))
if r:
    h = r.text
    print("   api urls:", sorted(set(re.findall(r'["\'](/[a-z0-9\-/]*api[a-z0-9/_.\-]*)["\']', h)))[:8])
    print("   fetch/xhr:", sorted(set(re.findall(r'(oppa[a-z0-9/_.\-]*)', h)))[:8])

# --- 3. ABSOLVEVENTA search form params ---
r = show("absolventa /jobs (form grep)", get("https://www.absolventa.de/jobs"))
if r:
    print("   inputs:", re.findall(r'<input[^>]*name="([^"]+)"', r.text)[:12])
    print("   selects:", re.findall(r'<select[^>]*name="([^"]+)"', r.text)[:6])
    ac = get("https://www.absolventa.de/api/p/autocompletes/absolventa?q=fachinf")
    print("   autocomplete:", ac.text[:200] if ac is not None else "ERR")

# --- 4. GET-IN-IT data route ---
r = show("get-in-it /jobsuche (data route)", get("https://www.get-in-it.de/_next/data/UJgvXHtzry2IS-kqfNm18/jobsuche.json"))
if r and r.text.startswith("{"):
    j = r.json()
    print("   json keys:", list(j.keys())[:8])
    pp = j.get("pageProps", {})
    print("   pageProps:", list(pp.keys())[:10])

# --- 5. GERMANTECHJOBS /jobs + robots ---
r = show("germantechjobs /jobs", get("https://germantechjobs.de/jobs"))
rr = get("https://germantechjobs.de/robots.txt")
print("   robots:", rr.text[:200].replace("\n", " | ") if rr is not None else "ERR")

# --- 6. JOBWARE robots + sitemap + serp ---
rr = get("https://www.jobware.de/robots.txt")
print("jobware robots:", rr.text[:300].replace("\n", " | ") if rr is not None else "ERR")
r = show("jobware /jobs?f=fachinformatiker", get("https://www.jobware.de/jobs?f=fachinformatiker"))

# --- 7. JOBLOCAL (powers regional news boards) ---
r = show("jobs.infranken.de (joblocal?)", get("https://jobs.infranken.de/"))
if r:
    h = r.text
    print("   api hints:", sorted(set(re.findall(r'(api\.joblocal[a-z0-9/_.\-]*|/api/v[0-9][a-z0-9/_.\-]*)', h)))[:8])
    print("   inputs:", re.findall(r'name="([^"]+)"', h)[:10])
r2 = get("https://api.joblocal.de/v4/search/jobs?q[fachinformatiker]&location=Erlangen")
print("joblocal api:", r2.status_code if r2 is not None else "ERR", (r2.text[:150] if r2 is not None else ""))

# --- 8. BERUFSSTART /jobs ---
r = show("berufsstart /jobs/", get("https://www.berufsstart.de/jobs/"))
if r:
    print("   bayern link:", re.findall(r'href="([^"]*bayern[^"]*)"', r.text)[:3])
    print("   search form:", list(dict.fromkeys(re.findall(r'action="([^"]+)"', r.text)))[:4])

# --- 9. fresh: TALENT.COM (neuvoo) ---
r = show("talent.com de search", get("https://de.talent.com/jobs?k=fachinformatiker&l=Erlangen"))
r = show("neuvoo de search", get("https://de.neuvoo.com/jobs?k=fachinformatiker&l=Erlangen"))

# --- 10. fresh: STAUFENBIEL ---
r = show("staufenbiel jobsuche", get("https://www.staufenbiel.de/jobs.html?searchTerm=fachinformatiker"))

# --- 11. fresh: IT-MITTELSTAND ---
r = show("it-mittelstand jobsuche", get("https://www.it-mittelstand.de/jobs/?s=fachinformatiker"))

# --- 12. fresh: T3N JOBS ---
r = show("t3n jobs", get("https://t3n.de/jobs/?q=fachinformatiker"))

# --- 13. JOBS.DE redirect check ---
r = get("https://www.jobs.de/")
print("jobs.de:", r.status_code if r is not None else "ERR", r.url[:80] if r is not None else "")
