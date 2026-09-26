"""Versioned source-scoped movement sequences and observed network context."""
import json
import math
import re
import uuid
from bisect import bisect_right
from datetime import datetime,timedelta
from .db import rows

VERSION='mobility-1'
GAP=30
NETWORK_AGE=30
FIELDS=('platform','access','upstream','operator')
SCHEMA='''
CREATE TABLE IF NOT EXISTS network_observations(
 id INTEGER PRIMARY KEY,event_id INTEGER NOT NULL REFERENCES events(id),import_id INTEGER NOT NULL REFERENCES imports(id),
 source_line INTEGER NOT NULL,ts TEXT NOT NULL,access TEXT NOT NULL,upstream TEXT NOT NULL DEFAULT 'unknown',
 operator TEXT,wifi_identity TEXT,basis TEXT NOT NULL,valid INTEGER NOT NULL DEFAULT 1,method TEXT NOT NULL,
 UNIQUE(event_id,source_line,method));
CREATE INDEX IF NOT EXISTS network_import_time ON network_observations(import_id,ts);
CREATE TABLE IF NOT EXISTS movement_sequences(
 id TEXT PRIMARY KEY,import_id INTEGER NOT NULL REFERENCES imports(id),start TEXT NOT NULL,end TEXT NOT NULL,
 break_reason TEXT NOT NULL,method TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS movement_samples(
 position_id INTEGER PRIMARY KEY REFERENCES geo_positions(id),sequence_id TEXT NOT NULL REFERENCES movement_sequences(id),
 ordinal INTEGER NOT NULL,observed_at TEXT NOT NULL,fix_at TEXT,elapsed_raw TEXT,speed_mps REAL,bearing_deg REAL,
 network_observation_id INTEGER REFERENCES network_observations(id),UNIQUE(sequence_id,ordinal));
CREATE INDEX IF NOT EXISTS movement_sequence_order ON movement_samples(sequence_id,ordinal);
'''


def timestamp(text,ts):
    m=re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d):(\d{3})\b',text)
    return m[1]+'.'+m[2]+'000' if m else datetime.fromisoformat(ts).isoformat(' ',timespec='microseconds')


def observations(text,ts):
    if not ts:return []
    found=[]
    for offset,line in enumerate(text.splitlines()):
        value=None;basis=None
        m=re.search(r'\s:\sCurrent network interface:\s*(\w+)\s*$',line)
        if m:value=m[1];basis='interface_observed'
        elif re.search(r'\bProcessCallLogger[^\n]*\s:\sDeviceStatus:\s*\{',line):
            try:
                obj=json.loads(line.split('DeviceStatus:',1)[1]);value=obj.get('connectionType');basis='device_status_observed'
            except (ValueError,AttributeError):continue
        if not isinstance(value,str):continue
        access={'cellular':'cellular','wifi':'wifi','wi-fi':'wifi','ethernet':'ethernet'}.get(value.lower(),'unknown')
        found.append(dict(ts=timestamp(text,ts),access=access,upstream='mobile_direct' if access=='cellular' else 'unknown',
                          basis=basis,offset=offset))
    return found


