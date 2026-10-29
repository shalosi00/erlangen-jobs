#!/usr/bin/env python3
"""Decisive unlock test: fetch REAL job listings from WAF-blocked boards
(a) via validated proxies, (b) via curl_cffi TLS-impersonation, (c) cloudscraper."""
import json
import random
import sys
import time

import requests
from curl_cffi import requests as cr

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
DATA = "/home/z/my-project/data/proxies/validated_proxies.json"

def load_proxies(field, n=6):
    rows = json.load(open(DATA))
    rows = [r for r in rows if r.get(field)] or rows
    rows.sort(key=lambda r: r["latency_ms"])
    return rows[:n]

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
                    open("/home/z/my-project/data/proxies/kimeta_sample.html", "w").write(html)
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
                    open("/home/z/my-project/data/proxies/stellenanzeigen_sample.html", "w").write(html)
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
                    open(f"/home/z/my-project/data/proxies/curlcffi_{name}_{imp}.html", "w").write(r.text)
                break
            except Exception as e:
                print(f"  {name:<16} impersonate={imp} -> ERR {type(e).__name__}: {str(e)[:60]}")

    # ---------- cloudscraper direct ----------
    print("=" * 70)
    import cloudscraper
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
