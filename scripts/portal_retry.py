#!/usr/bin/env python3
"""portal_retry.py — second-chance pass for the portal scan.
pass1: serial-ish retry of CONN-ERR/TIMEOUT/4xx/2xx-shell entries with 15s timeout + URL variants
pass2: proxy retry for WAF-blocked entries using the validated proxy pool (kimeta/stellenanzeigen unlockers first)
Merges into portal_scan_final_<ts>.json/.csv
"""
import concurrent.futures as cf
import csv, glob, json, random, re, time
from datetime import datetime
import requests, urllib3
urllib3.disable_warnings()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7"}
WAF_PAT = re.compile(r"Just a moment|Attention Required|Access denied|captcha|challenge-platform|cf-browser-verification", re.I)
TITLE_PAT = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)

src = sorted(glob.glob("/home/z/my-project/data/portals/portal_scan_*.json"))[-1]
scan = json.load(open(src))
results = scan["results"]
ts = datetime.now().strftime("%Y%m%d-%H%M")

VARIANTS = {
    "Golem Jobs": "https://jobs.golem.de/",
    "EURES": "https://eures.europa.eu/",
    "t3n Jobs": "https://t3n.de/",
    "SZ Jobs": "https://www.sueddeutsche.de/jobs",
    "Jobware": "https://www.jobware.de/",
    "JobScout24": "https://www.jobscout24.de/",
    "Jobboerse.de": "https://www.jobboerse.de/",
    "Jobboerse.com": "https://www.jobboerse.com/",
    "Stellenboerse.de": "https://www.stellenboerse.de/",
    "Tagesspiegel Jobs": "https://jobs.tagesspiegel.de/",
    "Regio-Jobanzeiger": "https://www.regiojobanzeiger.de/",
    "jobs-in-franken": "https://www.jobs-in-franken.de/",
    "Frankenjobs": "https://frankenjobs.de/",
    "Jobboerse Bayern": "https://jobboerse.bayern/",
    "Medi-Karriere": "https://www.medi-karriere.de/",
    "Pflege.jobs": "https://pflege.jobs/",
    "Handwerkerjobs.de": "https://handwerkerjobs.de/",
    "Sozialjobs": "https://www.sozialjobs.de/",
    "Ausbildungsatlas": "https://www.ausbildungsatlas.de/",
    "Kirchenjobs": "http://www.kirchenjobs.de/",
    "Brunel DE": "https://www.brunel.de/de/jobs",
    "Trovit DE": "https://de.trovit.com/",
    "dein-stellenmarkt (Joblocal)": "https://www.dein-stellenmarkt.de/",
    "Stellen.com": "https://stellen.com/",
    "Toytown Germany": "https://www.toytowngermany.com/jobs/",
    "Softgarden": "https://jobs.softgarden.de/",
}

def fetch(url, timeout=(5, 8), proxies=None):
    px = {"http": proxies, "https": proxies} if proxies else None
    r = requests.get(url, headers=HDRS, timeout=timeout, allow_redirects=True, verify=False, proxies=px)
    body = r.content[:150000].decode("utf-8", "ignore")
    m = TITLE_PAT.search(body)
    return {"http": r.status_code, "final_url": r.url, "title": (re.sub(r"\s+", " ", m.group(1)).strip()[:90] if m else ""),
            "waf": bool(r.status_code in (403, 429, 503) or WAF_PAT.search(body[:20000]))}

def classify(f):
    if f["http"] == 200 and not f["waf"]:
        return "OK"
    if f["http"] in (202,) or (f["http"] == 200 and f["waf"] is False and not f["title"]):
        return "JS-SHELL"
    if f["waf"]:
        return "BLOCKED-WAF"
    if f["http"] in (301, 302, 307, 308):
        return "REDIR"
    return f"HTTP-{f['http']}"

