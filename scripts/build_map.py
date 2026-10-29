#!/usr/bin/env python3
"""build_map.py — turn the geocoded final CSV into a self-contained interactive map.

Outputs (default under map/):
  index.html      fully self-contained Leaflet map (data embedded inline, works
                  from file:// or GitHub Pages; only Leaflet/tiles come from CDN)
  jobs.geojson    per-job FeatureCollection (1 feature per row, full properties)

Aggregation: rows sharing the same (company, lat, lon) become ONE marker whose
popup lists all of that employer's jobs. Marker color = source portal.

Usage:
  python3 scripts/build_map.py                      # newest geocoded final CSV
  python3 scripts/build_map.py --input download/erlangen_jobs_final_20261018_geo.csv
  python3 scripts/build_map.py --outdir map --title "Erlangen Job Corridor"
"""
import argparse, csv, datetime, html, json, math, os, re, sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PORTAL_COLORS = {
    "indeed": "#2f6fd6", "stepstone": "#12b886", "linkedin": "#0a84c1",
    "xing": "#00857a", "arbeitsagentur": "#f59f00", "bundesagentur": "#f59f00",
    "interamt": "#e8590c", "glassdoor": "#0caa41", "ziprecruiter": "#2f9e44",
    "bayern": "#9775fa", "monster": "#6f42c1",
}
_FALLBACK = ["#4dabf7", "#ffa94d", "#69db7c", "#f783ac", "#e599f7", "#ffc078", "#a9e34b"]

def portal_color(name, used=0):
    n = (name or "").lower()
    for k, c in PORTAL_COLORS.items():
        if k in n:
            return c
    return _FALLBACK[used % len(_FALLBACK)]

def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def latest_geo_csv():
    cands = sorted(f for f in os.listdir(os.path.join(BASE, "download"))
                   if f.startswith("erlangen_jobs_final_") and f.endswith(".csv")
                   and "_part" not in f)
    geo = [f for f in cands if "_geo" in f] or cands
    if not geo:
        sys.exit("no erlangen_jobs_final_*.csv found in download/")
    return os.path.join(BASE, "download", geo[-1])

# ------------------------------------------------------------------ aggregate
_PRETTY = {"indeed": "Indeed", "linkedin": "LinkedIn", "stepstone": "Stepstone",
           "xing": "XING", "glassdoor": "Glassdoor", "arbeitsagentur": "Arbeitsagentur"}

def pretty_portal(p):
    core = p[len("jobspy-"):] if p.startswith("jobspy-") else p
    return _PRETTY.get(core.lower(), core)

