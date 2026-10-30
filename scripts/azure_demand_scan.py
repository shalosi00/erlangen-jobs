#!/usr/bin/env python3
"""Azure/cloud demand scan across EVERY job corpus we hold.

Corpora:
  HIST — data/raw/erlangen_ALL_portals_20261017_1733.json (Indeed rows carry full
         descriptions; LinkedIn rows arrive text-blocked and are counted but only
         title-classified)
  NOW  — data/enriched/jobs_enriched_20261030-0709.json (77 active postings);
         BA-family rows re-fetched live via the BA detail API for full text,
         others fall back to the daily CSV snippet + title.

Outputs (data/azure_demand/):
  azure_scan_<ts>.json   per-job classification (both corpora)
  azure_scan_<ts>.csv    evidence table for the report
  stats_<ts>.json        headline numbers consumed by the report generator
Prints a compact summary on stdout.
"""
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")

BASE = "/home/z/my-project"
OUT = f"{BASE}/data/azure_demand"
os.makedirs(OUT, exist_ok=True)
TS = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")

# ---------------------------------------------------------------- keyword sets
K = {
    "azure": re.compile(r"\bazure\b", re.I),
    "azure_cert": re.compile(r"AZ[- ]?9?0?0\b|AZ[- ]?104\b|AZ[- ]?800\b|AZ[- ]?140\b"
                             r"|AZ[- ]?700\b|MCSA|MCSE|Microsoft\s+Zertifiz", re.I),
    "cloud_any": re.compile(r"\bcloud\b|\bAWS\b|\bazure\b|Google\s+Cloud|\bGCP\b"
                            r"|OpenStack|Cloudumgebung|Cloud-Technolog", re.I),
    "ms_stack": re.compile(r"Windows\s+Server|Active\s+Directory|M365|Microsoft\s?365"
                           r"|\bIntune\b|\bExchange\b|SCCM|Hyper-V", re.I),
    "virt": re.compile(r"VMware|Proxmox|Hyper-V|VirtualBox|\bDocker\b|Kubernetes|Virtualisierung", re.I),
    "net": re.compile(r"Netzwerk|\bnetwork\b|TCP/?IP|Firewall|\bVPN\b|\bLAN\b|\bWLAN\b|Routing", re.I),
    "linux": re.compile(r"\bLinux\b|Debian|Ubuntu|RHEL|Red\s?Hat", re.I),
    "entry": re.compile(r"Ausbildung|Azubi|Berufseinsteiger|Berufseinstieg|\bEinstieg\b"
                        r"|\bJunior\b|keine\s+erfahrung|Erfahrung\s+nicht\s+erforderlich"
                        r"|Quereinsteiger", re.I),
    "req_lang": re.compile(r"Voraussetzung|Kenntnisse|Erfahrung\s+mit|wir\s+bieten", re.I),
}
FISI_TITLE = re.compile(
    r"systemintegration|systemintegrator|systemadmin|it-?admin|administrator"
    r"|it-?support|\bsupport\b|sysadmin|it-?techniker|netzwerk|infrastruktur"
    r"|client|server|it-?betreuung|it-?operati|anwendungsbetreuer", re.I)
CERT_FULLNAME = re.compile(r"Microsoft\s+Certified[:\s]+(Administrator|Fundamentals|"
                           r"Windows\s+Server\s+Hybrid|Azure)", re.I)


def sentences_with(text, rx, limit=2):
    out = []
    for s in re.split(r"(?<=[.!?\n;])\s+", text):
        if rx.search(s):
            s = re.sub(r"\s+", " ", s).strip()
            if 20 < len(s) < 400:
                out.append(s)
            if len(out) >= limit:
                break
    return out


def classify(text, title=""):
    """Return dict of keyword hits + evidence sentences (azure)."""
    full = f"{title}\n{text}"
    res = {k: bool(rx.search(full)) for k, rx in K.items()}
    res["fisi_title"] = bool(FISI_TITLE.search(title))
    res["cert_fullname"] = bool(CERT_FULLNAME.search(full))
    res["azure_evidence"] = sentences_with(text or title, K["azure"])
    res["req_evidence"] = sentences_with(text or title, K["azure_cert"]) if res["azure_cert"] else []
    return res


# ---------------------------------------------------------------- HIST corpus
def load_hist():
    path = f"{BASE}/data/raw/erlangen_ALL_portals_20261017_1733.json"
    rows = json.load(open(path, encoding="utf-8"))
    seen, out, nolinkedin_desc = set(), [], 0
    for r in rows:
        title = (r.get("title") or "").strip()
        company = (r.get("company") or "").strip()
        key = (title.lower(), company.lower())
        if key in seen:
            continue
        seen.add(key)
        desc = (r.get("description") or "").strip()
        if not desc:
            nolinkedin_desc += 1
        cls = classify(desc, title)
        cls["corpus"] = "hist"
        cls["title"], cls["company"] = title, company
        cls["source"] = r.get("site") or r.get("source_site") or "?"
        cls["url"] = r.get("job_url") or ""
        cls["date_posted"] = r.get("date_posted") or ""
        cls["experience_range"] = r.get("experience_range") or ""
        cls["job_level"] = r.get("job_level") or ""
        out.append(cls)
    return out, nolinkedin_desc


