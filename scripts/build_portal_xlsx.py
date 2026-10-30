#!/usr/bin/env python3
"""build_portal_xlsx.py — German job-portal catalog workbook (xlsx skill compliant).
Sheets: Übersicht | Master | Live & erntbar | Blockiert & legacy | Integrationsplan | Review
"""
import json, sys, os
from datetime import datetime

SKILL = "/home/z/my-project/skills/xlsx"
for p in (SKILL, os.path.join(SKILL, "templates")):
    if p not in sys.path:
        sys.path.insert(0, p)
from base import *  # design tokens + helpers
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

SRC = "/home/z/my-project/data/portals/portal_scan_final_20261030-1716.json"
OUT = "/home/z/my-project/download/jobportals_deutschland_2026-10-31.xlsx"

data = json.load(open(SRC))["results"]
rows = [dict(name=r["name"], url=r.get("final_url") or r["url"], url0=r["url"], cat=r["category"],
             status=r["status"], http=r.get("http", 0), title=r.get("title", ""),
             hint=r.get("access_hint", ""), pipe=r.get("in_pipeline", "no"),
             note=r.get("note", ""), via=r.get("via_proxy", "")) for r in data]

DE = {"OK": "OK direkt", "OK-VIA-PROXY": "OK via Proxy", "JS-SHELL": "JS-Browser",
      "BLOCKED-STRICT": "WAF blockiert", "CONN-ERR": "Verbindungsfehler", "SSL-ERR": "SSL-Fehler",
      "TIMEOUT": "Timeout", "HTTP-404": "404 tot", "HTTP-406": "406 abgelehnt"}
for r in rows:
    r["de"] = DE.get(r["status"], r["status"])
LIVE = {"OK", "OK-VIA-PROXY", "JS-SHELL"}
CAT_DE = {"generalist": "Generalist", "public": "Öffentlich/Behörde", "tech": "Tech/IT",
          "freelance": "Freelance", "junior": "Junior/Ausbildung", "regional": "Regional",
          "aggregator": "Aggregator/Meta", "staffing": "Zeitarbeit", "niche": "Branchen-Nische",
          "english": "Englisch/Expat", "remote": "Remote", "ats": "ATS-Direktfeeds", "misc": "Sonstige"}
API_NOTE = {
    "Jooble DE": "Offizielle API mit kostenlosem Key verfügbar -> 1. Wahl statt Scraping",
    "Adzuna DE": "Offizielle API (app_id/app_key, kostenlos) -> 1. Wahl statt Scraping",
    "Careerjet DE": "Affiliate-Suche-API mit Key -> 1. Wahl statt Scraping",
    "Talent.com DE": "Partner-API verfügbar; Scraping OK direkt",
    "WhatJobs DE": "API-Angebot vorhanden; Scraping OK direkt",
    "RemoteOK": "Öffentliche JSON-API: remoteok.com/api",
    "Remotive": "Öffentliche JSON-API: remotive.com/api/remote-jobs",
    "kimeta.de": "In früheren Sessions via Proxy-Pool erfolgreich geerntet; Pool auffrischen",
    "Stellenanzeigen.de": "In früheren Sessions via Proxy-Pool erfolgreich geerntet; Pool auffrischen",
    "meinestadt.de Jobs": "In früheren Sessions via Proxy-Pool erfolgreich geerntet; Pool auffrischrefresh",
    "Indeed DE": "Bewährt: mobiler/guest-Endpunkt + Proxy-Rotation (1.977 Postings im Speicher)",
    "LinkedIn Jobs": "Bewährt: Guest-API mit Drossel (1.848 Postings im Speicher)",
    "EURES": None,  # handled separately (live)
    "Ashby": "Marketingseite blockiert; Feed api.ashbyhq.com/posting-api/job-board/{org} bleibt nutzbar",
    "Workable": "Marketingseite blockiert; Feed apply.workable.com/api/v1/widget/accounts/{org}/jobs bleibt nutzbar",
    "Personio feeds": "Marketingseite via Proxy OK; Firmen-Feeds {co}.jobs.personio.de/xml direkt nutzbar",
    "Greenhouse boards": "Feed boards.greenhouse.io/v1/boards/{org}/jobs ohne Key nutzbar",
    "Lever": "Feed api.lever.co/v0/postings/{org} ohne Key nutzbar",
    "SmartRecruiters": "Feed jobs.smartrecruiters.com/v1/companies/{id}/postings ohne Key nutzbar",
    "Monster DE": "Nach Monster/CareerBuilder-Merger fraglich; Status prüfen",
    "Stack Overflow Jobs": "Eingestellt; nur noch Legacy-Zweigstelle",
    "Joblift": "Meta-Suche ca. 2023 eingestellt",
    "Kalaydo Jobs": "Legacy-Portal, weitgehend eingestellt",
    "Jobninja": "Status unklar (WAF)",
}
for r in rows:
    if r["name"] in API_NOTE and API_NOTE[r["name"]]:
        r["note"] = (r["note"] + " | " if r["note"] else "") + API_NOTE[r["name"]]

