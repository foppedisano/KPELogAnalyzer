"""Explicit KPE Switch Network requests, with separately evidenced context.

Read-only: no inferred switches, call merges, persistent backfill or quality changes.
"""
import re
import json
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timedelta

from .transients import observed_timestamp

VERSION = 'network-switch-1'
MARKER = 'KPE was requested to handle a switchNetworkEvent'
LIMIT = 5000
LABELS = {'wifi':'Wi-Fi','cellular':'Rete mobile','ethernet':'Ethernet',
          'edge':'EDGE','lte':'LTE','gprs':'GPRS','umts':'UMTS','hspa':'HSPA',
          'hspap':'HSPA+','nr':'5G NR','nrnsa':'5G NSA','unknown':'Non determinato'}
SCHEMA = dict(type='object',properties={
    **{k:dict(type='integer',minimum=1) for k in ('call_id','perspective_id','import_id')},
    **{k:dict(type='string') for k in ('start','end','platform','access','upstream','operator')},
    'quality':dict(type='string',enum=['fresh','declared']), 'locate':dict(type='boolean')},
    required=[],additionalProperties=False)


def state(value):
    key=value.strip().lower().replace('wi-fi','wifi')
    return key if key in LABELS else None


def explicit(text, filename):
    name=filename.replace('\\','/').rsplit('/',1)[-1].lower()
    if not name.startswith('kpelog'): return None
    h=text.split('\n',1)[0]
    # The marker must be the log message, not an address, JSON value or SIP body.
    m=re.fullmatch(r'\[[^\]\n]+\]\s+\[KPECORE\]\s+\[(?:INFO|DEBUG|WARNING)\]\s+'
                   +re.escape(MARKER)+r'(?:\s+from ([A-Za-z+ -]+) to ([A-Za-z+ -]+))?\s*\.?',h)
    if not m: return None
    before=state(m[1]) if m[1] else None;after=state(m[2]) if m[2] else None
    return dict(type='network_switch',stage='requested',previous=before,next=after,
                transition_basis='explicit_fields' if before and after else 'not_reported')


def iso(t): return t.isoformat(' ',timespec='microseconds')


def proof(e):
    return dict(event_id=e['id'],filename=e['filename'],line=e['line_no'],ts=e['ts'])


def describe(item):
    a=LABELS.get(item['previous'],'Non determinato');b=LABELS.get(item['next'],'Non determinato')
    return 'Switch Network · '+a+' → '+b


def interface_context(db,item):
    """Nearby declarations describe context, never manufacture a switch marker.

    Only use a differing pair within 3 seconds of this request. Equal interfaces
    cannot establish a radio change. Conflicting simultaneous states are unknown.
    """
    t=datetime.fromisoformat(item['ts']);lo=iso(t-timedelta(seconds=3));hi=iso(t+timedelta(seconds=3))
    nn=[dict(r) for r in db.execute('''SELECT n.ts,n.access,n.event_id,e.line_no,f.name filename
        FROM network_observations n JOIN events e ON e.id=n.event_id JOIN files f ON f.id=e.file_id
        WHERE n.import_id=? AND n.valid=1 AND n.method='mobility-1' AND n.ts>=? AND n.ts<=?
        ORDER BY n.ts,n.id LIMIT 101''',(item['import_id'],lo,hi))]
    item['context_truncated']=len(nn)>100
    item['network_context']=[dict(ts=n['ts'],state=n['access'],event_id=n['event_id'],
        filename=n['filename'],line=n['line_no']) for n in nn[:100]]
    if item['transition_basis']=='explicit_fields' or item['context_truncated']:return
    grouped=defaultdict(set)
    for n in nn: grouped[n['ts']].add(n['access'])
    if any(len(s)>1 or 'unknown' in s for s in grouped.values()):return
    sequence=[]
    for ts,values in grouped.items():
        v=next(iter(values))
        if not sequence or sequence[-1][1]!=v:sequence.append((ts,v))
    # Multiple changes or multiple switch requests in this context are ambiguous.
    if len(sequence)!=2 or item.get('nearby_switches',0)>1:return
    item.update(previous=sequence[0][1],next=sequence[1][1],transition_basis='nearby_interface_observations')


