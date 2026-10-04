"""Persistent location evidence and versioned position/MOS intervals."""
import hashlib
import json
import math
import re
from itertools import groupby
from bisect import bisect_right
from datetime import datetime, timedelta
from .db import rows
from .mos import calculate, MODEL

VERSION = 'geo-mos-1'
MAX_AGE = 120
SCHEMA = '''
CREATE TABLE IF NOT EXISTS geo_positions(
 id INTEGER PRIMARY KEY,event_id INTEGER NOT NULL REFERENCES events(id),
 import_id INTEGER NOT NULL REFERENCES imports(id),call_id INTEGER REFERENCES calls(id),
 source_line INTEGER NOT NULL,ts TEXT NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL,
 accuracy REAL,elapsed TEXT,kind TEXT NOT NULL,valid INTEGER NOT NULL,method TEXT NOT NULL,
 UNIQUE(event_id,source_line,kind,latitude,longitude,method));
CREATE INDEX IF NOT EXISTS geo_position_time ON geo_positions(import_id,ts);
CREATE TABLE IF NOT EXISTS geo_mos(
 id INTEGER PRIMARY KEY,signature TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,
 latitude REAL NOT NULL,longitude REAL NOT NULL,accuracy REAL,position_ts TEXT NOT NULL,
 direction TEXT NOT NULL,mos REAL NOT NULL,loss REAL NOT NULL,quality TEXT NOT NULL,
 model TEXT NOT NULL,method TEXT NOT NULL,
 UNIQUE(signature,start,end,latitude,longitude,quality,method));
CREATE INDEX IF NOT EXISTS geo_mos_time ON geo_mos(direction,start,end);
CREATE INDEX IF NOT EXISTS geo_mos_space ON geo_mos(latitude,longitude);
CREATE TABLE IF NOT EXISTS geo_mos_evidence(
 observation_id INTEGER NOT NULL REFERENCES geo_mos(id),metric_id INTEGER NOT NULL REFERENCES metrics(id),
 position_id INTEGER NOT NULL REFERENCES geo_positions(id),PRIMARY KEY(observation_id,metric_id,position_id));
'''


def iso(t):
    return t.isoformat(' ', timespec='microseconds')


def extract(text, ts):
    """Accept known Android fixes and actual SIP headers, never bodies/auth headers."""
    if not ts:
        return []
    stamp = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d):(\d{3})\b', text)
    observed = stamp[1]+'.'+stamp[2]+'000' if stamp else iso(datetime.fromisoformat(ts))
    result = []
    def add(match, kind, offset, accuracy=None, elapsed=None):
        lat, lon = float(match[1]), float(match[2])
        valid = math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180
        if accuracy is not None and (not math.isfinite(accuracy) or accuracy<0):
            valid = False
        result.append(dict(ts=observed,latitude=lat,longitude=lon,accuracy=accuracy,
                           elapsed=elapsed,kind=kind,valid=int(valid),offset=offset))
    for offset, line in enumerate(text.splitlines()):
        m = re.search(r'Location\[\w+\s+(-?[\d.]+),\s*(-?[\d.]+)',line)
        if m:
            a = re.search(r'\bhAcc=([-\d.]+)',line)
            e = re.search(r'\bet=([^\s\]]+)',line)
            try:
                add(m,'fresh' if 'New location received:' in line else 'cached',offset,
                    float(a[1]) if a else None,e[1] if e else None)
            except ValueError:
                pass
    lines=text.splitlines()
    start=next((i for i,l in enumerate(lines) if re.match(r'^\s*(?:[A-Z]+ sips?:\S+ SIP/2.0|SIP/2.0 \d{3})',l)),None)
    if start is not None and 'SIP message:' in text:
        kind='sip_local' if 'OUTGOING SIP message:' in text else 'sip_remote'
        for offset in range(start+1,len(lines)):
            line=lines[offset]
            if not line.strip():break
            m=re.match(r'^X-Location:\s*geo:(-?[\d.]+),(-?[\d.]+)(?:;|\s|$)',line,re.I)
            if m:
                try:add(m,kind,offset)
                except ValueError:pass
    return result


