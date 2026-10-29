#!/usr/bin/env python3
"""V2: 0-transfer rail reachability from Erlangen Bahnhof (VGN GTFS), robust to service patterns."""
import csv, collections, datetime, json

GTFS = '/home/z/my-project/research/2-e/vgn_gtfs/'
OUT = '/home/z/my-project/research/2-e/'
ERL_PARENT = 'Parentde:09562:3110'

erl_plats, stop_name = set(), {}
with open(GTFS + 'stops.txt', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        stop_name[r['stop_id']] = r['stop_name']
        if r['parent_station'] == ERL_PARENT:
            erl_plats.add(r['stop_id'])

routes = {}
with open(GTFS + 'routes.txt', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        routes[r['route_id']] = (r['route_type'], r.get('route_short_name','').strip(), r.get('route_long_name','').strip())

trips = {}
with open(GTFS + 'trips.txt', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        trips[r['trip_id']] = (r['route_id'], r['service_id'])

# calendar regularity over 90 days from today (Mon 2026-10-12)
WS = datetime.date(2026, 10, 12)
cal = {}
with open(GTFS + 'calendar.txt', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        cal[r['service_id']] = (datetime.date.fromisoformat(r['start_date'][:4]+'-'+r['start_date'][4:6]+'-'+r['start_date'][6:8]),
                                datetime.date.fromisoformat(r['end_date'][:4]+'-'+r['end_date'][4:6]+'-'+r['end_date'][6:8]),
                                [int(r[k]) for k in ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')])
exc = collections.defaultdict(dict)
with open(GTFS + 'calendar_dates.txt', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        d = datetime.date.fromisoformat(r['date'][:4]+'-'+r['date'][4:6]+'-'+r['date'][6:8])
        exc[r['service_id']][d] = r['exception_type']

def wd_active(sid, d):
    c = cal.get(sid); base = bool(c and c[0] <= d <= c[1] and c[2][d.weekday()])
    e = exc.get(sid, {}).get(d)
    return True if e == '1' else False if e == '2' else base

weekdays = [WS + datetime.timedelta(days=i) for i in range(90) if (WS + datetime.timedelta(days=i)).weekday() < 5]
svc_wd = {sid: sum(1 for d in weekdays if wd_active(sid, d)) / len(weekdays) for sid in cal}

erl_trips = set()
with open(GTFS + 'stop_times.txt', encoding='utf-8-sig') as f:
    for st in csv.DictReader(f):
        t = trips.get(st['trip_id'])
        if t and routes[t[0]][0] == '2' and st['stop_id'] in erl_plats:
            erl_trips.add(st['trip_id'])

seqs = collections.defaultdict(list)
with open(GTFS + 'stop_times.txt', encoding='utf-8-sig') as f:
    for st in csv.DictReader(f):
        if st['trip_id'] in erl_trips:
            seqs[st['trip_id']].append((int(st['stop_sequence']), st['stop_id'], st['arrival_time'], st['departure_time']))

def sec(s): h, m, x = s.split(':'); return int(h)*3600 + int(m)*60 + int(x)

# any-service best and regular-service best per stop, plus route sets
any_best, reg_best = {}, {}
routes_any = collections.defaultdict(set); routes_reg = collections.defaultdict(set)
erl_routes_all = collections.Counter(); erl_routes_reg = collections.Counter()
for tid, s in seqs.items():
    s.sort()
    rid, sid = trips[tid]
    erl_routes_all[rid] += 1
    if svc_wd.get(sid, 0) >= 0.6: erl_routes_reg[rid] += 1
    e_dep = None
    for (q, stp, a, d) in s:
        if stp in erl_plats: e_dep = sec(d)
    if e_dep is None: continue
    for (q, stp, a, d) in s:
        if stp in erl_plats: continue
        dt = sec(a) - e_dep
        if dt < 0: continue
        if stp not in any_best or dt < any_best[stp]: any_best[stp] = dt
        routes_any[stp].add(rid)
        if svc_wd.get(sid, 0) >= 0.6:
            if stp not in reg_best or dt < reg_best[stp]: reg_best[stp] = dt
            routes_reg[stp].add(rid)

def short(rid):
    return routes[rid][1] or routes[rid][2]

print('=== ALL RAIL ROUTES TOUCHING ERLANGEN ===')
for rid, n in erl_routes_all.most_common():
    rt, sn, ln = routes[rid]
    print(f'{sn!r:14} trips={n:4} reg={erl_routes_reg[rid]:4} | {ln[:95]}')

print('\n=== REGULAR 0-TRANSFER REACHABLE (weekday, min in-vehicle min) ===')
rows = sorted((round(t/60.0, 1), stop_name[stp], stp, sorted({short(r) for r in routes_reg[stp]})) for stp, t in reg_best.items())
for r in rows: print(r)
print('total stops regular:', len(rows))

print('\n=== REACHABLE ONLY ON IRREGULAR SERVICES (edge cases) ===')
for stp, t in sorted(any_best.items(), key=lambda x: x[1]):
    if stp not in reg_best:
        print(round(t/60.0,1), stop_name[stp], stp, sorted({short(r) for r in routes_any[stp]}))

# explicit exclusion checks
print('\n=== EXCLUSION CHECK: rail presence of candidate towns (any stop name containing...) ===')
cand = ['Herzogenaurach', 'Höchstadt', 'Neustadt (Aisch)', 'Neustadt an der Aisch', 'Bad Windsheim', 'Feucht', 'Winkelhaid', 'Altdorf', 'Postbauer', 'Neumarkt', 'Roth', 'Schwabach', 'Ansbach', 'Würzburg', 'Kitzingen', 'Iphofen', 'Markt Bibart', 'Emskirchen', 'Zirndorf', 'Langenzenn', 'Cadolzburg', 'Wachendorf', 'Kalchreuth', 'Eschenau', 'Gräfenberg', 'Eckental', 'Heroldsberg', 'Baiersdorf', 'Forchheim', 'Bamberg', 'Haßfurt', 'Zeil', 'Ebern', 'Baunach', 'Scheßlitz', 'Weismain', 'Burgkunstadt', 'Küps', 'Kronach', 'Buckenhof', 'Spardorf', 'Uttenreuth', 'Marquardsen', 'Neunkirchen am Brand', 'Dormitz', 'Kleinsendelbach', 'Hetzles', 'Effeltrich', 'Pretzfeld', 'Kirchehrenbach', 'Leutenbach', 'Weilersbach', 'Churchuren', 'Reuth']
names = collections.defaultdict(list)
for stp, nm in stop_name.items(): names[nm].append(stp)
for c in cand:
    hits = [nm for nm in names if c.lower() in nm.lower()]
    if not hits: print(f'{c:24} -> NO GTFS STOP'); continue
    stps = {s for nm in hits for s in names[nm]}
    in_any = stps & set(any_best); in_reg = stps & set(reg_best)
    print(f'{c:24} -> stops={len(stps):3} direct_any={len(in_any)} direct_reg={len(in_reg)}' + (f'  e.g. {sorted((round(any_best[x]/60,1), stop_name[x]) for x in in_any)[:3]}' if in_any else ''))

json.dump({'regular': rows, 'any_count': len(any_best)}, open(OUT + 'erlangen_reachability.json', 'w'), ensure_ascii=False, indent=1)