def aggregate(rows):
    """Group rows by (company, lat, lon) -> list of marker dicts."""
    groups = defaultdict(list)
    skipped = 0
    for r in rows:
        try:
            lat, lon = float(r.get("lat") or ""), float(r.get("lon") or "")
        except ValueError:
            skipped += 1
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            skipped += 1
            continue
        groups[(r.get("company") or "?", round(lat, 6), round(lon, 6))].append(r)

    markers = []
    for (company, lat, lon), rs in groups.items():
        rs.sort(key=lambda r: (r.get("date_posted") or "", ), reverse=True)
        n = len(rs)
        portal_names = Counter(pretty_portal(r.get("source_portal") or "unknown") for r in rs)
        main_portal = portal_names.most_common(1)[0][0]
        color = portal_color(main_portal, len(markers))
        address = (rs[0].get("company_address") or "").strip()
        precision = (rs[0].get("geo_precision") or "").strip()
        jobs = []
        for r in rs:
            url = r.get("job_url") or r.get("job_url_direct") or ""
            jobs.append({
                "t": (r.get("title") or "").strip(),
                "c": company,
                "u": url,
                "p": pretty_portal(r.get("source_portal") or "unknown"),
                "d": (r.get("date_posted") or "").strip(),
                "km": (r.get("erlangen_km") or "").strip(),
                "line": (r.get("line") or "").strip(),
                "st": (r.get("station") or "").strip(),
            })
        badges = " ".join(
            f'<span class="badge" style="background:{portal_color(p)}">{html.escape(str(p))}&nbsp;·&nbsp;{c}</span>'
            for p, c in portal_names.most_common(6))
        prec_badge = ('<span class="prec">≈ town centre</span>' if precision == "city"
                      else '<span class="prec poi">company POI</span>' if precision == "poi"
                      else '<span class="prec street">street address</span>')
        rows_html = []
        for j in jobs[:150]:
            link = (f'<a href="{html.escape(j["u"], quote=True)}" target="_blank" rel="noopener">'
                    f'{html.escape(j["t"] or "(no title)")}</a>') if j["u"] else html.escape(j["t"] or "")
            meta = " · ".join(x for x in (j["p"], j["d"], f'{j["km"]} km' if j["km"] else "", j["line"]) if x)
            rows_html.append(f'<li><div class="jt">{link}</div><div class="jm">{html.escape(meta)}</div></li>')
        more = f'<li class="more">+ {n - 150} more job(s) — see CSV</li>' if n > 150 else ""
        popup = (
            f'<div class="pp">'
            f'<div class="pc">{html.escape(company)}</div>'
            f'<div class="pa">{html.escape(address or "address unknown")}</div>'
            f'<div class="pb">{prec_badge} {badges}</div>'
            f'<ul class="pj">{"".join(rows_html)}{more}</ul>'
            f'</div>')
        markers.append({
            "lat": lat, "lon": lon, "n": n, "company": company,
            "address": address, "precision": precision, "portal": main_portal,
            "color": color, "popup": popup, "jobs": jobs,
        })
    markers.sort(key=lambda m: -m["n"])

    # Spread employers that share an identical point (city-centroid stacks):
    # deterministic golden-angle spiral, so EVERY company gets its own dot.
    # True coordinates stay in jobs.geojson; the HTML uses the spread position.
    by_point = defaultdict(list)
    for m in markers:
        by_point[(m["lat"], m["lon"])].append(m)
    n_spread = 0
    for (lat, lon), ms in by_point.items():
        if len(ms) < 2:
            continue
        n = len(ms)
        for i, m in enumerate(sorted(ms, key=lambda x: x["company"])):
            ang = i * 2.39996323                              # golden angle
            # sunflower disc: radii fill 0..cap uniformly, lon corrected for
            # latitude so the spread looks circular, not elliptical
            rad = 0.009 * math.sqrt((i + 0.5) / n)
            m["lat"] = round(lat + rad * math.cos(ang), 6)
            m["lon"] = round(lon + rad * math.sin(ang) / math.cos(math.radians(lat)), 6)
            m["spread"] = True
            n_spread += 1
    return markers, skipped, n_spread

# ------------------------------------------------------------------ geojson
def build_geojson(rows):
    feats = []
    for r in rows:
        try:
            lat, lon = float(r["lat"]), float(r["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        props = {k: (r.get(k) or "") for k in
                 ("title", "company", "company_address", "geo_precision", "geo_source",
                  "location", "city", "is_remote", "source_portal", "date_posted",
                  "station", "line", "erlangen_km", "job_url")}
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [lon, lat]},
                      "properties": props})
    return {"type": "FeatureCollection", "features": feats}

# ------------------------------------------------------------------ html
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--bg:#10151c;--panel:#161d27;--edge:#232d3b;--txt:#dbe4ee;--dim:#8296ac;--hot:#4dabf7}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);
 font:14px/1.45 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
#layout{display:flex;height:100%}
#side{width:330px;min-width:330px;background:var(--panel);border-right:1px solid var(--edge);
 display:flex;flex-direction:column;z-index:800}
#side header{padding:14px 16px 10px;border-bottom:1px solid var(--edge)}
#side h1{margin:0;font-size:17px;letter-spacing:.2px}
#side h1 b{color:var(--hot)}
#stats{margin-top:6px;color:var(--dim);font-size:12px}
#stats b{color:var(--txt)}
#search{margin:12px 16px 8px;padding:8px 10px;width:calc(100% - 32px);background:#0d1218;
 border:1px solid var(--edge);border-radius:8px;color:var(--txt);outline:none}
#search:focus{border-color:var(--hot)}
#filters{padding:0 16px;max-height:150px;overflow:auto}
#filters label{display:flex;align-items:center;gap:7px;padding:3px 0;cursor:pointer;font-size:13px}
#filters .cnt{margin-left:auto;color:var(--dim);font-size:11px}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
.sect{padding:10px 16px 4px;color:var(--dim);font-size:10.5px;text-transform:uppercase;letter-spacing:1px}
#toplist{flex:1;overflow:auto;padding:0 8px 12px}
#toplist .emp{display:flex;gap:8px;align-items:baseline;padding:5px 8px;border-radius:7px;cursor:pointer}
#toplist .emp:hover{background:#1c2634}
#toplist .ec{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#toplist .en{color:var(--dim);font-size:11px}
#toplist .ea{color:var(--dim);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#side footer{padding:10px 16px;border-top:1px solid var(--edge);color:var(--dim);font-size:11px}
#side footer a{color:var(--dim)}
#map{flex:1}
#reset{position:absolute;top:12px;right:12px;z-index:900;background:var(--panel);color:var(--txt);
 border:1px solid var(--edge);border-radius:8px;padding:7px 12px;cursor:pointer;font-size:12.5px}