STATUS_COLOR = {"OK direkt": ACCENT_POSITIVE, "OK via Proxy": ACCENT_POSITIVE,
                "JS-Browser": ACCENT_WARNING, "WAF blockiert": ACCENT_NEGATIVE}
CAT_PRIO = {"public": "Hoch", "tech": "Hoch", "junior": "Hoch", "regional": "Hoch",
            "generalist": "Hoch", "staffing": "Hoch", "aggregator": "Mittel",
            "freelance": "Mittel", "niche": "Mittel", "english": "Mittel", "ats": "Mittel",
            "remote": "Niedrig", "misc": "Niedrig"}
METHOD = {"OK": "direkt scrapen / API", "OK-VIA-PROXY": "Proxy-Pool",
          "JS-SHELL": "Headless-Browser", "BLOCKED-STRICT": "API-Key prüfen / Proxy frisch",
          "CONN-ERR": "-", "SSL-ERR": "-", "TIMEOUT": "-", "HTTP-404": "-", "HTTP-406": "-"}

wb = Workbook()

def style_status(ws, col_letter, row):
    c = ws[f"{col_letter}{row}"]
    col = STATUS_COLOR.get(c.value)
    if col:
        c.font = Font(name=FONT_NAME, size=11, color=col)

# ---------- Sheet 1: Übersicht ----------
ws = wb.active
ws.title = "Übersicht"
n = len(rows)
cnt = {}
for r in rows:
    cnt[r["de"]] = cnt.get(r["de"], 0) + 1
live_n = sum(v for k, v in cnt.items() if k in ("OK direkt", "OK via Proxy", "JS-Browser"))
headers1 = ["Kategorie", "Portale", "Live direkt", "Live via Proxy", "JS-Browser", "Blockiert", "Tot/Fehler"]
cats = sorted({r["cat"] for r in rows})
last_col = len(headers1) + 1
setup_sheet(ws, title=f"Jobportale Deutschland - Katalog & Live-Scan ({datetime.now().strftime('%d.%m.%Y')})", last_col=last_col)
ws["B3"] = f"{n} Portale identifiziert, live geprüft (direkt, Retry-Phase, Proxy-Pool). Live erreichbar: {live_n}."
ws["B3"].font = font_caption()
for c, h in enumerate(headers1, 2):
    ws.cell(row=4, column=c, value=h)
style_header_row(ws, row_num=4, col_start=2, col_end=last_col)
ri = 0
tot = [0] * 5
for cat in cats:
    sub = [r for r in rows if r["cat"] == cat]
    ok = sum(1 for r in sub if r["status"] == "OK")
    vp = sum(1 for r in sub if r["status"] == "OK-VIA-PROXY")
    js = sum(1 for r in sub if r["status"] == "JS-SHELL")
    bl = sum(1 for r in sub if r["status"] == "BLOCKED-STRICT")
    de = len(sub) - ok - vp - js - bl
    vals = [CAT_DE[cat], len(sub), ok, vp, js, bl, de]
    for c, v in enumerate(vals, 2):
        ws.cell(row=5 + ri, column=c, value=v)
    style_data_row(ws, row_num=5 + ri, col_start=2, col_end=last_col, row_index=ri)
    for c in range(3, last_col + 1):
        ws.cell(row=5 + ri, column=c).alignment = align_number()
    tot = [a + b for a, b in zip(tot, vals[1:])]
    ri += 1
ws.cell(row=5 + ri, column=2, value="Summe")
for c, v in enumerate(tot, 3):
    ws.cell(row=5 + ri, column=c, value=v)
    ws.cell(row=5 + ri, column=c).alignment = align_number()