def collect(db, import_id=None, start=None, end=None, call_id=None, perspective_id=None):
    clauses=[];args=[]
    if import_id is not None:clauses.append('e.import_id=?');args.append(import_id)
    if call_id is not None:
        clauses.append('e.import_id IN (SELECT import_id FROM perspectives WHERE call_id=?)');args.append(call_id)
    if call_id is not None:
        from .call_events import windows as call_windows
        selected=[p for p in call_windows(db,call_id) if p['start'] and p['end']
                  and (perspective_id is None or p['id']==perspective_id)]
        if not selected:return []
        clauses.append('e.ts>=? AND e.ts<=?')
        args.extend([iso(datetime.fromisoformat(min(p['start'] for p in selected))-timedelta(seconds=6)),
                     iso(datetime.fromisoformat(max(p['end'] for p in selected))+timedelta(seconds=6))])
    # Include neighboring requests so narrowing a view cannot make context unique.
    if start:clauses.append('e.ts>=?');args.append(iso(datetime.fromisoformat(start)-timedelta(seconds=6)))
    if end:clauses.append('e.ts<?');args.append(iso(datetime.fromisoformat(end)+timedelta(seconds=6)))
    clauses.extend(["e.file_id IN (SELECT id FROM files WHERE lower(name) LIKE '%kpelog%')",'instr(e.text,?)>0']);args.append(MARKER)
    candidates=db.execute('''SELECT e.id,e.import_id,e.call_id,e.perspective_id,e.line_id,e.ts,e.line_no,
        substr(e.text,1,instr(e.text||char(10),char(10))-1) text,f.name filename
        FROM events e JOIN files f ON f.id=e.file_id WHERE '''+' AND '.join(clauses)+
        ' ORDER BY e.ts,e.id LIMIT 10001',args).fetchall()
    if len(candidates)>10000:raise ValueError('Troppe richieste Switch Network: restringere sorgente o periodo')
    result=[];seen={};windows={};all_source_times=defaultdict(set)
    for row in candidates:
        e=dict(row);decoded=explicit(e['text'],e['filename'])
        if not decoded or not e['ts']:continue
        e['ts'],_=observed_timestamp(e['text'],e['ts'])
        iid=e['import_id']
        all_source_times[iid].add(e['ts'])
        if iid not in windows:
            windows[iid]=[dict(p) for p in db.execute('''SELECT p.*,i.label,
                COALESCE(p.end,(SELECT MAX(ts) FROM events INDEXED BY event_call_ts WHERE import_id=p.import_id AND call_id=p.call_id)) bounded_end
                FROM perspectives p JOIN imports i ON i.id=p.import_id WHERE p.import_id=?
                AND p.id NOT IN (SELECT perspective_id FROM effective_duplicates)''',(iid,))]
            from .call_events import bounded
            for index,perspective in enumerate(windows[iid]):
                effective=bounded(db,perspective)
                effective['bounded_end']=effective['end']
                windows[iid][index]=effective
        active=[p for p in windows[iid] if p['start'] and p['bounded_end'] and p['start']<=e['ts']<=p['bounded_end']]
        p=next((p for p in windows[iid] if p['id']==e['perspective_id']),None)
        if e['perspective_id'] is not None and p is None:continue
        if p and p.get('window_evidence') and p not in active:
            p=None;e['call_id']=None;e['perspective_id']=None
        if p is None:
            choices=[q for q in active if (e['call_id'] is None or q['call_id']==e['call_id'])
                and (e['line_id'] is None or q['line_id']==e['line_id'])]
            p=choices[0] if len(choices)==1 else None
        if call_id is not None and not any(q['call_id']==call_id and (perspective_id is None or q['id']==perspective_id) for q in active):continue
        if p and ((call_id is not None and p['call_id']!=call_id) or (perspective_id is not None and p['id']!=perspective_id)):continue
        key=(iid,e['ts'],e['text'])
        if key in seen:seen[key]['evidence'].append(proof(e));continue
        item=dict(decoded,id=e['id'],event_id=e['id'],import_id=iid,ts=e['ts'],
            call_id=p['call_id'] if p else e['call_id'],perspective_id=p['id'] if p else None,
            association='event_perspective' if e['perspective_id'] else 'unique_source_window' if p else 'unassigned_source_context',
            evidence=[proof(e)],network_context=[],location=None)
        seen[key]=item;result.append(item)
    if len(result)>LIMIT:raise ValueError('Oltre 5.000 Switch Network: restringere il periodo')
    source_times={iid:[datetime.fromisoformat(ts) for ts in sorted(values)] for iid,values in all_source_times.items()}
    result=[s for s in result if (not start or s['ts']>=start) and (not end or s['ts']<end)]
    for item in result:
        times=source_times[item['import_id']];t=datetime.fromisoformat(item['ts'])
        item['nearby_switches']=bisect_right(times,t+timedelta(seconds=6))-bisect_left(times,t-timedelta(seconds=6))
        interface_context(db,item);item['label']=describe(item)
    return result