def enrich(db, iid):
    from .ios_positions import enrich as enrich_ios_positions
    enrich_ios_positions(db,iid)
    marker=f'{VERSION}:{iid}'
    if db.execute('SELECT 1 FROM meta WHERE key=?',(marker,)).fetchone():return
    for e in db.execute("SELECT * FROM events WHERE import_id=? AND kind NOT LIKE 'telemetry.%' AND (instr(text,'Location[')>0 OR instr(lower(text),'x-location:')>0)",(iid,)):
        for p in extract(e['text'],e['ts']):
            db.execute('''INSERT OR IGNORE INTO geo_positions(event_id,import_id,call_id,source_line,ts,
                latitude,longitude,accuracy,elapsed,kind,valid,method) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (e['id'],iid,e['call_id'],e['line_no']+p['offset'],p['ts'],p['latitude'],p['longitude'],
                 p['accuracy'],p['elapsed'],p['kind'],p['valid'],VERSION))
    positions=rows(db,"SELECT * FROM geo_positions WHERE import_id=? AND valid=1 AND method=? ORDER BY ts,id",(iid,VERSION))
    if not positions:
        db.execute('INSERT INTO meta VALUES(?,?)',(marker,VERSION))
        return
    for perspective in rows(db,'SELECT p.*,c.call_key,r.role FROM perspectives p JOIN calls c ON c.id=p.call_id LEFT JOIN observation_roles r ON r.perspective_id=p.id WHERE p.import_id=?',(iid,)):
        if perspective['role'] not in (None,'app'):continue
        scores=calculate(db,[perspective['call_id']],perspective['id'])
        if not scores:continue
        for quality in ('fresh','declared'):
            pp=[p for p in positions if p['kind']=='fresh' or (quality=='declared' and p['kind']=='sip_local' and p['call_id']==perspective['call_id'])]
            # Conflicting positions at the same timestamp break association.
            grouped={}
            for p in pp:grouped.setdefault(p['ts'],[]).append(p)
            times=sorted(grouped)
            stamps=[datetime.fromisoformat(t) for t in times]
            for m in scores:
                if m.get('clock_domain') == 'UTC':continue
                if m['direction'] not in ('incoming','outgoing'):continue
                begin,end=map(datetime.fromisoformat,(m['ts'],m['valid_until']))
                i=max(0,bisect_right(stamps,begin)-1)
                while i<len(stamps) and stamps[i]<end:
                    batch=grouped[times[i]]; p=batch[0]
                    a=max(begin,stamps[i]); b=min(end,stamps[i]+timedelta(seconds=MAX_AGE),stamps[i+1] if i+1<len(stamps) else end)
                    i+=1
                    if b<=a or len({(x['latitude'],x['longitude']) for x in batch})!=1:continue
                    # Identical RTCP evidence in overlapping ZIPs has one lineage.
                    event=db.execute('SELECT text FROM events WHERE id=?',(m['event_id'],)).fetchone()[0]
                    signature=hashlib.sha256(json.dumps([perspective['call_key'],event,m['direction'],m['flow'],m['ssrc'],m['report_ts'],m['loss_percent']],ensure_ascii=False).encode()).hexdigest()
                    values=(signature,iso(a),iso(b),p['latitude'],p['longitude'],p['accuracy'],p['ts'],
                            'downstream' if m['direction']=='incoming' else 'upstream',m['value'],m['loss_percent'],quality,MODEL['version'],VERSION)
                    db.execute('''INSERT OR IGNORE INTO geo_mos(signature,start,end,latitude,longitude,accuracy,position_ts,direction,mos,loss,quality,model,method)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',values)
                    oid=db.execute('SELECT id FROM geo_mos WHERE signature=? AND start=? AND end=? AND latitude=? AND longitude=? AND quality=? AND method=?',
                                   (signature,iso(a),iso(b),p['latitude'],p['longitude'],quality,VERSION)).fetchone()[0]
                    for evidence in m['evidence']:
                        db.execute('INSERT OR IGNORE INTO geo_mos_evidence VALUES(?,?,?)',(oid,evidence['metric_id'],p['id']))
    db.execute('INSERT INTO meta VALUES(?,?)',(marker,VERSION))


def pending(db):
    with db:
        for iid, in db.execute('SELECT id FROM imports').fetchall():enrich(db,iid)


def grid(lat,lon,size):
    # Latitude bands with longitude widths adjusted at the band centre (metres).
    step=size/111195.08
    band=math.floor((lat+90)/step)
    south=max(-90,band*step-90);north=min(90,south+step)
    width=min(360,step/max(.00001,math.cos(math.radians((south+north)/2))))
    col=math.floor((lon+180)/width)
    west=max(-180,col*width-180);east=min(180,west+width)
    return f'{band}:{col}',[west,south,east,north]


def aggregate(db, params):
    if params.get('metric','mos') == 'perceptual':
        from .perceptual_geo import aggregate as perceptual
        return perceptual(db, params)
    if params.get('metric','mos') != 'mos': raise ValueError('Metrica geografica non valida')
    from .mobility import Context, expand, filters, matches, summary, FIELDS
    selected_filters=filters(params)
    size=int(params.get('cell','250'));direction=params.get('direction','downstream');quality=params.get('quality','fresh')
    if size not in (50,100,250,500,1000,5000,10000) or direction not in ('downstream','upstream') or quality not in ('fresh','declared'):
        raise ValueError('Filtri geografici non validi')
    start=params.get('start','');end=params.get('end','')
    for t in (start,end):
        if t:
            dt=datetime.fromisoformat(t)
            if dt.tzinfo:raise ValueError('Usare gli orari originali senza fuso')
    start=iso(datetime.fromisoformat(start)) if start else '0001-01-01 00:00:00.000000'
    end=iso(datetime.fromisoformat(end)) if end else '9999-12-31 23:59:59.999999'
    if end<=start:raise ValueError('La fine deve seguire l’inizio')
    data=rows(db,'''SELECT g.* FROM geo_mos g WHERE direction=? AND quality=? AND method=? AND end>? AND start<?
        AND EXISTS(SELECT 1 FROM geo_mos_evidence ev JOIN metrics m ON m.id=ev.metric_id
        LEFT JOIN observation_roles r ON r.perspective_id=m.perspective_id WHERE ev.observation_id=g.id AND (r.role IS NULL OR r.role='app'))
        ORDER BY signature,start,end LIMIT 200001''',(direction,quality,VERSION,start,end))
    if len(data)>200000:raise ValueError('Oltre 200.000 intervalli: restringere il periodo')
    data=expand(db,data)
    telemetry_data=rows(db,'''SELECT g.*,t.context FROM geo_mos g JOIN telemetry_geo_context t ON t.observation_id=g.id
        WHERE g.direction=? AND g.quality=? AND g.end>? AND g.start<? ORDER BY g.signature,g.start LIMIT 200001''',
        (direction,quality,start,end))
    if len(telemetry_data)+len(data)>500000 or len(telemetry_data)>200000:
        raise ValueError('Troppi intervalli: restringere il periodo')
    for r in telemetry_data:r['context']=json.loads(r['context'])
    data=sorted(data+telemetry_data,key=lambda r:(r['signature'],r['start'],r['end']))
    cells={};total=0;weighted=0;conflicts=0;known_seconds=0;context_seconds={}
    canonical=[]
    for _, group in groupby(data,key=lambda r:r['signature']):
        group=list(group)
        boundaries=sorted({max(r['start'],start) for r in group}|{min(r['end'],end) for r in group})
        for a,b in zip(boundaries,boundaries[1:]):
            active=[r for r in group if r['start']<b and r['end']>a]
            if not active:continue
            if len({(r['latitude'],r['longitude'],r['mos']) for r in active})!=1:
                conflicts+=1
                continue
            context={}
            for field in FIELDS:
                values={r['context'][field] for r in active}
                context[field]=values.pop() if len(values)==1 else 'unknown'
            canonical.append((dict(active[0],context=context),a,b))
    for r,a,b in canonical:
        if not matches(r['context'],selected_filters):continue
        seconds=(datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()
        if r['context']['access']!='unknown':known_seconds+=seconds
        context_key=(r['context']['access'],r['context']['upstream'],r['context']['operator'])
        context_seconds[context_key]=context_seconds.get(context_key,0)+seconds
        key,bounds=grid(r['latitude'],r['longitude'],size)
        cell=cells.setdefault(key,dict(id=key,bounds=bounds,seconds=0,weighted=0,minimum=5,maximum=1,observations=0,days=set(),first=a,last=b,accuracy_max=None))
        cell['seconds']+=seconds;cell['weighted']+=seconds*r['mos'];cell['minimum']=min(cell['minimum'],r['mos']);cell['maximum']=max(cell['maximum'],r['mos']);cell['observations']+=1
        day=datetime.fromisoformat(a).date()
        last_day=(datetime.fromisoformat(b)-timedelta(microseconds=1)).date()
        while day<=last_day:
            cell['days'].add(str(day));day+=timedelta(days=1)
        cell['first']=min(cell['first'],a);cell['last']=max(cell['last'],b)
        if r['accuracy'] is not None:cell['accuracy_max']=max(cell['accuracy_max'] or 0,r['accuracy'])
        total+=seconds;weighted+=seconds*r['mos']
    for cell in cells.values():
        cell['mean']=cell.pop('weighted')/cell['seconds'];cell['days']=len(cell['days'])
        cell['limited']=cell['seconds']<60 or cell['days']<2
    if len(cells)>10000:raise ValueError('Oltre 10.000 celle: aumentare la dimensione o restringere il periodo')
    extent=db.execute("SELECT min(ts),max(ts),count(*) FROM geo_positions WHERE valid=1 AND kind!='sip_remote'").fetchone()
    counts=dict(db.execute('SELECT kind,count(*) FROM geo_positions GROUP BY kind').fetchall())
    # Grey position cells contain no quality claim and no identities.
    locations={}
    location_rows=rows(db,"SELECT latitude,longitude,import_id,ts FROM geo_positions WHERE valid=1 AND kind!='sip_remote' AND method=? AND ts>=? AND ts<? LIMIT 100001",(VERSION,start,end))
    context=Context(db,{r['import_id'] for r in location_rows})
    for r in location_rows:
        if not matches(context.at(r['import_id'],r['ts']),selected_filters):continue
        key,bounds=grid(r['latitude'],r['longitude'],size);locations[key]=dict(id=key,bounds=bounds)
    return dict(cells=sorted(cells.values(),key=lambda c:c['mean']),locations=list(locations.values())[:10000],
                locations_truncated=len(locations)>10000 or len(location_rows)>100000,conflicting_intervals=conflicts,seconds=total,mean=weighted/total if total else None,
                extent=list(extent),position_counts=counts,cell=size,direction=direction,quality=quality,
                model=MODEL['version'],method=VERSION,max_age_seconds=MAX_AGE,
                filters=selected_filters,mobility=summary(db),network_known_seconds=known_seconds,
                network_known_percent=100*known_seconds/total if total else None,
                network_breakdown=[dict(access=k[0],upstream=k[1],operator=k[2],seconds=v) for k,v in sorted(context_seconds.items())])