#reset:hover{border-color:var(--hot)}
.leaflet-popup-content-wrapper{background:var(--panel);color:var(--txt);border-radius:10px}
.leaflet-popup-tip{background:var(--panel)}
.leaflet-popup-content{margin:12px 14px}
.leaflet-container a.leaflet-popup-close-button{color:var(--dim)}
.pp{min-width:260px;max-width:330px}
.pc{font-size:15px;font-weight:650;color:#fff}
.pa{color:var(--dim);font-size:12px;margin:2px 0 6px}
.prec{font-size:10px;border:1px solid var(--edge);border-radius:20px;padding:1px 7px;color:var(--dim)}
.prec.street{border-color:#12b886;color:#12b886}
.prec.poi{border-color:#b197fc;color:#b197fc}
.badge{display:inline-block;font-size:10px;border-radius:20px;padding:1px 7px;margin-left:4px;color:#fff}
.pj{list-style:none;margin:8px 0 0;padding:0;max-height:250px;overflow:auto}
.pj li{padding:6px 0;border-top:1px solid var(--edge)}
.jt a{color:var(--hot);text-decoration:none;font-weight:550}
.jt a:hover{text-decoration:underline}
.jm{color:var(--dim);font-size:11px;margin-top:1px}
li.more{color:var(--dim);font-size:12px}
.count-badge{background:#0d1218;border:1px solid var(--edge);border-radius:20px;padding:0 6px;
 margin-left:6px;font-size:11px;color:var(--hot)}
@media(max-width:720px){#layout{flex-direction:column}#side{width:100%;min-width:0;height:45%;order:2}#map{height:55%}}
</style>
</head>
<body>
<div id="layout">
 <div id="side">
  <header>
   <h1><b>__TITLE__</b></h1>
   <div id="stats"></div>
  </header>
  <input id="search" type="search" placeholder="Search job title or employer…" autocomplete="off">
  <div class="sect">Portals</div>
  <div id="filters"></div>
  <div class="sect">Top employers <span style="text-transform:none">(click to fly)</span></div>
  <div id="toplist"></div>
  <footer>
   Generated __GENERATED__ · data: <code>__CSV__</code><br>
   Scraped via strict proxy-only network · per-company geocoding chain:
   Photon → maps.co → headless Google-Maps → description mining<br>
   <a href="https://github.com/shalosi00/erlangen-jobs" target="_blank" rel="noopener">github.com/shalosi00/erlangen-jobs</a>
  </footer>
 </div>
 <div id="map"><button id="reset">Reset view</button></div>
</div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const P = JSON.parse(document.getElementById('payload').textContent);
const esc = s => { const d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; };

const map = L.map('map', { zoomControl: true });
const ctr = P.markers.length
  ? [P.markers.reduce((s,m)=>s+m.lat,0)/P.markers.length,
     P.markers.reduce((s,m)=>s+m.lon,0)/P.markers.length]
  : [49.55, 10.95];
map.setView(ctr, 10);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
  maxZoom: 17,
  attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'
}).addTo(map);

// every employer is its OWN marker — no clustering
const layer = L.layerGroup().addTo(map);
const all = P.markers.map(m => {
  const c = L.circleMarker([m.lat, m.lon], {
    radius: 5.5, color: '#eef4fb', weight: 1.1, fillColor: m.color, fillOpacity: .88 });
  c.bindPopup(m.popup, { maxWidth: 360 });
  c._m = m; return c;
});

function applyFilters(){
  const q = document.getElementById('search').value.trim().toLowerCase();
  const on = new Set([...document.querySelectorAll('#filters input:checked')].map(i => i.value));
  const keep = all.filter(c => {
    const m = c._m;
    if (!on.has(m.portal)) return false;
    if (q && !(m.company.toLowerCase().includes(q) ||
               m.jobs.some(j => (j.t||'').toLowerCase().includes(q)))) return false;
    return true;
  });
  layer.clearLayers(); keep.forEach(c => layer.addLayer(c));
  const prec = P.prec || {};
  const streetish = (prec.street||0) + (prec.poi||0);
  document.getElementById('stats').innerHTML =
    `<b>${keep.reduce((s,c)=>s+c._m.n,0)}</b> jobs · <b>${keep.length}</b> employers · ${P.townCount} locations` +
    ` <span class="count-badge">${streetish} at real address</span>` +
    (P.nSkipped ? ` <span class="count-badge">${P.nSkipped} unlocated</span>` : '');
}
document.getElementById('search').addEventListener('input', applyFilters);

const fdiv = document.getElementById('filters');
P.portals.forEach(p => {
  const l = document.createElement('label');
  l.innerHTML = `<input type="checkbox" value="${esc(p.name)}" checked>
    <span class="dot" style="background:${p.color}"></span> ${esc(p.name)}
    <span class="cnt">${p.count}</span>`;
  fdiv.appendChild(l);
});
fdiv.addEventListener('change', applyFilters);

const tdiv = document.getElementById('toplist');
P.topEmployers.forEach(e => {
  const d = document.createElement('div');
  d.className = 'emp';
  d.innerHTML = `<span class="dot" style="background:${e.color};position:relative;top:1px"></span>
    <span style="flex:1;min-width:0"><span class="ec" style="display:block">${esc(e.company)}</span>
    <span class="ea" style="display:block">${esc(e.address || '—')}</span></span>
    <span class="en">${e.n}</span>`;
  d.onclick = () => {
    const c = all.find(x => x._m.company === e.company);
    if (c) { const z = (c._m.precision === 'street' || c._m.precision === 'poi') ? 15 : 13;
             map.flyTo([c._m.lat, c._m.lon], z, { duration: .8 });
             setTimeout(() => c.openPopup(), 850); }
  };
  tdiv.appendChild(d);
});

document.getElementById('reset').onclick = () => map.setView(ctr, 10);
applyFilters();
</script>
</body>
</html>
"""

def render(payload, title, generated, csv_name):
    js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE.replace("__PAYLOAD__", js)
                    .replace("__TITLE__", html.escape(title))
                    .replace("__GENERATED__", html.escape(generated))
                    .replace("__CSV__", html.escape(csv_name)))

def main():
    ap = argparse.ArgumentParser(description="build self-contained Leaflet map from geocoded CSV")
    ap.add_argument("--input", default=None)
    ap.add_argument("--outdir", default=os.path.join(BASE, "map"))
    ap.add_argument("--title", default="Erlangen Job Corridor")
    a = ap.parse_args()

    src = a.input or latest_geo_csv()
    rows = load_rows(src)
    markers, skipped, n_spread = aggregate(rows)
    portals = Counter(m["portal"] for m in markers)
    colors_seen = {}
    plist = []
    for name, count in portals.most_common():
        c = portal_color(name, len(colors_seen))
        plist.append({"name": name, "count": count, "color": c})
    towns = {m["address"] for m in markers if m["address"]}
    top_emp = [{"company": m["company"], "n": m["n"], "address": m["address"],
                "color": m["color"]} for m in markers[:25]]
    prec = dict(Counter(m["precision"] or "city" for m in markers))

    payload = {
        "markers": markers, "portals": plist, "topEmployers": top_emp,
        "townCount": len(towns), "nSkipped": skipped, "prec": prec,
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    os.makedirs(a.outdir, exist_ok=True)
    out_html = os.path.join(a.outdir, "index.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(render(payload, a.title, payload["generated"], os.path.basename(src)))
    gj = build_geojson(rows)
    out_gj = os.path.join(a.outdir, "jobs.geojson")
    with open(out_gj, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False)

    n_jobs = sum(m["n"] for m in markers)
    street = sum(1 for r in rows if r.get("geo_precision") == "street")
    print(f"input : {os.path.basename(src)} ({len(rows)} rows)")
    print(f"output: {out_html} ({os.path.getsize(out_html)//1024} KB)")
    print(f"        {out_gj} ({len(gj['features'])} features)")
    print(f"map   : {n_jobs} jobs @ {len(markers)} individual employer pins, "
          f"{len(plist)} portals, {len(towns)} unique addresses")
    print(f"geo   : street={prec.get('street',0)} poi={prec.get('poi',0)} "
          f"city={prec.get('city',0)} | {n_spread} stacked pins spread apart")

if __name__ == "__main__":
    main()