def locate(db, items, quality='declared', start=None, end=None):
    """Only simultaneous positions or bracketing fixes in the same call/source.

    No nearest-position snapping; missing geometry remains explicitly unlocated.
    """
    for item in items:
        item['location_reason']='Nessuna posizione locale coeva o coppia di estremi entro 120 s'
        if item['perspective_id'] is None:
            item['location_reason']='Switch di sorgente non attribuibile a una chiamata univoca';continue
        t=datetime.fromisoformat(item['ts'])
        lo=max(iso(t-timedelta(seconds=120)),start or '0001');hi=min(iso(t+timedelta(seconds=120)),end or '9999')
        p=db.execute('SELECT * FROM perspectives WHERE id=?',(item['perspective_id'],)).fetchone()
        role=db.execute('SELECT role FROM observation_roles WHERE perspective_id=?',(p['id'],)).fetchone()
        if role and role['role'] not in ('app','unknown'):
            item['location_reason']='Osservatore non locale app';continue
        positions=[dict(r) for r in db.execute('''SELECT g.*,f.name filename FROM geo_positions g
            JOIN events e ON e.id=g.event_id JOIN files f ON f.id=e.file_id
            WHERE g.import_id=? AND g.valid=1 AND g.method='geo-mos-1' AND g.kind NOT IN ('cached','sip_remote')
            AND g.ts>=? AND g.ts<=? ORDER BY g.ts,g.id LIMIT 1001''',(item['import_id'],lo,hi))]
        if len(positions)>1000:raise ValueError('Troppe posizioni intorno allo Switch Network')
        # Ineligible fixes remain barriers, rather than being skipped to bridge a gap.
        grouped=defaultdict(list)
        for g in positions:grouped[g['ts']].append(g)
        def usable(group):
            if len({(g['latitude'],g['longitude'],g['call_id'],g['kind']) for g in group})!=1:return None
            g=group[0]
            if quality=='fresh' and g['kind']!='fresh':return None
            if g['ts']<p['start'] or (p['end'] and g['ts']>p['end']):return None
            if g['call_id'] is not None:return g if g['call_id']==item['call_id'] else None
            overlaps=db.execute('''SELECT id FROM perspectives WHERE import_id=? AND start<=?
                AND (end IS NULL OR end>=?) AND id NOT IN (SELECT perspective_id FROM effective_duplicates)''',
                (item['import_id'],g['ts'],g['ts'])).fetchall()
            return g if [r[0] for r in overlaps]==[item['perspective_id']] else None
        times=list(grouped);left=max((s for s in times if s<=item['ts']),default=None);right=min((s for s in times if s>=item['ts']),default=None)
        a=usable(grouped[left]) if left else None;b=usable(grouped[right]) if right else None
        if not a or not b:continue
        gap=(datetime.fromisoformat(b['ts'])-datetime.fromisoformat(a['ts'])).total_seconds()
        if gap>120:continue
        fraction=0 if not gap else (t-datetime.fromisoformat(a['ts'])).total_seconds()/gap
        delta=(b['longitude']-a['longitude']+180)%360-180
        item['location']=dict(latitude=a['latitude']+fraction*(b['latitude']-a['latitude']),
            longitude=(a['longitude']+fraction*delta+180)%360-180,
            basis='observed' if not gap else 'interpolated',gap_seconds=gap,
            evidence=[dict(position_id=g['id'],event_id=g['event_id'],filename=g['filename'],line=g['source_line'],ts=g['ts'],kind=g['kind']) for g in ([a] if not gap else [a,b])])
        item['location_reason']=None
    return items


