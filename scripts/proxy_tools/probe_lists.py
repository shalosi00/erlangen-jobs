#!/usr/bin/env python3
"""Probe candidate free-proxy list repos: confirm raw URLs live + format."""
import concurrent.futures as cf
import requests

CANDIDATES = {
    # name -> (protocol, raw_url)
    "TheSpeedX/PROXY-List": [
        ("http",   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
        ("socks4", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt"),
        ("socks5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
    ],
    "monosans/proxy-list": [
        ("http",   "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"),
        ("socks4", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt"),
        ("socks5", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt"),
        ("meta",   "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/main.json"),
    ],
    "proxifly/free-proxy-list": [
        ("http",   "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt"),
        ("https",  "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt"),
        ("socks4", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt"),
        ("socks5", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt"),
        ("json",   "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/all/data.json"),
    ],
    "roosterkid/openproxylist": [
        ("http",   "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt"),
        ("socks4", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt"),
        ("socks5", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt"),
    ],
    "zloi-user/hideip.me": [
        ("http",   "https://raw.githubusercontent.com/zloi-user/hideip.me/master/http.txt"),
        ("https",  "https://raw.githubusercontent.com/zloi-user/hideip.me/master/https.txt"),
        ("socks4", "https://raw.githubusercontent.com/zloi-user/hideip.me/master/socks4.txt"),
        ("socks5", "https://raw.githubusercontent.com/zloi-user/hideip.me/master/socks5.txt"),
    ],
    "mmpx12/proxy-list": [
        ("http",   "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt"),
        ("socks4", "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt"),
        ("socks5", "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt"),
    ],
    "gfpcom/free-proxy-list": [
        ("http",   "https://raw.githubusercontent.com/gfpcom/free-proxy-list/master/http.txt"),
        ("socks4", "https://raw.githubusercontent.com/gfpcom/free-proxy-list/master/socks4.txt"),
        ("socks5", "https://raw.githubusercontent.com/gfpcom/free-proxy-list/master/socks5.txt"),
    ],
    "Zaeem20/FREE_PROXIES_LIST": [
        ("http",   "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt"),
    ],
    "clarketm/proxy-list": [
        ("mixed",  "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"),
    ],
    "hookzof/socks5_list": [
        ("socks5", "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxies.txt"),
    ],
    "MuRongPIG/Proxy-Master": [
        ("http",   "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt"),
        ("socks4", "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt"),
        ("socks5", "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt"),
    ],
    "ShiftyTR/Proxy-List": [
        ("http",   "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"),
    ],
    "jetkai/proxy-list": [
        ("json",   "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/json/proxies.json"),
    ],
}

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

def probe(item):
    repo, (proto, url) = item
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.status_code != 200:
            return repo, proto, url, f"HTTP {r.status_code}", 0, ""
        lines = [l.strip() for l in r.text.splitlines() if l.strip()]
        sample = lines[0][:90] if lines else ""
        return repo, proto, url, "OK", len(lines), sample
    except Exception as e:
        return repo, proto, url, f"ERR {type(e).__name__}: {str(e)[:60]}", 0, ""

def main():
    tasks = [(repo, it) for repo, lst in CANDIDATES.items() for it in lst]
    results = {}
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for repo, proto, url, status, n, sample in ex.map(probe, tasks):
            results.setdefault(repo, []).append((proto, status, n, sample, url))
    for repo, rows in results.items():
        print(f"\n### {repo}")
        for proto, status, n, sample, url in rows:
            print(f"  [{proto:>6}] {status:<22} lines={n:<6} sample: {sample}")

if __name__ == "__main__":
    main()
