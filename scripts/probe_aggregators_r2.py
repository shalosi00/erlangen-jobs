#!/usr/bin/env python3
"""Round-2 recon: find the real programmatic endpoints for alive aggregators."""
import json, os, re, requests

PROBE = "/home/z/my-project/research/aggregators-round2/probe"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}

def get(url, **kw):
    try:
        return requests.get(url, headers=H, timeout=20, allow_redirects=True, **kw)
    except Exception as e:
        return None

def brief(r, name, extra=""):
    if r is None:
        print(f"  {name:38} ERR")
        return
    body = r.text[:2_000_000]
    n_jp = body.count('"JobPosting"') + body.count("'JobPosting'")
    slugs = list(dict.fromkeys(re.findall(r'href="(/[a-z0-9\-/]*job[a-z0-9\-/]{3,80})"', body)))[:5]
    print(f"  {name:38} {r.status_code} {len(body):>8}B jp={n_jp} {extra} slugs={slugs[:3]}")
    if r.status_code == 200:
        fn = f"{PROBE}/r2_{name.replace('/','_').replace('?','q').replace('=','_').replace('&','_')}.html"
        open(fn, "w", errors="ignore").write(body)

print("== ABSOLVEVENTA ==")
for u in ["https://www.absolventa.de/jobs?what=fachinformatiker&where=Erlangen",
          "https://www.absolventa.de/jobs/fachinformatiker",
          "https://www.absolventa.de/jobs/fachinformatiker/erlangen"]:
    brief(get(u), u.replace("https://www.absolventa.de", ""))
brief(get("https://www.absolventa.de/api/p/autocompletes/absolventa?q=fachinf"), "autocomplete api")

print("== GET-IN-IT (next data) ==")
h = open(f"{PROBE}/get-in-it_www_get-in-it_de_200.html", errors="ignore").read()
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', h, re.S)
if m:
    j = json.loads(m.group(1))
    print("  buildId:", j.get("buildId"), "page:", j.get("page"))
    pp = j.get("props", {}).get("pageProps", {})
    print("  pageProps keys:", list(pp.keys())[:12])
    apil = sorted(set(re.findall(r'https://[a-z0-9.\-]*(?:get-in-it|azubiyo)[a-z0-9.\-]*/[a-z0-9/\-_.]{3,60}', h)))
    print("  api-ish urls:", apil[:8])
for u in ["https://www.get-in-it.de/jobsuche?was=fachinformatiker&wo=Erlangen",
          "https://www.get-in-it.de/jobsuche/fachinformatiker"]:
    brief(get(u), u.replace("https://www.get-in-it.de", ""))

print("== JOBWARE (api hints in saved html) ==")
h = open(f"{PROBE}/jobware_www_jobware_de_200.html", errors="ignore").read()
print("  api hints:", sorted(set(re.findall(r'"(/api/[a-z0-9/_.\-]{3,70})"', h)))[:12])
print("  searchform actions:", list(dict.fromkeys(re.findall(r'<form[^>]*action="([^"]+)"', h)))[:6])
print("  jobsPerPage/rpc:", sorted(set(re.findall(r'(restclient|/rest/[a-z0-9/_.\-]{3,60}|jobsuche[a-z0-9/_.\-]*)', h)))[:8])

print("== GERMANTECHJOBS (next data) ==")
h = open(f"{PROBE}/germantechjobs_germantechjobs_de_200.html", errors="ignore").read()
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', h, re.S)
if m:
    j = json.loads(m.group(1))
    print("  buildId:", j.get("buildId"), "page:", j.get("page"))
    print("  pageProps keys:", list(j.get("props", {}).get("pageProps", {}).keys())[:12])
print("  fetch urls:", sorted(set(re.findall(r'https://[a-z0-9.\-]*germantechjobs\.de/api[a-z0-9/_.\-]*', h)))[:8])
brief(get("https://germantechjobs.de/api/jobs?search=fachinformatiker"), "gtj /api/jobs")

print("== CONNECTICUM ==")
h = open(f"{PROBE}/connecticum_www_connecticum_de_200.html", errors="ignore").read()
print("  jsonld:", h.count('ld+json'), "| form actions:", list(dict.fromkeys(re.findall(r'action="([^"]+)"', h)))[:5])
print("  job links:", list(dict.fromkeys(re.findall(r'href="(/jobboerse/[a-z0-9\-/]{5,90})"', h)))[:6])

print("== STELLENANZEIGEN saved 200 ==")
h = open(f"{PROBE}/stellenanzeigen_www_stellenanzeigen_de_200.html", errors="ignore").read()
print("  cf challenge?", bool(re.search(r'Just a moment|challenge-platform', h)), "| JobPosting:", h.count('"JobPosting"'))
print("  api hints:", sorted(set(re.findall(r'"(/api/[a-z0-9/_.\-]{3,70})"', h)))[:10])
print("  job links:", list(dict.fromkeys(re.findall(r'href="(/[a-z0-9\-]{6,80}/[a-z0-9\-]{6,80}/\d{5,12})"', h)))[:5])

print("== INTERAMT homepage ==")
r = get("https://interamt.de/")
if r is not None:
    print("  status", r.status_code, "len", len(r.text))
    print("  links:", list(dict.fromkeys(re.findall(r'href="([^"]*(?:stelle|suche|such)[^"]*)"', r.text)))[:8])
    api = sorted(set(re.findall(r'(oppa-service[a-z0-9/_.\-]*)', r.text)))
    print("  oppa hints:", api[:6])

print("== BERUFSSTART homepage ==")
r = get("https://www.berufsstart.de/")
if r is not None:
    print("  status", r.status_code, "len", len(r.text))
    print("  job links:", list(dict.fromkeys(re.findall(r'href="([^"]*(?:jobs?|stellen)[^"]*)"', r.text)))[:8])

print("== INFRANKEN ==")
for u in ["https://www.infranken.de/", "https://www.infranken.de/stellenmarkt/"]:
    r = get(u)
    if r is not None:
        print(f"  {u[-30:]:32} {r.status_code} {len(r.text)}B")
        if r.status_code == 200:
            print("   stellen links:", list(dict.fromkeys(re.findall(r'href="([^"]*(?:stellen|job)[^"]*)"', r.text)))[:8])

print("== KIMETA retry ==")
for hdrs in [{}, {"Accept-Encoding": "gzip"}, ]:
    r = get("https://www.kimeta.de/", headers={**H, **hdrs})
    print("  kimeta.de:", r.status_code if r else "ERR", len(r.text) if r else "")
