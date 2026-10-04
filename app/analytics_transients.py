"""Request-local temporal comparisons with explicit denominators and evidence."""
from bisect import bisect_left, bisect_right
from collections import defaultdict
import hashlib
from .incidents import epoch
from .transients import TYPES, signals, observed_timestamp

TABLES = {
 'a_transient_evidence': ('Every source copy retained for a normalized transient, including rotations deduplicated within an import. No raw text.',
  'transient_id INTEGER,event_id INTEGER,filename TEXT,line_no INTEGER'),
 'a_transients': ('Observed notifications/operations, not causes. Unambiguous same-import windows may attribute global events; ambiguous events remain unassigned. States and details are whitelisted. Requests are not confirmed transitions.',
  'id INTEGER,ts TEXT,type TEXT,previous_state TEXT,next_state TEXT,detail TEXT,call_id INTEGER,perspective_id INTEGER,import_id INTEGER,platform TEXT,basis TEXT,attribution_basis TEXT,event_id INTEGER,filename TEXT,line_no INTEGER,time_basis TEXT'),
 'a_counter_transient_matches': ('One counter interval/transient pair within transient_tolerance_seconds. distance_seconds is distance from the closed interval, zero inside. Temporal coincidence only. Exact perspective; observer/input/lifecycle remain on the counter.',
  'metric_id INTEGER,transient_id INTEGER,type TEXT,distance_seconds REAL,relation TEXT'),
 'a_counter_transient_context': ('Nearest transient and distance to connection/end for each counter interval. Distances are from the closed interval, not localization of the counter increment. NULL means unavailable.',
  'metric_id INTEGER,nearest_transient_id INTEGER,nearest_distance_seconds REAL,connection_distance_seconds REAL,end_distance_seconds REAL'),
 'a_counter_transient_summary': ('Per call/perspective/counter series/type denominators. Only status=ok intervals. Positive delta means counter increase. Count each interval once per type; types overlap. without_any_transient means no recognized attributable transient within tolerance, never absence of a cause.',
  'call_id INTEGER,perspective_id INTEGER,platform TEXT,name TEXT,observer TEXT,output_device TEXT,input_device TEXT,device TEXT,lifecycle TEXT,flow TEXT,ssrc TEXT,direction TEXT,unit TEXT,type TEXT,total_intervals INTEGER,intervals_with_transient INTEGER,positive_intervals_with_transient INTEGER,positive_intervals_without_any_transient INTEGER'),
 'a_counter_initial_observations': ('First valid uncontested observation in the complete selected lifecycle, separately from measured increments. Not localizable. Creation supplies the lower bound when known; connection is only a contextual bound and does not prove all accumulated quantity occurred after connection.',
  'metric_id INTEGER,event_id INTEGER,call_id INTEGER,perspective_id INTEGER,platform TEXT,name TEXT,observer TEXT,input_device TEXT,lifecycle TEXT,value REAL,unit TEXT,window_start TEXT,window_end TEXT,window_basis TEXT,start_event_id INTEGER,localizable INTEGER'),
 'a_transient_coverage': ('Per perspective availability and recognized evidence. Zero transients is not proof that route/focus/interruptions were logged. Unassigned evidence is retained in a_transients.',
  'call_id INTEGER,perspective_id INTEGER,platform TEXT,transient_count INTEGER,source_files INTEGER,warning TEXT'),
}


def distance(a, b, t):
    return max(a-t, t-b, 0)