style_total_row(ws, row_num=5 + ri, col_start=2, col_end=last_col)
note_r = 5 + ri + 2
notes = ["Methode: HTTP-Probe aller Portale (UA Chrome, Retry + 49-köpfiger Proxy-Pool aus validated_proxies.json).",
         "Quellen: Web-Recherche (connexion-emploi.com Portal-Übersicht 10/2026, jobboersencheck.de, haufe.de) + Bestands-Pipeline (mega_sweep, probe_aggregators r1-r7).",
         "Scan-Artefakte: data/portals/portal_scan_20261030-1703.json (Runde 1), portal_scan_final_20261030-1716.json (final)."]
for i, t in enumerate(notes):
    ws.cell(row=note_r + i, column=2, value=t).font = font_caption()
auto_fit_columns(ws, min_width=8, max_width=30, header_row=4, data_start_row=5)

# ---------- Sheet 2: Master ----------
ws2 = wb.create_sheet("Master")
h2 = ["#", "Portal", "URL", "Kategorie", "Status", "HTTP", "Erkannter Seitentitel", "Zugang", "In Pipeline", "Hinweis"]
setup_sheet(ws2, title=f"Master-Katalog: {n} deutsche Jobportale", last_col=len(h2) + 1)
for c, h in enumerate(h2, 2):
    ws2.cell(row=4, column=c, value=h)
style_header_row(ws2, row_num=4, col_start=2, col_end=len(h2) + 1)
order = {"generalist": 0, "public": 1, "tech": 2, "junior": 3, "regional": 4, "aggregator": 5,
         "staffing": 6, "niche": 7, "freelance": 8, "english": 9, "remote": 10, "ats": 11, "misc": 12}
rows_sorted = sorted(rows, key=lambda r: (order[r["cat"]], r["de"] != "OK direkt", r["name"]))
for i, r in enumerate(rows_sorted):
    rn = 5 + i
    vals = [i + 1, r["name"], r["url0"], CAT_DE[r["cat"]], r["de"], r["http"] or "-", r["title"] or "-",
            METHOD[r["status"]], r["pipe"], r["note"] or "-"]
    for c, v in enumerate(vals, 2):
        ws2.cell(row=rn, column=c, value=v)
    style_data_row(ws2, row_num=rn, col_start=2, col_end=len(h2) + 1, row_index=i)
    style_status(ws2, "F", rn)
    ws2.cell(row=rn, column=2).alignment = align_number()
    ws2.cell(row=rn, column=7).alignment = align_number()
ws2.freeze_panes = "D5"
auto_fit_columns(ws2, min_width=6, max_width=42, header_row=4, data_start_row=5)
master_last = 5 + len(rows_sorted) - 1

# ---------- Sheet 3: Live & erntbar ----------
ws3 = wb.create_sheet("Live & erntbar")
live = [r for r in rows_sorted if r["status"] in LIVE]
h3 = ["#", "Kategorie", "Portal", "URL", "Erreichbarkeit", "Ernte-Methode", "FISI-Priorität"]
setup_sheet(ws3, title=f"Live erreichbar: {len(live)} Portale - Ernte-Bereitschaft", last_col=len(h3) + 1)
for c, h in enumerate(h3, 2):
    ws3.cell(row=4, column=c, value=h)
style_header_row(ws3, row_num=4, col_start=2, col_end=len(h3) + 1)
for i, r in enumerate(live):
    rn = 5 + i
    vals = [i + 1, CAT_DE[r["cat"]], r["name"], r["url0"], r["de"], METHOD[r["status"]], CAT_PRIO[r["cat"]]]
    for c, v in enumerate(vals, 2):
        ws3.cell(row=rn, column=c, value=v)
    style_data_row(ws3, row_num=rn, col_start=2, col_end=len(h3) + 1, row_index=i)
    style_status(ws3, "F", rn)
    ws3.cell(row=rn, column=2).alignment = align_number()
ws3.freeze_panes = "E5"
auto_fit_columns(ws3, min_width=6, max_width=42, header_row=4, data_start_row=5)

# ---------- Sheet 4: Blockiert & legacy ----------
ws4 = wb.create_sheet("Blockiert & legacy")
dead = [r for r in rows_sorted if r["status"] not in LIVE]
h4 = ["#", "Portal", "URL", "Kategorie", "Status", "Vermutliche Ursache", "Option"]
setup_sheet(ws4, title=f"Blockiert / stillgelegt: {len(dead)} Portale", last_col=len(h4) + 1)
for c, h in enumerate(h4, 2):
    ws4.cell(row=4, column=c, value=h)
