#!/usr/bin/env python3
"""CERTIFICATE-landscape scan across EVERY job corpus we hold.

Extends azure_demand_scan.py: instead of Azure-only flags this classifies
  (a) explicit vendor CERTIFICATE mentions (AZ-xxx, MD-102, MS/SC-xxx, MCSA/MCSE,
      AWS, GCP, CompTIA, CCNA/CCNP, ITIL, PRINCE2/PMP, LPIC, RHCSA, VCP, CKA,
      CEH, Fortinet NSE, SAP) with requirement-strength classification,
  (b) generic certification-willingness signal (Zertifizierung/Zertifikat/certification),
  (c) SKILL STACKS that map to certs (Windows Server, AD/Entra, M365/Intune,
      network+firewall vendors, security, virtualization, Docker/K8s, Linux,
      scripting, ITSM, SAP, backup, cloud, entry signals).

Corpora (same as azure_demand_scan.py):
  HIST — data/raw/erlangen_ALL_portals_20261017_1733.json
         (Indeed rows carry full text; LinkedIn rows are title-only)
  NOW  — data/enriched/jobs_enriched_20261030-0709.json (77 active postings);
         BA-family rows re-fetched live via the BA detail API, others via
         daily CSV snippet + title.

Outputs → data/azure_demand/: cert_scan_<ts>.json (per-job), cert_evidence_<ts>.csv,
cert_stats_<ts>.json. Prints a compact summary.
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

# ------------------------------------------------ explicit certificate patterns
CERTS = {
    "AZ-900 (Azure Fundamentals)":        r"\bAZ[-\s]?900\b",
    "AZ-104 (Azure Administrator)":       r"\bAZ[-\s]?104\b",
    "AZ-800/801 (Windows Server Hybrid)": r"\bAZ[-\s]?80[01]\b",
    "AZ-305 (Azure Solutions Architect)": r"\bAZ[-\s]?305\b",
    "AZ-500 (Azure Security)":            r"\bAZ[-\s]?500\b",
    "other AZ-xxx":                       r"\bAZ[-\s]?\d{3}\b",
    "MD-102 (M365 Endpoint Admin)":       r"\bMD[-\s]?102\b",
    "MS-900 (M365 Fundamentals)":         r"\bMS[-\s]?900\b",
    "other MS/SC-xxx":                    r"\b(?:MS|SC)[- ]?\d{3}\b",
    "MCSA/MCSE/MTA (legacy)":             r"\bMCSA\b|\bMCSE\b|\bMTA\b",
    "Microsoft Certified/Zertifizierung": r"Microsoft\s+(?:Certified|Zertifizier)",
    "AWS Certified (any)":                r"AWS\s+Certified|AWS\s+Zertifizier|Cloud\s+Practitioner|Solutions\s+Architect",
    "Google Cloud Certified":             r"Google\s+Cloud\s+Certified|Professional\s+Cloud\s+Architect",
    "CompTIA (any)":                      r"\bCompTIA\b|\bNetwork\s?\+\b|\bSecurity\s?\+\b",
    "CCNA/CCNP (Cisco)":                  r"\bCCNA\b|\bCCNP\b|\bCCENT\b",
    "ITIL":                               r"\bITIL\b",
    "PRINCE2/PMP":                        r"\bPRINCE2\b|\bPMP\b",
    "LPIC (Linux)":                       r"\bLPIC\b",
    "RHCSA/RHCE (Red Hat)":               r"\bRHCSA\b|\bRHCE\b|Red\s+Hat\s+Certified",
    "VCP (VMware)":                       r"\bVCP\b|VMware\s+Certified",
    "CKA/CKAD (Kubernetes)":              r"\bCKA\b|\bCKAD\b|Certified\s+Kubernetes",
    "CEH/OSCP (Security)":                r"\bCEH\b|\bOSCP\b",
    "Fortinet NSE":                       r"\bNSE\s?\d\b|Fortinet\s+(?:Zertifiz|Certified)",
    "SAP Certified":                      r"SAP\s+(?:Zertifiz|Certified)",
}
CERT_RX = {k: re.compile(v, re.I) for k, v in CERTS.items()}
GENERIC_CERT = re.compile(r"Zertifizierung(?:en)?|\bZertifikat(?:e|s)?\b|\bcertification\b", re.I)

# ------------------------------------------------ skill stacks (cert mapping)
SKILLS = {
    "windows_server": r"Windows\s+Server",
    "ad_entra":       r"Active\s+Directory|Entra\s+ID|Azure\s+AD",
    "m365_endpoint":  r"M365|Microsoft\s?365|Office\s?365|\bIntune\b|SCCM|Endpoint\s+Manager|Autopilot",
    "exchange":       r"\bExchange\b",
    "network":        r"Netzwerk|\bnetwork\b|TCP/?IP|Firewall|\bVPN\b|\bLAN\b|\bWLAN\b|Routing|Cisco|FortiGate|Fortinet|SonicWall|pfSense|Ubiquiti|Meraki|Juniper|MikroTik",
    "security":       r"IT-?Sicherheit|Informationssicherheit|IT-?Security|\bSecurity\b|Datenschutz|DSGVO|ISMS|ISO\s?27001|NIS\s?2",
    "virtualization": r"VMware|Proxmox|Hyper-V|Nutanix|Virtualisierung",
    "docker_k8s":     r"\bDocker\b|Kubernetes|\bK8s\b",
    "linux":          r"\bLinux\b|Debian|Ubuntu|RHEL|Red\s?Hat",
    "cloud_any":      r"\bcloud\b|\bAWS\b|\bazure\b|Google\s+Cloud|\bGCP\b|Cloudumgebung|Cloud-Technolog",
    "azure":          r"\bazure\b",
    "aws":            r"\bAWS\b|Amazon\s+Web\s+Services",
    "gcp":            r"\bGCP\b|Google\s+Cloud",
    "scripting":      r"PowerShell|Python|\bBash\b|Ansible|Automatisier",
    "itsm":           r"ITIL|ITSM|Ticketsystem|ServiceNow|\bJira\b|OTRS|GLPI|Service\s?Desk|Servicedesk",
    "sap":            r"\bSAP\b",
    "backup":         r"Backup|Veeam|Datensicher",
    "entry":          r"Ausbildung|Azubi|Berufseinsteiger|Berufseinstieg|\bEinstieg\b|\bJunior\b|keine\s+erfahrung|Erfahrung\s+nicht\s+erforderlich|Quereinsteiger",
}
SKILL_RX = {k: re.compile(v, re.I) for k, v in SKILLS.items()}

STRENGTH_REQ = re.compile(r"Voraussetzung|erforderlich|vorausgesetzt|wird\s+ben(?:ö|oe)tigt|setzen\s+wir\s+voraus|abgeschlossene", re.I)
STRENGTH_PLUS = re.compile(r"w(?:ü|ue)nschenswert|von\s+Vorteil|nice\s+to\s+have|\bBonus\b|erw(?:ü|ue)nscht|idealerweise|zus(?:ä|ae)tzlich|\bplus\b", re.I)

FISI_TITLE = re.compile(
    r"systemintegration|systemintegrator|systemadmin|it-?admin|administrator"
    r"|it-?support|\bsupport\b|sysadmin|it-?techniker|netzwerk|infrastruktur"
    r"|client|server|it-?betreuung|it-?operati|anwendungsbetreuer", re.I)


def sentences_with(text, rx, limit=2):
    out = []
    for s in re.split(r"(?<=[.!?\n;])\s+", text or ""):
        if rx.search(s):
            s = re.sub(r"\s+", " ", s).strip()
            if 20 < len(s) < 400:
                out.append(s)
            if len(out) >= limit:
                break
    return out


def classify(text, title=""):
    full = f"{title}\n{text or ''}"
    res = {}
    certs_hit, strength = [], {}
    for k, rx in CERT_RX.items():
        if rx.search(full):
            certs_hit.append(k)
            sents = sentences_with(text or title, rx, limit=1)
            s = sents[0] if sents else ""
            if STRENGTH_REQ.search(s):
                strength[k] = "required"
            elif STRENGTH_PLUS.search(s):
                strength[k] = "asset"
            else:
                strength[k] = "mentioned"
    res["certs_hit"] = certs_hit
    res["cert_strength"] = strength
    res["cert_evidence"] = {k: sentences_with(text or title, CERT_RX[k], limit=1)
                            for k in certs_hit}
    res["generic_cert_mention"] = bool(GENERIC_CERT.search(full))
    res["generic_cert_evidence"] = sentences_with(text or title, GENERIC_CERT, limit=1)
    for k, rx in SKILL_RX.items():
        res[k] = bool(rx.search(full))
        if k in ("network", "security", "itsm", "m365_endpoint", "azure") and res[k]:
            res[f"{k}_ev"] = sentences_with(text or title, rx, limit=1)
    res["fisi_title"] = bool(FISI_TITLE.search(title))
    return res


# ---------------------------------------------------------------- corpora
def load_hist():
    path = f"{BASE}/data/raw/erlangen_ALL_portals_20261017_1733.json"
    rows = json.load(open(path, encoding="utf-8"))
    seen, out = set(), []
    for r in rows:
        title = (r.get("title") or "").strip()
        company = (r.get("company") or "").strip()
        key = (title.lower(), company.lower())
        if key in seen:
            continue
        seen.add(key)
        desc = (r.get("description") or "").strip()
        cls = classify(desc, title)
        cls["corpus"] = "hist"
        cls["title"], cls["company"] = title, company
        cls["source"] = r.get("site") or r.get("source_site") or "?"
        cls["url"] = r.get("job_url") or ""
        cls["date_posted"] = r.get("date_posted") or ""
        cls["text_mode"] = "full" if desc else "title_only"
        out.append(cls)
    return out


def load_now():
    enr = json.load(open(f"{BASE}/data/enriched/jobs_enriched_20261030-0709.json",
                         encoding="utf-8"))
    snippets = {}
    csvp = (f"{BASE}/download/daily/2026-10-30/"
            "jobs_fachinformatiker-systemintegration-erlangen-50km-14d_20261030-0706.csv")
    for r in csv.DictReader(open(csvp, encoding="utf-8-sig")):
        snippets[r.get("url", "")] = r.get("snippet") or ""

    import enrich_jobs as ej  # proven BA fetch stack
    out, fetched, fetch_fail = [], 0, 0
    for row in enr:
        title = row.get("title") or ""
        url = row.get("url") or ""
        src = row.get("source") or ""
        text, mode = "", "snippet"
        if src.startswith("BA"):
            try:
                api_json, desc = ej.fetch_ba({"url": url})
                text = desc or ""
                if api_json and api_json.get("stellenangebotsBeschreibung"):
                    text = api_json["stellenangebotsBeschreibung"]
                mode, fetched = "ba_api_full", fetched + 1
            except Exception:
                fetch_fail += 1
        if not text:
            text = snippets.get(url) or snippets.get(row.get("original_url") or "") or ""
        cls = classify(text, title)
        cls["corpus"] = "now"
        cls["title"], cls["company"] = title, row.get("company_db") or ""
        cls["source"], cls["url"] = src, url
        cls["date_posted"] = row.get("date_posted") or ""
        cls["text_mode"] = mode
        out.append(cls)
    return out, fetched, fetch_fail


def rate(rows, flag):
    n = sum(1 for r in rows if r.get(flag))
    return n, (100.0 * n / len(rows) if rows else 0.0)


# ---------------------------------------------------------------- run
hist = load_hist()
now, ba_ok, ba_fail = load_now()
allrows = hist + now
hist_text = [r for r in hist if r["source"] == "indeed"]        # full-text baseline
hist_linkedin = [r for r in hist if r["source"] != "indeed"]    # title-only

stats = {"generated_utc": datetime.now(timezone.utc).isoformat(),
         "hist_total_unique": len(hist), "hist_text_indeed": len(hist_text),
         "hist_linkedin_title_only": len(hist_linkedin),
         "now_total": len(now), "now_ba_fulltext": ba_ok, "now_ba_fail": ba_fail}

for label, rows in [("hist_text", hist_text), ("now", now),
                    ("fisi_now", [r for r in now if r["fisi_title"]])]:
    b = stats[label] = {"n": len(rows)}
    for k in CERT_RX:
        b[f"cert::{k}"] = sum(1 for r in rows if k in r["certs_hit"])
    b["generic_cert_mention"] = sum(1 for r in rows if r["generic_cert_mention"])
    for k in SKILL_RX:
        b[f"skill::{k}"] = sum(1 for r in rows if r.get(k))

# strengths of explicit cert mentions (all corpora)
strength_ct = Counter()
for r in allrows:
    for k, s in r["cert_strength"].items():
        strength_ct[f"{k}::{s}"] += 1
stats["cert_strength_all_corpora"] = dict(strength_ct)

# example evidence for the report: explicit cert mentions + generic mentions
ex_certs, ex_generic = [], []
for r in allrows:
    if r["certs_hit"]:
        ex_certs.append({"corpus": r["corpus"], "title": r["title"], "company": r["company"],
                         "source": r["source"], "certs": r["certs_hit"],
                         "evidence": r["cert_evidence"], "url": r["url"]})
    elif r["generic_cert_mention"] and r["corpus"] == "now":
        ex_generic.append({"corpus": r["corpus"], "title": r["title"], "company": r["company"],
                           "source": r["source"], "evidence": r["generic_cert_evidence"],
                           "url": r["url"]})
stats["examples_explicit_certs"] = ex_certs
stats["examples_generic_cert_active"] = ex_generic[:40]

json.dump(allrows, open(f"{OUT}/cert_scan_{TS}.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
with open(f"{OUT}/cert_evidence_{TS}.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["corpus", "title", "company", "source", "certs", "strength",
                "evidence", "url"])
    for r in allrows:
        if r["certs_hit"] or r["generic_cert_mention"]:
            w.writerow([r["corpus"], r["title"], r["company"], r["source"],
                        "; ".join(r["certs_hit"]) or "(generic mention)",
                        "; ".join(f"{k}={v}" for k, v in r["cert_strength"].items()),
                        " | ".join(sum((r["cert_evidence"].get(k, [])
                                        for k in r["certs_hit"]), [])[:2])[:400]
                        or " | ".join(r["generic_cert_evidence"])[:400],
                        r["url"]])
json.dump(stats, open(f"{OUT}/cert_stats_{TS}.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- summary print
print(f"hist unique={len(hist)} (indeed-text={len(hist_text)}, "
      f"linkedin-title-only={len(hist_linkedin)})  now={len(now)} "
      f"(ba_full={ba_ok}, ba_fail={ba_fail})")
for label in ("hist_text", "now", "fisi_now"):
    b = stats[label]
    certs = {k.split("::")[1]: v for k, v in b.items()
             if k.startswith("cert::") and v > 0}
    skills = {k.split("::")[1]: v for k, v in b.items()
              if k.startswith("skill::") and v > 0}
    print(f"\n== {label} (n={b['n']}) ==")
    print(" certs>0 :", certs)
    print(" generic cert mention:", b["generic_cert_mention"],
          f"({100.0*b['generic_cert_mention']/b['n']:.1f}%)")
    print(" skills  :", {k: v for k, v in skills.items()})
print(f"\nfiles: cert_scan_{TS}.json / cert_evidence_{TS}.csv / cert_stats_{TS}.json in {OUT}")
