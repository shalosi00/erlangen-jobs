#!/usr/bin/env python3
"""Compute 0-transfer rail reachability from Erlangen Bahnhof using VGN GTFS."""
import csv, collections, datetime, json

GTFS = '/home/z/my-project/research/2-e/vgn_gtfs/'
ERL_PARENT = 'Parentde:09562:3110'
OUT = '/home/z/my-project/research/2-e/'

# --- stops: children of Erlangen parent + name lookup
erl_plats = set()
stop_name = {}
with open(GTFS + 'stops.txt', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        stop_name[r['stop_id']] = r['stop_name']
        if r['parent_station'] == ERL_PARENT:
            erl_plats.add(r['stop_id'])
print('Erlangen platform stop_ids:', sorted(erl_plats))

# --- routes (keep rail route_type=2)
routes = {}
with open(GTFS + 'routes.txt', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        routes[r['route_id']] = (r['route_type'], r.get('route_short_name',''), r.get('route_long_name',''))

# --- trips
trips = {}
with open(GTFS + 'trips.txt', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        trips[r['trip_id']] = (r['route_id'], r['service_id'])

# --- pass 1: rail trip_ids that touch an Erlangen platform
erl_trips = set()
with open(GTFS + 'stop_times.txt', encoding='utf-8-sig') as f:
    for st in csv.DictReader(f):
        t = trips.get(st['trip_id'])
        if t and routes[t[0]][0] == '2' and st['stop_id'] in erl_plats:
            erl_trips.add(st['trip_id'])
print('rail trips serving Erlangen:', len(erl_trips))

# --- calendar: service active weekday fraction over 90-day window from today
WINDOW_START = datetime.date(2026, 10, 12)
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
    c = cal.get(sid)
    base = False
    if c and c[0] <= d <= c[1] and c[2][d.weekday()]:
        base = True
    e = exc.get(sid, {}).get(d)
    if e == '1': return True
    if e == '2': return False
    return base

DAYS = [WINDOW_START + datetime.timedelta(days=i) for i in range(90)]
weekdays = [d for d in DAYS if d.weekday() < 5]
svc_wd_frac = {}
for sid in cal:
    frac = sum(1 for d in weekdays if wd_active(sid, d)) / len(weekdays)
    svc_wd_frac[sid] = frac
print('services total:', len(cal), ' regular(>=0.6 weekday):', sum(1 for v in svc_wd_frac.values() if v >= 0.6))

def hms(s):
    h, m, sec = s.split(':'); return int(h)*3600 + int(m)*60 + int(sec)

# --- pass 2: full sequences for erl trips; compute min in-vehicle time per stop
best = {}   # stop_id -> dict(min_sec, routes set, via_trip, erl_dep)
route_of_trip = {}
erl_seq_cache = collections.defaultdict(list)
with open(GTFS + 'stop_times.txt', encoding='utf-8-sig') as f:
    for st in csv.DictReader(f):
        if st['trip_id'] in erl_trips:
            erl_seq_cache[st['trip_id']].append((int(st['stop_sequence']), st['stop_id'], hms(st['arrival_time']), hms(st['departure_time'])))

for tid, seq in erl_seq_cache.items():
    seq.sort()
    rid, sid = trips[tid]
    for (sq, stp, arr, dep) in seq:
        if stp in erl_plats:
            erl_dep = dep
            for (sq2, stp2, arr2, dep2) in seq:
                if stp2 in erl_plats: continue
                dt = arr2 - erl_dep
                if dt < 0: continue
                b = best.get(stp2)
                if b is None or dt < b['sec']:
                    best[stp2] = {'sec': dt, 'route': rid, 'erl_dep': erl_dep, 'svc': sid, 'trip': tid}
            break  # first Erlangen occurrence defines origin

# --- aggregate per stop: min time via regular weekday service; collect all routes reaching stop
per_stop = collections.defaultdict(lambda: {'sec': None, 'routes': set(), 'regular_sec': None})
for stp, b in best.items():
    p = per_stop[stp]
    if p['sec'] is None or b['sec'] < p['sec']: p['sec'] = b['sec']
    p['routes'].add(b['route'])
    if svc_wd_frac.get(b['svc'], 0) >= 0.6:
        if p['regular_sec'] is None or b['sec'] < p['regular_sec']: p['regular_sec'] = b['sec']

# routes serving Erlangen on regular services (info)
erl_routes = collections.defaultdict(set)
for tid, seq in erl_seq_cache.items():
    rid, sid = trips[tid]
    if svc_wd_frac.get(sid, 0) >= 0.6:
        erl_routes[rid].add(sid)

print('\n=== RAIL ROUTES SERVING ERLANGEN (regular weekday services) ===')
for rid, svcs in sorted(erl_routes.items(), key=lambda x: routes[x[0]][1]):
    rt, sn, ln = routes[rid]
    print(f'route_id={rid} | type={rt} | short={sn!r} | long={ln!r} | regular_trips={len(svcs)}')

print('\n=== STOPS REACHABLE 0-TRANSFER BY RAIL FROM ERLANGEN (<=90 min shown) ===')
rows = []
for stp, p in per_stop.items():
    if p['regular_sec'] is None: continue
    m = p['regular_sec'] / 60.0
    if m <= 90:
        rows.append((round(m,1), stop_name.get(stp, stp), stp, sorted(routes[r][1] or routes[r][2] for r in p['routes'])))
rows.sort()
for r in rows: print(r)
print('count <=60min:', sum(1 for r in rows if r[0] <= 60), ' count <=90min:', len(rows))
json.dump({'reachable': rows, 'routes_serving_erlangen': {rid: {'type': routes[rid][0], 'short': routes[rid][1], 'long': routes[rid][2]} for rid in erl_routes}},
          open(OUT + 'erlangen_reachability.json', 'w'), ensure_ascii=False, indent=1)