def populate(db, config):
    ps = [dict(r) for r in db.execute('SELECT * FROM a_observations')]
    by_import = defaultdict(list)
    for p in ps:
        by_import[p['import_id']].append(p)
    selected = {p['id']: p for p in ps}
    events = []
    seen = {};evidence=[]
    # Search only files with validated formats; never scan message/chat bodies.
    for iid, perspectives in by_import.items():
        all_perspectives = [dict(r) for r in db.execute('SELECT * FROM perspectives WHERE import_id=?',(iid,))]
        files = list(db.execute("SELECT id,name FROM files WHERE import_id=? AND (name IN ('PhoneEngine.log','ios_hwwrapper.log','application.log','application-1.log','App.log') OR name LIKE 'kpelog%' OR name LIKE 'VDlog%' OR name LIKE 'sip_debug%')", (iid,)))
        platform = perspectives[0]['platform']
        for f in files:
            if f['name'].startswith('VDlog'):
                markers=('Creating device','We reset the VOD timing')
            elif f['name'].startswith('sip_debug'):
                markers=('INVITE sip',)
            elif f['name']=='App.log':
                markers=('Network changed from SSID:',)
            elif f['name']=='PhoneEngine.log':
                markers=('Received route change notification:',': Network connection changed')
            elif f['name']=='ios_hwwrapper.log':
                markers=('Set isSpeakerphoneActive',)
            elif f['name'].startswith('application'):
                markers=('AudioState[','AudioRoute: resetAudio.','Network is ','Network available','Network lost')
            else:
                markers=('Setting audio input','On hold request sent','Blocking resume call','VDK reported that on-hold')
            # Read only notification headers; SIP needs the complete header block.
            condition=' OR '.join('instr(text,?)>0' for _ in markers)
            for row in db.execute("SELECT id,ts,CASE WHEN kind='sip' THEN text ELSE substr(text,1,instr(text||char(10),char(10))-1) END text,line_no,perspective_id,line_id FROM events WHERE file_id=? AND ("+condition+")", (f['id'],)+markers):
                e = dict(row)
                for kind, previous, following, detail in signals(e['text']):
                    ts, time_basis = observed_timestamp(e['text'], e['ts'])
                    if not ts:
                        continue
                    # Never invent attribution across exports or overlapping lines.
                    p = selected.get(e['perspective_id'])
                    basis = 'event_perspective'
                    if p is None and e['perspective_id'] is None:
                        candidates = [q for q in all_perspectives if q['start'] and q['start'] <= ts and (q['end'] is None or ts <= q['end']) and (e['line_id'] is None or e['line_id'] == q['line_id'])]
                        p = selected.get(candidates[0]['id']) if len(candidates) == 1 else None
                        basis = 'unique_source_window' if p else 'unassigned_or_ambiguous'
                    if e['perspective_id'] is not None and p is None:
                        continue
                    signature = (iid, ts, kind, hashlib.sha256(e['text'].encode('utf-8')).digest(), p['id'] if p else None)
                    if signature in seen:
                        evidence.append((seen[signature],e['id'],f['name'],e['line_no']))
                        continue
                    seen[signature]=len(events)+1
                    events.append((len(events)+1, ts, kind, previous, following, detail, p['call_id'] if p else None, p['id'] if p else None, iid, platform, 'observed', basis, e['id'], f['name'], e['line_no'], time_basis))
                    evidence.append((len(events),e['id'],f['name'],e['line_no']))
                    if len(events) > 100000:
                        raise ValueError('Oltre 100.000 transitori: restringere lo scope')
    for p in ps:
        for field, kind in [('connected','call_connected'), ('end','call_ended')]:
            if not p[field]:
                continue
            e = db.execute('SELECT e.id,f.name,e.line_no FROM events e JOIN files f ON f.id=e.file_id WHERE e.call_id=? AND e.perspective_id=? AND e.ts=? ORDER BY e.id LIMIT 1', (p['call_id'], p['id'], p[field])).fetchone()
            if e:
                events.append((len(events)+1,p[field],kind,None,None,'perspective_boundary',p['call_id'],p['id'],p['import_id'],p['platform'],'inferred','perspective_boundary',e['id'],e['name'],e['line_no'],'event_timestamp'))
                evidence.append((len(events),e['id'],e['name'],e['line_no']))
    db.executemany('INSERT INTO a_transients VALUES('+','.join('?' for _ in range(16))+')',events)
    db.executemany('INSERT INTO a_transient_evidence VALUES(?,?,?,?)',evidence)
    db.execute('CREATE INDEX transient_perspective_time ON a_transients(perspective_id,ts)')
    grouped = defaultdict(list)
    for e in events:
        if e[7] is not None:
            grouped[e[7]].append((epoch(e[1]),e[0],e[2]))
    for items in grouped.values():
        items.sort()
    times = {pid:[r[0] for r in items] for pid,items in grouped.items()}
    summary = {}
    tolerance = config['transient_tolerance_seconds']
    matches = []
    contexts = []
    initial = []
    for row in db.execute('SELECT * FROM a_transient_counter_intervals'):
        c = dict(row)
        p = selected.get(c['perspective_id'])
        if p is None:
            continue
        pid = p['id']
        if c['status'] == 'initial' and c['valid'] and c['simultaneous'] == 1:
            # lifecycle begins with the output's explicit creation event ID.
            creation_ids = [int(value) for value in c['lifecycle'].split('|') if value.isdigit()]
            starts = [db.execute("SELECT id,ts FROM events WHERE id=? AND import_id=? AND text LIKE '%Creating device%'", (value, p['import_id'])).fetchone() for value in creation_ids]
            start = max((r for r in starts if r and r['ts']),key=lambda r:r['ts'],default=None)
            lower = start['ts'] if start else p['connected']
            basis = 'lifecycle_creation' if start else 'connection_context_only' if lower else 'unknown'
            if lower and lower > c['ts']:
                lower = None; basis = 'unknown'
            initial.append((c['id'],c['event_id'],c['call_id'],pid,p['platform'],c['name'],c['observer'],c['input_device'],c['lifecycle'],c['value'],c['unit'],lower,c['ts'],basis,start['id'] if start and lower else None,0))
        if c['interval_start'] is None:
            continue
        a,b = epoch(c['interval_start']),epoch(c['ts'])
        items = grouped[pid]; tt = times.get(pid,[])
        left,right = bisect_left(tt,a-tolerance),bisect_right(tt,b+tolerance)
        kinds = set()
        for t,eid,kind in items[left:right]:
            d = distance(a,b,t)
            matches.append((c['id'],eid,kind,d,'temporal_coincidence'))
            kinds.add(kind)
        if len(matches) > 1000000:
            raise ValueError('Oltre 1.000.000 confronti: restringere scope o tolleranza')
        pos = bisect_left(tt,a)
        nearest = min(items[max(0,pos-1):pos+1],key=lambda r:distance(a,b,r[0]),default=None)
        contexts.append((c['id'],nearest[1] if nearest else None,distance(a,b,nearest[0]) if nearest else None,distance(a,b,epoch(p['connected'])) if p['connected'] else None,distance(a,b,epoch(p['end'])) if p['end'] else None))
        if c['status'] != 'ok':
            continue
        key = (c['call_id'],pid,p['platform'],c['name'],c['observer'],c['output_device'],c['input_device'],c['device'],c['lifecycle'],c['flow'],c['ssrc'],c['direction'],c['unit'])
        counts = summary.setdefault(key,{kind:[0,0,0,0] for kind in TYPES})
        for kind,values in counts.items():
            values[0] += 1
            values[1] += int(kind in kinds)
            values[2] += int(kind in kinds and c['delta'] > 0)
            values[3] += int(not kinds and c['delta'] > 0)
    db.executemany('INSERT INTO a_counter_transient_matches VALUES(?,?,?,?,?)',matches)
    db.executemany('INSERT INTO a_counter_transient_context VALUES(?,?,?,?,?)',contexts)
    db.executemany('INSERT INTO a_counter_initial_observations VALUES('+','.join('?' for _ in range(16))+')',initial)
    db.executemany('INSERT INTO a_counter_transient_summary VALUES('+','.join('?' for _ in range(18))+')',(key+(kind,)+tuple(values) for key,counts in summary.items() for kind,values in counts.items()))
    for p in ps:
        count = db.execute("SELECT COUNT(*) FROM files WHERE import_id=? AND name IN ('PhoneEngine.log','ios_hwwrapper.log','application.log','application-1.log')",(p['import_id'],)).fetchone()[0]
        db.execute('INSERT INTO a_transient_coverage VALUES(?,?,?,?,?,?)',(p['call_id'],p['id'],p['platform'],len(grouped[p['id']]),count,'No recognized transient does not mean no cause; focus/interruption coverage unverified.'))
