# Research 2-e: Train-Reachability Filter for Jobs from Erlangen (VGN open data, DB APIs, 0-transfer whitelist)

Agent: 2-e | Date of research: 2026-10-11 (live tests) | Status: VERIFIED against primary data
Purpose: technical basis for programmatically filtering job postings by **direct (0-transfer) train reachability from Erlangen Bahnhof within ~60 min**.

---

## 0. Executive summary

- **VGN publishes its full scheduled-timetable (Soll-Fahrplan) as GTFS** at `https://www.vgn.de/opendata/` — plain Apache directory index, stable URL `GTFS.zip` always contains the latest feed. License: **CC BY-SA 3.0 DE**. Latest file: 2026-06-24 (14.6 MB zip → ~153 MB unpacked). Updates are irregular (3–6×/year, near timetable changes).
- **I downloaded and analyzed the actual VGN GTFS feed** (trip-level, 1.71 M stop_times rows): computed the complete set of stops reachable **0-transfer by rail (route_type=2) from Erlangen Bahnhof** within 60 min on regular weekday services. Result: **82 stops / 29 municipalities** (incl. 2 flagged "limited"). This is primary-data verification, not anecdote.
- **Key discovery: VGN stop IDs embed the official Bavarian municipality key (AGS)** — e.g. `de:09563:2110:12:21` = Fürth (09563), `de:09562:*` = Erlangen city, `de:09572:*` = Landkreis Erlangen-Höchstadt. Municipality/PLZ mapping needs **no geo-join** — just the ID prefix + BKG Gemeindeverzeichnis.
- **v6.db.transport.rest is DEAD for data endpoints** (HTTP 503 on `/stops`, `/journeys`, `/departures`; verified live 2026-10-11; root doc page still 200). Known since Jan 2025 (GitHub issue #34). Do NOT build on it.
- **db-vendo-client** (now at `public-transport/db-vendo-client`; `derhuerst/db-vendo` URL is 404) works only **self-hosted** (Node); upstream README warns "DB APIs are subject to haphazard blocking and have become very unreliable" and recommends MOTIS/transitous instead.
- **Pragmatic verdict: use the hardcoded whitelist (method b) as the job filter; optionally regenerate it quarterly from VGN GTFS with the provided 40-line Python script (method a). No journey-API dependency needed.**
- S-Bahn caveat that invalidates older assumptions: on **2025-12-14 the S1/S3 line ends were swapped back** — S1 = Bamberg–Erlangen–Nürnberg–**Hartmannshof** (Lauf valley); the temporary 2023–2025 routing via Feucht/Altdorf/**Neumarkt** is now the **S3** (no Erlangen service). Neumarkt/Feucht/Altdorf/Postbauer-Heng are therefore **NOT 0-transfer** from Erlangen anymore.
- Deutschlandticket: **€63/month since Jan 2026** (was €58 in 2025, €49 2023–24) → the entire whitelist is commute-covered at zero per-ride cost.

---

## 1. Data sources (verified table)

| Source | URL | Format / content | License | Freshness (verified 2026-10-11) | Verdict |
|---|---|---|---|---|---|
| **VGN GTFS** | `https://www.vgn.de/opendata/` (dir index), stable latest: `https://www.vgn.de/opendata/GTFS.zip` | GTFS, full VGN area incl. Nbg/Fürth/Erlangen + Upper Franconia expansion (Bamberg, Coburg, Kronach, Lichtenfels, Haßberge…), Sollfahrplan | **CC BY-SA 3.0 DE** (`Nutzungsbedingungen.txt`, §5(3), commercial OK, attribution + share-alike) | `GTFS.zip`: 15,261,462 bytes, Last-Modified **2026-06-24**, HTTP 200. Dated exports since 2017 (irregular, ~2–7×/yr) | ✅ PRIMARY SOURCE |
| VGN OpenData terms | `https://www.vgn.de/opendata/Nutzungsbedingungen.txt` | 4.5 KB text | — | 2017 file, still current | ✅ |
| **gtfs.de (OpenOV/motis project) Germany feeds** | `https://download.gtfs.de/germany/nv_free/latest.zip` (Nahverkehr), `…/rv_free/latest.zip` (Regional), `…/fv_free/latest.zip` (Fernverkehr) | All-Germany GTFS merges | open (CC0-style, gtfs.de terms) | **Daily** builds (Last-Modified 2026-10-10); NV = **278 MB**, RV = 11.4 MB | ✅ fallback / cross-check |
| `opendata.db.de` | — | was DB open-data portal | — | **DNS does not resolve** (2026-10-11) | ❌ dead |
| **v6.db.transport.rest** | `https://v6.db.transport.rest/` | DB HAFAS REST proxy (FPTF) | — | Root docs HTTP 200; **ALL data endpoints 503** (`/stops?query=`, `/stops/8000116`, `/departures`, `/journeys` tested 2026-10-11; hangs ~10 s then 503). Broken since ~2025-01 (GH issue #34 on derhuerst/db-rest) | ❌ **dead for data** |
| **db-vendo-client** | `https://github.com/public-transport/db-vendo-client` (old `derhuerst/db-vendo` → 404) | Node client for new DB "vendo/movas" APIs; profiles `db`/`dbnav`/`dbweb` (no API key), `dbris` (key); `journeys/locations/departures/trip` | ISC | Actively maintained (2026); **no public hosted instance → self-host**; upstream warning: DB APIs "haphazard blocking … very unreliable"; recommends `motis-fptf-client` + transitous.org or self-hosted MOTIS | ⚠️ self-host only |
| **transitous.org (MOTIS)** | `https://api.transitous.org/` | Public routing API (MOTIS v1: `/api/v1/plan` — 400 without params = alive; usage policy applies) | open, fair-use policy | HTTP 200 (2026-10-11) | ⚠️ usable, respect policy |
| VAG realtime API (Nbg city) | `https://opendata.vag.de/dataset/api-echtzeitauskunft` (`start.vag.de`) | departures/trips for VAG U-Bahn/tram/bus only — **no trains** | open | documented, not needed for rail filter | ℹ️ |
| **VGN routing API** | none public. `efa.vgn.de/vgnExt_oeffi/` → HTTP 404 (2026-10-11); website journey planner is JS/EFA-internal | — | — | — | ❌ **no public VGN trip API** |
| VGN tariff zone plans | `https://www.vgn.de/media/tarifzonenplan-erlangen_2025.pdf`, `…-nuernberg-fuerth_2025.pdf`, `…-vgn_gesamtraum2026.pdf` | zone maps, "gültig ab 01.01.2026" | VGN © | current | ✅ |

**VGN GTFS internals (measured):** stops 25,464 · trips 90,753 · routes 1,295 (route_type: 71 rail, 10 U-Bahn, 8 tram, 1,206 bus) · stop_times 1,710,427 rows (145.8 MB) · calendar 1,389 services + 30,653 calendar_dates exceptions (school-holiday patterns!). One agency row (VGN). Erlangen Bahnhof parent: `Parentde:09562:3110`, rail platforms `de:09562:3110:{1:1,2:2,2:3,3:A,3:B,3:C,4:4}`.

---

## 2. Method for the 0-transfer computation (reproducible)

Script: `research/2-e/analyze_erlangen_reach2.py` (runs in ~2–4 min, plain Python stdlib, no DB needed).

Algorithm (a) — GTFS trip-scan, **no full router needed for "direct train"**:
1. Read `stops.txt`, collect all platform stop_ids with `parent_station == Parentde:09562:3110`.
2. Read `routes.txt` + `trips.txt`, keep `route_type == 2` (rail: S-Bahn/RE/RB/IC/ICE; excludes U-Bahn=1, tram=0, bus=3).
3. Pass over `stop_times.txt`: find trip_ids containing an Erlangen platform → 569 rail trips.
4. Second pass: rebuild ordered stop sequences for those trips; for each trip and each other stop, in-vehicle time = `stop.arrival − Erlangen.departure` (same trip_id ⇒ same vehicle ⇒ 0 transfers by construction).
5. Regularity filter: build service weekday-activity over a 90-day window from today (`calendar.txt` + `calendar_dates.txt` exceptions); a stop is whitelisted if reachable via a service active on ≥60% of weekdays (kills school-holiday/weekend-only ghosts). Sanity check: the "irregular-only" set was **empty** — every reachable stop is on regular service.
6. Group by `stop_id[3:8]` = **AGS municipality key** → municipalities; join to PLZ via BKG "Verzeichnisse der Gemeinden" (opendata) — no lat/lon geocoding needed.
7. Refresh quarterly (or after each new `GTFS.zip` date / December timetable change).

Result JSON: `research/2-e/erlangen_reachability.json`; full dump: `research/2-e/reach_v2_full.txt`; feed: `research/2-e/vgn_gtfs/` (unzipped).

Method (b) — hardcode the whitelist below in the job filter (regex/PLZ list), re-verify quarterly. Recommended default: zero runtime dependencies.

Method (c) — journey-API: dead as of 2026 (v6 503; VGN has no public API; db-vendo needs self-hosting and upstream warns of blocking). Only sensible API route: self-host **MOTIS** (github.com/motis-project/motis) fed with VGN GTFS, or transitous.org with rate-limit care. Not needed for a boolean "direct ≤ 60 min" filter.

Data volumes/effort honestly: VGN feed 14.6 MB down / 153 MB unpacked; analysis script <200 lines stdlib; ~2–4 min CPU; gtfs.de all-Germany feed 278 MB (only if whole-DE coverage wanted). Quarterly refresh = re-run one script.

---

## 3. THE WHITELIST — municipalities with 0-transfer train from Erlangen, ≤60 min (verified from VGN GTFS 2026-06-24)

Rail lines serving Erlangen (feed `j26-1`, confirmed by official VGN Tarifzonenplan Erlangen 2025): **S1** (Bamberg–Erlangen–Fürth–Nürnberg–Lauf–Hersbruck–Hartmannshof), **RE 14** (Nbg–Bamberg–Lichtenfels–Kronach–Ludwigsstadt), **RE 19** (Nbg–Bamberg–Coburg–Sonneberg), **RE 20** (Nbg–Bamberg–Haßfurt), **RE 28** (Nbg–Bamberg–Lichtenfels–Coburg–Sonneberg), **RE 29** (Nbg–Bamberg–Coburg), **IC 61** (Bamberg–Erlangen–Nbg–Ansbach–Crailsheim–Stuttgart; **limited: ~2–4 trips/day**). Erlangen has **no ICE stop**; no RB12 exists; no direct Erlangen–Würzburg train.

Times = scheduled in-vehicle minutes from Erlangen Bahnhof (min over regular weekday trips; door-to-door adds access+wait ~10–15 min). Direction: N=North, S=South, E=East.

### 3.1 Core whitelist (≤60 min, regular service)

| Municipality (AGS) | Station(s) | Line(s) | ~min | Dir | ~PLZ | Notes |
|---|---|---|---|---|---|---|
| Erlangen (09562) | (origin) Paul-Gossen-Str., Erlangen-Bruck, Eltersdorf | S1 | 2–6 | — | 91052–91058 | intra-city |
| **Fürth** (09563) | Fürth (Bay) Hbf; Fürth Klinikum; Fürth Vach | RE14/19/20/28/29; S1 | 7 (RE Hbf) / 10–17 (S1) | S | 90762 | |
| **Nürnberg** (09564) | Nürnberg Hbf | all RE + IC61 | **14–15** (RE) / 28 (S1) | S | 90402 ff. | city stops S1: Dürrenhof 33, Ostring 35, Mögeldorf 37, Rehhof 39, Laufamholz 41; per-feed also Steinbühl 26, Rothenburger Str. 24 (see §5) |
| **Baiersdorf** (09572) | Baiersdorf | S1 | 6 | N | 91096 | |
| **Bubenreuth** (09572) | Bubenreuth | S1 | 3 | N | 91058? (Lk) | village stop |
| **Forchheim** (09474) | Forchheim; Forchheim Nord; Kersbach | RE14/19/20/28/29; S1 | 7 (RE) / 13–18 (S1); Kersbach 9 | N | 91301 | Kersbach = Forchheim district |
| **Eggolsheim** (09474) | Eggolsheim | RE14 / S1 | 16 | N | 91336 | |
| **Buttenheim** (09471) | Buttenheim | S1 | 24 | N | 96155 | |
| **Hirschaid** (09471) | Hirschaid | RE* / S1 | 16 | N | 96146 | |
| **Strullendorf** (09471) | Strullendorf | S1 | 31 | N | 96157 | |
| **Bamberg** (09461) | Bamberg | RE* / IC61 20–22; S1 37 | 20–37 | N | 96047 ff. | ICE hub 1 transfer away |
| **Hallstadt** (09471) | Hallstadt | RE14/28 | 30 | N | 96050 | |
| **Breitengüßbach** (09471) | Breitengüßbach | RE14/28 | 30 | N | 96149 | |
| **Rattelsdorf** (09471) | Ebing | RE14/28 | 34 | N | 96179 | |
| **Zapfendorf** (09471) | Zapfendorf | RE14/28 | 36 | N | 96199 | |
| **Ebensfeld** (09478) | Ebensfeld | RE14/28 | 38 | N | 96237 | |
| **Bad Staffelstein** (09478) | Bad Staffelstein | RE14/28 | 42 | N | 96231 | |
| **Lichtenfels** (09478) | Lichtenfels; Schney | RE14/28 (47); IC61 (37) | 37–57 | N | 96215 | Schney = Lichtenfels district |
| **Michelau i.OFr.** (09478) | Michelau | RE14 | 53 | N | 96247 | |
| **Hochstadt a.Main** (09478) | Hochstadt-Marktzeuln | RE14 | 56 | N | 96272 | |
| **Redwitz a.d.Rodach** (09478) | Redwitz | RE14 | 59 | N | 96257 | |
| **Kronach** (09476) | Kronach | **IC61 (51, limited)**; RE14 65 | 51 (flag) | N | 96317 | regular RE is 65 min |
| **Haßfurt** (09674) | Haßfurt | RE20 | 41 | W | 97421 | |
| **Schwaig b.Nürnberg** (09574) | Schwaig | S1 | 43 | E | 90571 | |
| **Röthenbach a.d.Pegnitz** (09574) | Röthenbach (Pegn); -Steinberg; -Seespitze | S1 | 46–50 | E | 90596 | |
| **Lauf a.d.Pegnitz** (09574) | Lauf West; Lauf (li Pegn) | S1 | 52–53 | E | 91207 | |
| **Ottensoos** (09574) | Ottensoos | S1 | 57 | E | 91224 | |
| **Henfenfeld** (09574) | Henfenfeld | S1 | 60 | E | 91225 | |
| **Coburg** (09463) | Coburg | RE19/28/29 | **47** | N | 96450 | ~65 km but <60 min by express — filter by TIME, not km |
| **Ansbach** (09561) | Ansbach | **IC61 only (48, limited ~2–4×/day)** | 48 (flag) | S | 91522 | no regional direct; RE needs change in Nürnberg |

Count: **29 municipalities + Erlangen city** (82 stops; 6 flagged-limited entries).

### 3.2 Borderline (61–65 min, include if cutoff is soft)

Küps (RE14, 61, Lk Kronach) · Ebersdorf b.Coburg (RE28, 62) · Hersbruck (li Pegn) (S1, 63) · Dörfles-Esbach (RE19/28/29, 63) · Coburg Nord (RE19/28, 64).

### 3.3 Explicitly EXCLUDED towns (verified, with reason)

| Town | Reason (primary-data verified) |
|---|---|
| **Herzogenaurach** | **No rail at all** — 0 rail stops in GTFS; VGN Tarifzonenplan shows zone 199 with bus lines (203/209/210/285/289/295…) from Erlangen; former railway closed to passengers. Bus-only (≈30 min). EXCLUDE for train rule |
| **Höchstadt a.d. Aisch** | no rail; bus only (210/213) |
| Buckenhof, Spardorf, Uttenreuth, Marquardsen, Dormitz, Neunkirchen a.Brand, Kleinsendelbach, Hetzles, Effeltrich, Pretzfeld, Kirchehrenbach, Weilersbach, Leutenbach | no rail (former Gräfenberg branch bus-replaced); all 0 direct stops in GTFS |
| Heroldsberg, Kalchreuth, Eschenau, Gräfenberg, Eckental | served by the Nürnberg–Gräfenberg line **from Nürnberg, not Erlangen** → ≥1 transfer |
| **Schwabach, Roth, Feucht, Winkelhaid, Altdorf, Postbauer-Heng, Neumarkt i.d.OPf.** | S2/S3 branches south of Nürnberg → 1 transfer. **NOTE:** Dec 2023–14 Dec 2025 S1 temporarily ran to Neumarkt — since the 2025-12-14 "Rücktausch" this is the **S3** and NOT reachable 0-transfer from Erlangen (older web pages say otherwise!) |
| **Würzburg, Kitzingen, Iphofen, Markt Bibart, Emskirchen, Neustadt a.d.Aisch, Bad Windsheim** | Nbg–Würzburg trains run via Fürth–Neustadt(Aisch), bypass Erlangen → 1 transfer. **No direct Erlangen–Würzburg train exists** |
| Zirndorf, Langenzenn, Cadolzburg, Wilhermsdorf | Fürth–Markt Erlbach/Würzburg RB from Fürth → 1 transfer |
| Zeil a.Main, Ebern, Baunach, Scheßlitz, Weismain, Burgkunstadt | no direct train from Erlangen (1 transfer via Bamberg/Lichtenfels or bus) |
| >60 min: Rödental 70, Creidlitz 69, Grub am Forst 66, Neuses b.Kronach 66, Happurg 67, Pommelsbrunn 71, Hartmannshof 74, Crailsheim 74 (IC61 limited), Ludwigsstadt 74/94, Neustadt b.Coburg 79, Sonneberg 83 | fail 60-min cutoff |

---

## 4. Tariff zones & Deutschlandticket (official VGN sources)

- Zones: **Nürnberg + Fürth = Zonen 100 + 200** (Stadttarif A: Nürnberg–Fürth–Stein); **Erlangen = Zone 400** (Stadttarif **C**) — official Tarifzonenplan Erlangen, gültig ab 01.01.2026. (The briefing's guess "655/653/650" is wrong — that numbering belongs to other Verbünde.) Other relevant: Baiersdorf zone 254, Herzogenaurach zone 199, Schwabach 600; Stadttarif D covers Ansbach, Bamberg, Forchheim, Neumarkt, Schwabach…; E: Coburg etc.
- Price levels: Stadttarife A–F for city rides; regional **Preisstufen 1–10** cross-city; zone 200 counted once.
- **Deutschlandticket: €58 (2025) → €63/month from Jan 2026** (multiple sources incl. VGN-region press 2025-09 + 2026-09). Context prices: VGN TagesTicket Solo A €10.60; JahresAbo A €79.20/mo.
- Budget implication: with a €63 D-Ticket the **entire whitelist (incl. Coburg/Kronach/Lichtenfels)** is covered — commute cost is flat, so the train-filter can ignore fare distance entirely. Without D-Ticket, Erlangen→Nürnberg/Fürth is the only realistic daily-commute range (monthly pass ~4er/Preisstufe A-region level, ~€90+).
- VGN area note: Upper Franconia (Lk Bamberg, Lichtenfels, Kronach, Coburg, Hof, Kulmbach…) joined VGN 01.01.2024 (further expansion Dec 2025) → the whole 60-min train radius is now one tarif area.

## 5. Caveats / quirks found (important for correctness)

1. **S1 model calls at Nürnberg Steinbühl (26 min) + Rothenburger Str. (24 min)** on all 279 S1 trips (depot/yard routing between Nbg Hbf and Fürth), and the feed shows **no S1 stop at Fürth Hardhöhe / Fürth Stadthalle**. Fürth/Nürnberg municipality verdicts unaffected (Hbf/Klinikum/Vach + Hbf stop lists dominate). If using stop-level lists, re-verify these two Nürnberg stops against vgn.de/bahn.de before trusting.
2. `regular_trips` per route in §3 are service-day counts, not trains/day; S1 ≈ 114 regular weekday services (20-min core takt Erlangen–Lauf), RE 14/19/20/28/29 ≈ 15–36/day, IC 61 ≈ 4/day.
3. `calendar_dates` carry school-holiday exceptions — always filter by a real-date window (the script does).
4. VGN feed updates are irregular (2024-02-29, 2024-04-22, 2024-11-27, 2025-08-06, 2025-12-02, 2026-01-12, 2026-06-24) — pin the zip date in the report and re-check at each December timetable change.
5. Times are scheduled (Soll), not real-time; add transfer-free margin: realistic door-to-door ≈ +10–15 min.

## 6. Recommended implementation for the job filter

1. **Default:** hardcode the 29-municipality whitelist (table 3.1) as a set of AGS codes + PLZ prefixes + name regexes; attach per-town `max_minutes` and `lines` metadata; flag Ansbach/Kronach entries "limited".
2. **Quarterly refresh:** re-run `analyze_erlangen_reach2.py` against fresh `GTFS.zip` (one cron line, stdlib only).
3. **Do not** add v6.db.transport.rest or any DB-hosted API to the pipeline (503/unreliable). If live routing is ever needed: self-hosted MOTIS on VGN GTFS (license CC BY-SA 3.0 DE → keep attribution, internal filtering is fine).