style_header_row(ws4, row_num=4, col_start=2, col_end=len(h4) + 1)
CAUSE = {"WAF blockiert": "Cloudflare/WAF blockiert Datacenter-IP (auch via 4 Proxies)",
         "Verbindungsfehler": "Verbindung abgelehnt - stillgelegt oder IP-Sperre",
         "SSL-Fehler": "Zertifikats-/TLS-Problem",
         "Timeout": "Server antwortet nicht",
         "404 tot": "Pfad/Portal nicht mehr vorhanden",
         "406 abgelehnt": "Server lehnt Client-Fingerprint ab",
         "JS-Browser": "JavaScript-App ohne serverseitiges HTML"}
for i, r in enumerate(dead):
    rn = 5 + i
    opt = ("API-Key (kostenlos) nutzen" if any(k in r["name"] for k in ("Jooble", "Adzuna", "Careerjet"))
           else "Proxy-Pool auffrischen + erneut versuchen" if r["status"] == "WAF blockiert"
           else "Headless-Browser nutzen" if r["status"] == "JS-SHELL"
           else "keine - überspringen")
    vals = [i + 1, r["name"], r["url0"], CAT_DE[r["cat"]], r["de"], CAUSE[r["de"]], opt]
    for c, v in enumerate(vals, 2):
        ws4.cell(row=rn, column=c, value=v)
    style_data_row(ws4, row_num=rn, col_start=2, col_end=len(h4) + 1, row_index=i)
    style_status(ws4, "F", rn)
    ws4.cell(row=rn, column=2).alignment = align_number()
ws4.freeze_panes = "D5"
auto_fit_columns(ws4, min_width=6, max_width=42, header_row=4, data_start_row=5)

# ---------- Sheet 5: Integrationsplan ----------
ws5 = wb.create_sheet("Integrationsplan")
h5 = ["Prio", "Portal/Feed", "Warum (FISI/Junior-Bezug)", "Methode", "Aufwand", "Nächster Schritt"]
setup_sheet(ws5, title="Integrationsplan: Empfohlene neue Quellen für die Daily-Pipeline", last_col=len(h5) + 1)
for c, h in enumerate(h5, 2):
    ws5.cell(row=4, column=c, value=h)
