#!/usr/bin/env python3
"""Decisive unlock test: fetch REAL job listings from WAF-blocked boards
(a) via validated proxies, (b) via curl_cffi TLS-impersonation, (c) cloudscraper."""
import json
import os
import sys
import time

import requests
from curl_cffi import requests as cr

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
# proxy_tools/ is two levels below the repo root -> three dirname hops
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(BASE, "data", "proxies", "validated_proxies.json")

def load_proxies(field, n=6):
    """Load the validated proxy pool; fail with an actionable message, never a traceback."""
    try:
        with open(DATA, encoding="utf-8") as f:
            rows = json.load(f)
    except FileNotFoundError:
        sys.exit("ERROR: validated proxy pool not found: %s\n"
                 "       Build it first:  python3 scripts/proxy_tools/fetch_and_test.py"
                 % DATA)
    except json.JSONDecodeError as e:
        sys.exit("ERROR: validated proxy pool is corrupt (%s): %s\n"
                 "       Rebuild it:     python3 scripts/proxy_tools/fetch_and_test.py"
                 % (DATA, e))
    if not isinstance(rows, list) or not rows:
        sys.exit("ERROR: validated proxy pool is empty: %s\n"
                 "       Rebuild it:  python3 scripts/proxy_tools/fetch_and_test.py" % DATA)
    rows = [r for r in rows if isinstance(r, dict) and r.get(field)] or rows
    rows.sort(key=lambda r: r.get("latency_ms") or 9999)
    return rows[:n]

def save_sample(name, html):
    """Persist a fetched HTML sample; never abort the test if the write fails."""
    path = os.path.join(BASE, "data", "proxies", name)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    except OSError as e:
        print(f"  WARN: could not save sample {name}: {type(e).__name__}: {e}")

def via_proxy(url, proxy_row, timeout=12):
    p = proxy_row
    scheme = {"http": "http", "https": "http", "socks4": "socks4", "socks5": "socks5h"}[p["protocol"]]
    proxies = {"http": f"{scheme}://{p['host']}:{p['port']}",
               "https": f"{scheme}://{p['host']}:{p['port']}"}
    t0 = time.perf_counter()
    r = requests.get(url, headers=UA, proxies=proxies, timeout=timeout)
    return r.status_code, int((time.perf_counter()-t0)*1000), r.text

def main():
    # ---------- KIMETA via proxies ----------
    print("=" * 70)
    print("KIMETA search via best proxies  (direct = 503 from this DC)")
    kim = load_proxies("kimeta_ok")
    url = "https://www.kimeta.de/fachinformatiker-jobs-erlangen"
    wins = 0
    for p in kim:
        try:
            code, lat, html = via_proxy(url, p)
            n_jobs = html.count('job-') + html.count('JobPosting')
            marker = "JSON-LD" if 'JobPosting' in html else ("cards" if 'job-' in html else "?")
            print(f"  {p['protocol']:>6} {p['host']}:{p['port']} [{p.get('country')}] "
                  f"-> {code} {lat}ms len={len(html)} marker={marker}({n_jobs})")
            if code == 200 and len(html) > 50000:
                wins += 1
                if wins == 1:
                    save_sample("kimeta_sample.html", html)
        except Exception as e:
            print(f"  {p['protocol']:>6} {p['host']}:{p['port']} -> ERR {type(e).__name__}")

    # ---------- STELLENANZIGEN via proxies ----------
    print("=" * 70)
    print("STELLENANZIGEN.de search via best proxies  (direct = CF-blocked)")
    st = load_proxies("stellenanzeigen_ok")
    url2 = "https://www.stellenanzeigen.de/suche/?keywords=Fachinformatiker&region=Erlangen"
    wins2 = 0
    for p in st:
        try:
            code, lat, html = via_proxy(url2, p)
            n_jobs = html.count('JobPosting')
            print(f"  {p['protocol']:>6} {p['host']}:{p['port']} [{p.get('country')}] "
                  f"-> {code} {lat}ms len={len(html)} JobPosting={n_jobs}")
            if code == 200 and len(html) > 50000:
                wins2 += 1
                if wins2 == 1:
                    save_sample("stellenanzeigen_sample.html", html)
        except Exception as e:
            print(f"  {p['protocol']:>6} {p['host']}:{p['port']} -> ERR {type(e).__name__}")

    # ---------- curl_cffi direct (no proxy!) ----------
    print("=" * 70)
    print("curl_cffi TLS-impersonation DIRECT (no proxy)")
    for name, url in [("kimeta", "https://www.kimeta.de/fachinformatiker-jobs-erlangen"),
                      ("stellenanzeigen", "https://www.stellenanzeigen.de/suche/?keywords=Fachinformatiker&region=Erlangen"),
                      ("jobvector", "https://www.jobvector.de/jobs?search_term=Fachinformatiker"),
                      ("jobrapido", "https://de.jobrapido.com/?q=Fachinformatiker+Erlangen")]:
        for imp in ("chrome124", "chrome110"):
            try:
                t0 = time.perf_counter()
                r = cr.get(url, impersonate=imp, timeout=15, headers={"Accept-Language": "de-DE,de;q=0.9"})
                lat = int((time.perf_counter()-t0)*1000)
                print(f"  {name:<16} impersonate={imp} -> {r.status_code} {lat}ms len={len(r.text)} "
                      f"JobPosting={r.text.count('JobPosting')}")
                if r.status_code == 200 and len(r.text) > 50000:
                    save_sample(f"curlcffi_{name}_{imp}.html", r.text)
                break
            except Exception as e:
                print(f"  {name:<16} impersonate={imp} -> ERR {type(e).__name__}: {str(e)[:60]}")

    # ---------- cloudscraper direct ----------
    print("=" * 70)
    print("cloudscraper direct (no proxy)")
    try:
        import cloudscraper
    except ImportError:
        print("  SKIP: cloudscraper is not installed (optional; pip install cloudscraper)")
    else:
        s = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "linux", "desktop": True})
        for name, url in [("kimeta", "https://www.kimeta.de/fachinformatiker-jobs-erlangen"),
                          ("jobvector", "https://www.jobvector.de/jobs?search_term=Fachinformatiker")]:
            try:
                t0 = time.perf_counter()
                r = s.get(url, timeout=20, headers={"Accept-Language": "de-DE,de;q=0.9"})
                lat = int((time.perf_counter()-t0)*1000)
                print(f"  cloudscraper {name:<12} -> {r.status_code} {lat}ms len={len(r.text)} "
                      f"JobPosting={r.text.count('JobPosting')}")
            except Exception as e:
                print(f"  cloudscraper {name:<12} -> ERR {type(e).__name__}: {str(e)[:60]}")

if __name__ == "__main__":
    main()