class Context:
    def __init__(self,db,ids):
        self.platform={};self.network={};self.times={}
        for iid in ids:
            row=db.execute('SELECT profile FROM source_profiles WHERE import_id=?',(iid,)).fetchone()
            platform=json.loads(row[0]).get('platform','unknown') if row else 'unknown'
            self.platform[iid]=platform if platform in ('android','ios','desktop') else 'unknown'
            nn=rows(db,'SELECT * FROM network_observations WHERE import_id=? AND method=? ORDER BY ts,id',(iid,VERSION))
            self.network[iid]=nn;self.times[iid]=[n['ts'] for n in nn]
    def at(self,iid,ts):
        result=dict(platform=self.platform.get(iid,'unknown'),access='unknown',upstream='unknown',operator='unknown',network_id=None)
        nn=self.network.get(iid,[]);times=self.times.get(iid,[]);i=bisect_right(times,ts)-1
        if i<0:return result
        stamp=times[i];batch=[]
        while i>=0 and times[i]==stamp:batch.append(nn[i]);i-=1
        age=(datetime.fromisoformat(ts)-datetime.fromisoformat(stamp)).total_seconds()
        if age>=NETWORK_AGE or any(not n['valid'] for n in batch):return result
        for field in ('access','upstream','operator'):
            values={n[field] or 'unknown' for n in batch}
            result[field]=values.pop() if len(values)==1 else 'unknown'
        if len({(n['access'],n['upstream'],n['operator']) for n in batch})==1:result['network_id']=batch[0]['id']
        return result
    def boundaries(self,iid,start,end):
        result={start,end}
        lo=datetime.fromisoformat(start)-timedelta(seconds=NETWORK_AGE)
        times=self.times.get(iid,[])
        for ts in times[max(0,bisect_right(times,lo.isoformat(' ',timespec='microseconds'))-1):]:
            if ts>=end:break
            expiry=(datetime.fromisoformat(ts)+timedelta(seconds=NETWORK_AGE)).isoformat(' ',timespec='microseconds')
            if start<ts<end:result.add(ts)
            if start<expiry<end:result.add(expiry)
        return sorted(result)


def elapsed_seconds(value):
    if not value or not re.fullmatch(r'\+?(?:\d+(?:ms|d|h|m|s))+',value):return None
    units={'d':86400,'h':3600,'m':60,'s':1,'ms':.001}
    return sum(int(n)*units[u] for n,u in re.findall(r'(\d+)(ms|d|h|m|s)',value))


def enrich(db,iid):
    marker=f'{VERSION}:{iid}'
    if db.execute('SELECT 1 FROM meta WHERE key=?',(marker,)).fetchone():return
    for e in db.execute('''SELECT e.* FROM events e JOIN files f ON f.id=e.file_id
        WHERE e.import_id=? AND f.parser!='telemetry' AND (lower(f.name) LIKE '%app%log' OR lower(f.name) LIKE '%phoneengine%')
        AND (instr(text,'Current network interface:')>0 OR instr(text,'DeviceStatus:')>0)''',(iid,)):
        for n in observations(e['text'],e['ts']):
            db.execute('''INSERT OR IGNORE INTO network_observations(event_id,import_id,source_line,ts,access,upstream,basis,method)
                VALUES(?,?,?,?,?,?,?,?)''',(e['id'],iid,e['line_no']+n['offset'],n['ts'],n['access'],n['upstream'],n['basis'],VERSION))
    context=Context(db,[iid]);previous=None;seq=None;ordinal=0;reason='first_sample'
    points=rows(db,"SELECT * FROM geo_positions WHERE import_id=? AND kind='fresh' ORDER BY ts,id",(iid,))
    bytime={}
    for p in points:bytime.setdefault(p['ts'],[]).append(p)
    for ts,batch in bytime.items():
        p=batch[0]
        if any(not x['valid'] for x in batch) or len({(x['latitude'],x['longitude']) for x in batch})!=1:
            previous=None;seq=None;reason='ambiguous_or_invalid';continue
        if previous:
            gap=(datetime.fromisoformat(ts)-datetime.fromisoformat(previous['ts'])).total_seconds()
            if gap>GAP:seq=None;reason='time_gap'
            elif p['elapsed'] and p['elapsed']==previous['elapsed']:
                # Repeated delivery of the same fix is not motion; conflicting copies break the sequence.
                if (p['latitude'],p['longitude'])!=(previous['latitude'],previous['longitude']):
                    previous=None;seq=None;reason='conflicting_fix'
                continue
            else:
                lat1,lat2=map(math.radians,(previous['latitude'],p['latitude']))
                dlat=lat2-lat1;dlon=math.radians(p['longitude']-previous['longitude'])
                distance=6371000*2*math.asin(min(1,math.sqrt(math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2)))
                if gap<=0 or distance>150*gap+(p['accuracy'] or 0)+(previous['accuracy'] or 0):seq=None;reason='implausible_jump'
        if previous:
            before=elapsed_seconds(previous['elapsed']);after=elapsed_seconds(p['elapsed'])
            if before is not None and after is not None and after<before:
                seq=None;reason='monotonic_reset'
        if seq is None:
            seq=uuid.uuid4().hex;ordinal=0
            db.execute('INSERT INTO movement_sequences VALUES(?,?,?,?,?,?)',(seq,iid,ts,ts,reason,VERSION))
        ordinal+=1
        db.execute('''INSERT OR IGNORE INTO movement_samples(position_id,sequence_id,ordinal,observed_at,elapsed_raw,network_observation_id)
            VALUES(?,?,?,?,?,?)''',(p['id'],seq,ordinal,ts,p['elapsed'],context.at(iid,ts)['network_id']))
        db.execute('UPDATE movement_sequences SET end=? WHERE id=?',(ts,seq));previous=p
    db.execute('INSERT INTO meta VALUES(?,?)',(marker,VERSION))