# ---------------------------------------------------------------- NOW corpus
def load_now():
    enr = json.load(open(f"{BASE}/data/enriched/jobs_enriched_20261030-0709.json",
                         encoding="utf-8"))
    snippets = {}
    csvp = (f"{BASE}/download/daily/2026-10-30/"
            "jobs_fachinformatiker-systemintegration-erlangen-50km-14d_20261030-0706.csv")
    for r in csv.DictReader(open(csvp, encoding="utf-8-sig")):
        snippets[r.get("url", "")] = r.get("snippet") or ""

    import enrich_jobs as ej  # reuse the proven fetch stack
    out, fetched, fetch_fail = [], 0, 0
    for row in enr:
        title = row.get("title") or ""
        url = row.get("url") or ""
        src = row.get("source") or ""
        text = ""
        mode = "snippet"
        if src.startswith("BA"):
            try:
                api_json, desc = ej.fetch_ba({"url": url})
                text = desc or ""
                if api_json and api_json.get("stellenangebotsBeschreibung"):
                    text = api_json["stellenangebotsBeschreibung"]
                mode = "ba_api_full"
                fetched += 1
            except Exception:
                fetch_fail += 1
        if not text:
            text = snippets.get(url) or snippets.get(row.get("original_url") or "") or ""
        cls = classify(text, title)
        cls["corpus"] = "now"
        cls["title"], cls["company"] = title, row.get("company_db") or ""
        cls["source"], cls["url"] = src, url
        cls["date_posted"] = row.get("date_posted") or ""
        cls["experience_range"] = ""
        cls["job_level"] = row.get("experience_class_t22") or ""
        cls["text_mode"] = mode
        out.append(cls)
    return out, fetched, fetch_fail


# ---------------------------------------------------------------- run
hist, hist_nodesc = load_hist()
now, ba_ok, ba_fail = load_now()
allrows = hist + now

for r in allrows:
    r["azure"] = r.get("azure", False)

def rate(rows, flag):
    n = sum(1 for r in rows if r.get(flag))
    return n, (100.0 * n / len(rows) if rows else 0.0)

hist_full = [r for r in hist if r.get("text_mode", "full") == "full" or r["corpus"] == "hist"
             and (r.get("azure_evidence") or True)]
# text-bearing hist rows only (Indeed); LinkedIn hist rows = title-only
hist_text = [r for r in hist if not (r["source"] == "linkedin" and not r.get("azure_evidence")
             and not r.get("ms_stack") and not r.get("cloud_any"))]
hist_text = [r for r in hist if r["source"] == "indeed"]

stats = {}
stats["generated_utc"] = datetime.now(timezone.utc).isoformat()
stats["hist_total_unique"] = len(hist)
stats["hist_nodesc_linkedin"] = hist_nodesc
stats["hist_text_indeed"] = len(hist_text)
stats["now_total"] = len(now)
stats["now_ba_fulltext"] = ba_ok
stats["now_ba_fail"] = ba_fail

for label, rows in [("hist", hist_text), ("now", now), ("all", allrows)]:
    stats[label] = {}
    for flag in ["azure", "azure_cert", "cloud_any", "ms_stack", "virt", "net",
                 "linux", "entry", "fisi_title", "cert_fullname"]:
        n, pct = rate(rows, flag)
        stats[label][flag] = {"n": n, "pct": round(pct, 1)}
    # cross-tabs
    a = [r for r in rows if r.get("azure")]
    stats[label]["azure_x_fisi"] = {
        "azure_and_fisi": sum(1 for r in a if r.get("fisi_title")),
        "fisi_total": sum(1 for r in rows if r.get("fisi_title")),
        "azure_within_fisi_pct": round(100.0 * sum(1 for r in rows
                                       if r.get("azure") and r.get("fisi_title"))
                                       / max(1, sum(1 for r in rows if r.get("fisi_title"))), 1)}
    stats[label]["azure_x_entry"] = {
        "azure_and_entry": sum(1 for r in a if r.get("entry")),
        "entry_within_azure_pct": round(100.0 * sum(1 for r in a if r.get("entry"))
                                        / max(1, len(a)), 1)}
    stats[label]["cloud_not_azure"] = sum(1 for r in rows
                                          if r.get("cloud_any") and not r.get("azure"))
    stats[label]["ms_stack_not_azure"] = sum(1 for r in rows
                                             if r.get("ms_stack") and not r.get("azure"))

# sources of NOW azure hits
stats["now_azure_by_source"] = dict(Counter(r["source"] for r in now if r.get("azure")))
# experience_range fill on hist azure hits
exp = Counter((r.get("experience_range") or "?") for r in hist_text if r.get("azure"))
stats["hist_azure_experience_range"] = dict(exp.most_common(8))

json.dump(allrows, open(f"{OUT}/azure_scan_{TS}.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
with open(f"{OUT}/azure_scan_{TS}.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["corpus", "title", "company", "source", "azure", "azure_cert",
                "cloud_any", "ms_stack", "entry", "fisi_title", "url", "evidence"])
    for r in allrows:
        if r.get("azure") or r.get("cloud_any") or r.get("azure_cert"):
            w.writerow([r["corpus"], r["title"], r["company"], r["source"],
                        int(r.get("azure", 0)), int(r.get("azure_cert", 0)),
                        int(r.get("cloud_any", 0)), int(r.get("ms_stack", 0)),
                        int(r.get("entry", 0)), int(r.get("fisi_title", 0)),
                        r["url"], " | ".join(r.get("azure_evidence") or [])[:500]])
json.dump(stats, open(f"{OUT}/stats_{TS}.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- print
print(json.dumps(stats, ensure_ascii=False, indent=1))
print(f"\nfiles: azure_scan_{TS}.json / .csv / stats_{TS}.json in {OUT}")
