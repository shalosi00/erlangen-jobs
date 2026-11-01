#!/usr/bin/env python3
"""Round-5: final endpoint verification per site."""
import json, re, requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}
P = "/home/z/my-project/research/aggregators-round2/probe"

def get(url, **kw):
    try:
        return requests.get(url, headers=H, timeout=25, allow_redirects=True, **kw)
    except Exception as e:
        print("   ERR", type(e).__name__, str(e)[:60]); return None

print("== ABSOLVEVENTA turbo frames ==")
h = open(f"{P}/r4_absolventa.html", errors="ignore").read()
fr = list(dict.fromkeys(re.findall(r'<turbo-frame[^>]*src="([^"]+)"', h)))
print("   turbo-frame srcs:", fr[:6])
cnt = re.findall(r'>(\d+)<', h)
ctx = re.findall(r'(\d+)\s*</(?:strong|b|span|p)>\s*(?:Jobs|Stellen|offene)', h)[:3]
print("   ctx counts:", ctx, "| 'offene' near:", re.findall(r'.{40}offene.{60}', h)[:2])
if fr:
    r = get(fr[0] if fr[0].startswith("http") else "https://www.absolventa.de" + fr[0])
    if r:
        open(f"{P}/r5_absolventa_frame.html", "w", errors="ignore").write(r.text)
        print("   frame:", r.status_code, len(r.text), "jp:", r.text.count("JobPosting"))
        print("   frame links:", list(dict.fromkeys(re.findall(r'href="(/jobs/[a-z0-9][a-z0-9\-]{10,110})"', r.text)))[:5])

print("== GET-IN-IT /jobsuche html api grep ==")
r = get("https://www.get-in-it.de/jobsuche?was=fachinformatiker&wo=Erlangen")
if r:
    open(f"{P}/r5_getinit_jobsuche.html", "w", errors="ignore").write(r.text)
    print("   status", r.status_code, len(r.text))
    print("   api strings:", sorted(set(re.findall(r'(https://[a-z0-9.\-]+/api[a-z0-9/_.\-]*)', r.text)))[:8])
    print("   NEXT_PUBLIC:", sorted(set(re.findall(r'(NEXT_PUBLIC_[A-Z_]+)', r.text)))[:8])
    print("   json fetch:", sorted(set(re.findall(r'"(/jobsuche/[a-z0-9/_.\-]+)"', r.text)))[:8])

print("== INTERAMT app.js api ==")
r = get("https://interamt.de/koop/js_26.0.5/interamt/app.js")
if r:
    print("   app.js", len(r.text))
    urls = sorted(set(re.findall(r'["\'](/[a-z0-9\-/]*(?:api|rest|service|stellen)[a-z0-9\-/.]*)["\']', r.text)))
    print("   paths:", urls[:12])
    hosts = sorted(set(re.findall(r'["\'](https?://[a-z0-9.\-/]*interamt[a-z0-9.\-/]*)["\']', r.text)))
    print("   hosts:", hosts[:8])

print("== BERUFSSTART ergebnisliste ==")
r = get("https://www.berufsstart.de/ergebnisliste.php?suchbegriff=fachinformatiker")
if r:
    open(f"{P}/r5_berufsstart.html", "w", errors="ignore").write(r.text)
    print("   status", r.status_code, len(r.text))
    print("   treffer:", re.findall(r'(\d+)\s*(?:Stellen|Treffer|Jobs|Anzeigen)', r.text)[:3])
    print("   detail links:", list(dict.fromkeys(re.findall(r'href="([^"]*(?:job|stelle|anzeigen)[^"]*)"', r.text)))[:6])

print("== INFRANKEN suchergebnisse ==")
r = get("https://jobs.infranken.de/suchergebnisse?Searchterm=fachinformatiker")
if r:
    open(f"{P}/r5_infranken.html", "w", errors="ignore").write(r.text)
    print("   status", r.status_code, len(r.text))
    print("   counts:", re.findall(r'(\d+)\s*(?:Jobs?|Stellen|Treffer|offene)', r.text)[:3])
    print("   links:", list(dict.fromkeys(re.findall(r'href="(/[a-z0-9\-/]{6,100})"', r.text)))[:10])

print("== TALENT.COM jsonld ==")
h = open(f"{P}/r4_talentcom.html", errors="ignore").read()
bl = re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)
for b in bl:
    try:
        j = json.loads(b)
        types = [x.get("@type") for x in (j if isinstance(j, list) else [j])]
        print("   ld types:", types[:3])
        if "@type" in j and j["@type"] == "ItemList" or (isinstance(j, list) and len(j) > 3):
            print("   items:", len(j) if isinstance(j, list) else j.get("numberOfItems"))
    except Exception as e:
        print("   ld parse err", str(e)[:50])
print("   total-jobs text:", re.findall(r'([\d\.]+)\s*(?:Jobs?|Stellenangebote|Stellen)', h)[:3])
cards = list(dict.fromkeys(re.findall(r'href="(https://de\.talent\.com/redirect[^"]+)"', h)))
print("   redirect cards:", len(cards), cards[:2])

print("== IT-MITTELSTAND structure ==")
h = open(f"{P}/r4_itmittelstand.html", errors="ignore").read()
print("   article links:", list(dict.fromkeys(re.findall(r'href="(https://www\.it-mittelstand\.de/[a-z0-9\-]{8,100}/)"', h)))[:6])
print("   external job links:", list(dict.fromkeys(re.findall(r'href="(https?://(?!www\.it-mittelstand)[a-z0-9.\-/]{15,90})"', h)))[:6])

print("== JOBWARE homepage form ==")
h = open(f"{P}/jobware_www_jobware_de_200.html", errors="ignore").read()
print("   forms:", list(dict.fromkeys(re.findall(r'<form[^>]*action="([^"]+)"', h)))[:5])
print("   api endpoints:", sorted(set(re.findall(r'"((?:https?://www\.jobware\.de)?/(?:api|rest|services?)/[a-z0-9/_.\-]{3,60})"', h)))[:8])
print("   search ui hints:", sorted(set(re.findall(r'(jobsearch[a-z0-9/_.\-]*|/jobsuche[a-z0-9/_.\-]*|/jo\?[a-z=&;]{0,40})', h)))[:8])