def request(db, obj):
    allowed={'call_id','perspective_id','import_id','start','end','quality','locate','platform','access','upstream','operator'}
    if not isinstance(obj,dict) or set(obj)-allowed:raise ValueError('Filtri Switch Network non validi')
    for key in ('call_id','perspective_id','import_id'):
        if key in obj and (type(obj[key]) is not int or obj[key]<1):raise ValueError('ID positivo richiesto')
    if 'perspective_id' in obj and 'call_id' not in obj:raise ValueError('Specificare call_id con perspective_id')
    for key in ('platform','access','upstream','operator'):
        if key in obj and not isinstance(obj[key],str):raise ValueError('Filtro rete non valido')
    if 'perspective_id' in obj and not db.execute('SELECT 1 FROM perspectives WHERE id=? AND call_id=?',(obj['perspective_id'],obj['call_id'])).fetchone():
        raise ValueError('Prospettiva non appartenente alla chiamata')
    for key in ('start','end'):
        if key in obj:
            if not isinstance(obj[key],str):raise ValueError('Periodo non valido')
            dt=datetime.fromisoformat(obj[key])
            if dt.tzinfo or dt.year<2 or dt.year>9998:raise ValueError('Usare orari osservati senza fuso')
    start=iso(datetime.fromisoformat(obj['start'])) if obj.get('start') else None
    end=iso(datetime.fromisoformat(obj['end'])) if obj.get('end') else None
    if start and end and end<=start:raise ValueError('Fine precedente all’inizio')
    if obj.get('quality','declared') not in ('fresh','declared'):raise ValueError('Filtro posizione non valido')
    if 'locate' in obj and type(obj['locate']) is not bool:raise ValueError('locate deve essere booleano')
    items=collect(db,obj.get('import_id'),start,end,obj.get('call_id'),obj.get('perspective_id'))
    from .mobility import Context, filters, matches
    selection=filters(obj);context=Context(db,{x['import_id'] for x in items})
    items=[x for x in items if matches(context.at(x['import_id'],x['ts']),selection)]
    if obj.get('locate',True):locate(db,items,obj.get('quality','declared'),start,end)
    result=dict(version=VERSION,events=items,count=len(items),unlocated=sum(x['location'] is None for x in items),
        rules=['Solo richieste switchNetworkEvent esplicite: non prova del completamento o della causa di un re-INVITE.',
               'Da/a ricavati dal contesto vicino sono osservazioni separate, non campi dichiarati dal marker.',
               'Cambio radio non dedotto dall’interfaccia cellular; dati assenti restano non determinati.',
               'Posizioni interpolate marcate come stime; nessun punto inventato senza estremi compatibili.'])
    if len(json.dumps(result,ensure_ascii=False).encode('utf-8'))>4*1024*1024:raise ValueError('Switch Network oltre 4 MiB: restringere la selezione')
    return result