style_header_row(ws5, row_num=4, col_start=2, col_end=len(h5) + 1)
PLAN = [
 ("1", "Get in IT + Get in Engineering", "Junior/Graduate-Fokus - exakt die Zielgruppe; schon im Corpus bewährt", "HTML direkt", "niedrig", "in daily pull aufnehmen"),
 ("2", "XING Jobs", "Zweites großes DACH-Netz neben LinkedIn; viele FISI-Quereinsteiger-Anzeigen", "Headless-Browser / OAuth-API", "mittel", "Browser-Flow mit agent-browser testen"),
 ("3", "Jobware", "Spezialisten/Mittelstand, serverseitig gerendert - gut scrapbar", "HTML direkt", "niedrig", "Suche 'Fachinformatiker' + Region BY anbinden"),
 ("4", "SZ Jobs (Süddeutsche)", "Bayerischer Fokus - passt zu Erlangen/Nürnberg", "HTML direkt", "niedrig", "Search-URL-Pattern ermitteln"),
 ("5", "FAZJOB.NET", "faz.net-Stellenmarkt; redirect auf stellenmarkt.faz.net", "HTML direkt", "niedrig", "Search-URL-Pattern ermitteln"),
 ("6", "ZEIT Jobs", "Breites Spektrum inkl. IT/junior", "HTML direkt", "niedrig", "Search-URL-Pattern ermitteln"),
 ("7", "Stellenmarkt.de + Jobworld", "Klassische Börsen, direkt erreichbar", "HTML direkt", "niedrig", "paginierte Suche anbinden"),
 ("8", "Interamt", "Öffentlicher Dienst Bund - IT-Rollen (Ordnungsamt-IT, Systemintegration)", "HTML direkt", "niedrig", "Suche nach 'IT' + Bayern"),
 ("9", "Stellenwerk + academics.de", "Uni-Börsen (FAU Erlangen-Nürnberg!) - Werkstudent/Junior", "HTML direkt", "niedrig", "stellenwerk-FAU-Teilboard suchen"),
 ("10", "ITsax.de + ITmitte.de + Joberty", "IT-Nischenbörsen, direkt erreichbar", "HTML direkt", "niedrig", "IT-Suche anbinden"),
 ("11", "Absolventa + ausbildung.de + IHK-Lehrstellen", "Junior/Ausbildung - Kernfilter des Mega-Search", "HTML direkt", "niedrig", "in daily pull aufnehmen"),
 ("12", "Talent.com + Jobijoba + WhatJobs", "Aggregatoren mit großem Volumen, direkt scrapbar", "HTML direkt", "niedrig", "Search-Patterns + Dedupe gegen history.db"),
 ("13", "Zeitarbeit: Adecco/Hays/DIS/Hofmann/Amadeus/persona/Manpower", "Hohes FISI-Volumen (auch entry); Direktbewerbung möglich", "HTML/JS gemischt", "mittel", "HTML-fähige zuerst (Manpower, Hofmann, Amadeus, persona)"),
 ("14", "Jooble/Adzuna/Careerjet APIs", "Offizielle APIs (kostenloser Key) statt Scraping - stabile Langzeitquelle", "REST-API", "mittel", "Keys registrieren (Jooble, Adzuna, Careerjet)"),
 ("15", "ATS-Feeds: Greenhouse/Lever/Ashby/Personio/SmartRecruiters", "Direktarbeitgeber OHNE Vermittler - exakt Task-24-Ziel (Original-Arbeitgeber, keine Zeitarbeit)", "öffentliche JSON/XML-Feeds", "mittel", "DE-Firmenliste sammeln (Repos: sitemap-Harvest)"),
 ("16", "EURES", "Offizielle EU-Jobsuche, JSON-Suche", "REST/POST-JSON", "mittel", "Endpoint aus priorer Session wieder verwenden"),
 ("17", "kimeta + meinestadt + stellenanzeigen", "Große Aggregatoren - bewährt via Proxy-Pool", "HTML via Proxy-Pool", "mittel", "Pool validieren (validated_proxies.json 4 Tage alt)"),
 ("18", "RemoteOK/Remotive/Jobicy APIs", "Remote-IT; Remotive+RemoteOK haben öffentliche APIs", "REST-API", "niedrig", "optional ergänzen"),
]
for i, row in enumerate(PLAN):
    rn = 5 + i
    for c, v in enumerate(row, 2):
        ws5.cell(row=rn, column=c, value=v)
    style_data_row(ws5, row_num=rn, col_start=2, col_end=len(h5) + 1, row_index=i)
    ws5.cell(row=rn, column=2).alignment = align_number()
auto_fit_columns(ws5, min_width=6, max_width=48, header_row=4, data_start_row=5)

# ---------- Sheet 6: Review ----------
ws6 = wb.create_sheet("Review")
ws6.sheet_properties.tabColor = "FFC000"
checks = [["Check", "Erwartet", "Tatsächlich", "Status"],
          ["Portale gesamt", n, f"=COUNTA(Master!C5:C{master_last})", '=IF(B2=C2,"PASS","FAIL")'],
          ["Live direkt", cnt.get("OK direkt", 0), f'=COUNTIF(Master!F5:F{master_last},"OK direkt")', '=IF(B3=C3,"PASS","FAIL")'],
          ["Live via Proxy", cnt.get("OK via Proxy", 0), f'=COUNTIF(Master!F5:F{master_last},"OK via Proxy")', '=IF(B4=C4,"PASS","FAIL")'],
          ["JS-Browser", cnt.get("JS-Browser", 0), f'=COUNTIF(Master!F5:F{master_last},"JS-Browser")', '=IF(B5=C5,"PASS","FAIL")'],
          ["WAF blockiert", cnt.get("WAF blockiert", 0), f'=COUNTIF(Master!F5:F{master_last},"WAF blockiert")', '=IF(B6=C6,"PASS","FAIL")'],
          ["Live-Sheet Zeilen", len(live), f"=COUNTA('Live & erntbar'!C5:C{4 + len(live)})", '=IF(B7=C7,"PASS","FAIL")']]
for i, row in enumerate(checks, 1):
    for j, val in enumerate(row, 1):
        ws6.cell(row=i, column=j, value=val)
for j in range(1, 5):
    ws6.cell(row=1, column=j).font = font_header()

wb.properties.creator = "Z.ai"
wb.save(OUT)
print(f"saved {OUT}; portals={n}, live={len(live)}, dead={len(dead)}")
print("counts:", cnt)