def pending(db):
    with db:
        for iid, in db.execute('SELECT id FROM imports').fetchall():enrich(db,iid)


def expand(db,data):
    if not data:return []
    ids={r['id'] for r in data};sources={}
    # Bounded by the selected observations; parameter batches stay below SQLite limits.
    selected=list(ids)
    for start in range(0,len(selected),500):
        part=selected[start:start+500];marks=','.join('?' for _ in part)
        for r in db.execute(f'''SELECT DISTINCT ev.observation_id,p.import_id FROM geo_mos_evidence ev
            JOIN metrics m ON m.id=ev.metric_id JOIN perspectives p ON p.id=m.perspective_id
            LEFT JOIN observation_roles role ON role.perspective_id=p.id
            WHERE ev.observation_id IN ({marks}) AND (role.role IS NULL OR role.role='app')''',part):
            sources.setdefault(r[0],set()).add(r[1])
    context=Context(db,{iid for ii in sources.values() for iid in ii});out=[]
    for r in data:
        for iid in sources.get(r['id'],[]):
            bounds=context.boundaries(iid,r['start'],r['end'])
            for a,b in zip(bounds,bounds[1:]):
                out.append(dict(r,start=a,end=b,context=context.at(iid,a)))
                if len(out)>500000:raise ValueError('Troppi intervalli di rete: restringere il periodo')
    return sorted(out,key=lambda r:(r['signature'],r['start'],r['end']))


def filters(params):
    allowed={'platform':('all','android','ios','desktop','unknown'), 'access':('all','cellular','wifi','ethernet','other','unknown'),
             'upstream':('all','mobile_direct','tethering','onboard_wifi','fixed','unknown')}
    out={k:params.get(k,'all') for k in (*allowed,'operator')}
    for k,values in allowed.items():
        if out[k] not in values:raise ValueError('Filtro di rete non valido')
    if len(out['operator'])>100:raise ValueError('Operatore non valido')
    return out


def matches(context,selected):
    return all(value=='all' or context.get(key,'unknown')==value for key,value in selected.items())


def summary(db):
    return dict(version=VERSION,max_gap_seconds=GAP,network_max_age_seconds=NETWORK_AGE,
        sequences=db.execute('SELECT count(*) FROM movement_sequences WHERE method=?',(VERSION,)).fetchone()[0],
        samples=db.execute('SELECT count(*) FROM movement_samples').fetchone()[0],
        network_observations=db.execute('SELECT count(*) FROM network_observations WHERE method=?',(VERSION,)).fetchone()[0],
        operators=[r[0] for r in db.execute("""SELECT operator FROM network_observations WHERE operator IS NOT NULL
            UNION SELECT json_extract(context,'$.operator') FROM telemetry_geo_context
            WHERE json_extract(context,'$.operator')!='unknown' ORDER BY 1 LIMIT 100""")])