# ---------- pass1: retry direct ----------
retry1 = [r for r in results if r["status"] not in ("OK", "BLOCKED-WAF")]
def try_direct(r):
    url = VARIANTS.get(r["name"], r["url"])
    if not url.startswith("http"):
        url = "https://" + url
    try:
        f = fetch(url)
        r.update(status=classify(f), retry_url=url, **{k: f.get(k) for k in ("http", "final_url", "title", "waf")})
    except requests.exceptions.SSLError:
        r.update(status="SSL-ERR", retry_url=url)
    except requests.exceptions.ConnectionError:
        r.update(status="CONN-ERR", retry_url=url)
    except requests.exceptions.Timeout:
        r.update(status="TIMEOUT", retry_url=url)
    except Exception as e:
        r.update(status="ERR:" + type(e).__name__, retry_url=url)
    return r

print(f"pass1: parallel retry of {len(retry1)} entries ...", flush=True)
t1 = time.time()
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    retry1 = list(ex.map(try_direct, retry1))
print(f"  pass1 done in {time.time()-t1:.0f}s", flush=True)

# ---------- pass2: proxy retry for WAF blocks ----------
pool = json.load(open("/home/z/my-project/data/proxies/validated_proxies.json"))
unlockers = [f"{p['protocol']}://{p['host']}:{p['port']}" for p in pool if p.get("kimeta_ok") or p.get("stellenanzeigen_ok")]
rest = [f"{p['protocol']}://{p['host']}:{p['port']}" for p in pool if not (p.get("kimeta_ok") or p.get("stellenanzeigen_ok"))]
random.seed(42)
pxs = unlockers + random.sample(rest, min(25, len(rest)))
blocked = [r for r in results if r["status"] == "BLOCKED-WAF"]
print(f"pass2: proxy retry of {len(blocked)} WAF-blocked with {len(pxs)} proxies ...", flush=True)

def proxy_probe(item):
    i, r = item
    tried = []
    for px in pxs[i % 9::9][:4]:  # deterministic spread, 4 tries each
        try:
            f = fetch(r["url"], timeout=(4, 7), proxies=px)
            tried.append(px)
            if classify(f) == "OK":
                r.update(status="OK-VIA-PROXY", via_proxy=px, tried_n=len(tried),
                         **{k: f.get(k) for k in ("http", "final_url", "title", "waf")})
                return r
        except Exception:
            tried.append(px)
    r["tried_n"] = len(tried)
    r["status"] = "BLOCKED-STRICT"
    return r

t0 = time.time()
with cf.ThreadPoolExecutor(max_workers=14) as ex:
    done = list(ex.map(proxy_probe, enumerate(blocked)))
print(f"  pass2 done in {time.time()-t0:.0f}s", flush=True)

# ---------- summary ----------
from collections import Counter
by_status = Counter(r["status"] for r in results)
print(f"\n=== FINAL {ts}: {len(results)} portals ===")
print("status:", dict(by_status))
ok_all = [r for r in results if r["status"] in ("OK", "OK-VIA-PROXY", "JS-SHELL")]
for r in ok_all:
    print(f"  [{r['status']:13}] [{r['category']:9}] {r['name']:34} {r.get('final_url', r['url'])[:64]}")
strict = [r for r in results if r["status"] == "BLOCKED-STRICT"]
print(f"\nSTILL BLOCKED after proxy ({len(strict)}):")
for r in strict:
    print(f"  {r['name']:34} {r['url'][:60]}")

jf = f"/home/z/my-project/data/portals/portal_scan_final_{ts}.json"
json.dump({"ts": ts, "count": len(results), "results": results}, open(jf, "w"), ensure_ascii=False, indent=1)
cf_path = f"/home/z/my-project/data/portals/portal_scan_final_{ts}.csv"
with open(cf_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["name", "url", "category", "access_hint", "status", "http", "waf", "title", "via_proxy", "in_pipeline", "note"])
    w.writeheader()
    for r in results:
        w.writerow({k: r.get(k, "") for k in w.fieldnames})
print(f"\nsaved: {jf}\nsaved: {cf_path}")
