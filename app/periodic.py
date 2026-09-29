"""Recent textual periodic observations, with explicit reader/input context.

No version inference, SSRC inference, or counter-to-episode conversion.
"""
import hashlib
import json
import math
import re
from datetime import datetime

VERSION = 'periodic-1'
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
NUMBER_END = r'(?![\w]|\.\d)'
SCHEMA = '''
ALTER TABLE metrics ADD COLUMN observer TEXT NOT NULL DEFAULT '';
ALTER TABLE metrics ADD COLUMN output_device TEXT NOT NULL DEFAULT '';
ALTER TABLE metrics ADD COLUMN input_device TEXT NOT NULL DEFAULT '';
ALTER TABLE metrics ADD COLUMN lifecycle TEXT NOT NULL DEFAULT '';
CREATE TABLE periodic_metadata(
 id INTEGER PRIMARY KEY,event_id INTEGER NOT NULL REFERENCES events(id),
 import_id INTEGER NOT NULL REFERENCES imports(id), perspective_id INTEGER REFERENCES perspectives(id),
 call_id INTEGER REFERENCES calls(id),ts TEXT NOT NULL,source_line INTEGER NOT NULL,
 observer TEXT NOT NULL,output_device TEXT NOT NULL,input_device TEXT NOT NULL,
 device TEXT NOT NULL,line_id INTEGER,flow TEXT NOT NULL,ssrc TEXT NOT NULL,
 lifecycle TEXT NOT NULL,name TEXT NOT NULL,value_json TEXT NOT NULL,extractor TEXT NOT NULL);
CREATE INDEX periodic_event ON periodic_metadata(event_id);
CREATE INDEX periodic_call ON periodic_metadata(call_id,ts);
CREATE INDEX metric_event ON metrics(event_id);
CREATE INDEX metric_perspective ON metrics(perspective_id,name,ts);
CREATE TABLE periodic_evidence(
 import_id INTEGER NOT NULL REFERENCES imports(id), signature TEXT NOT NULL,
 metric_id INTEGER REFERENCES metrics(id),metadata_id INTEGER REFERENCES periodic_metadata(id),
 PRIMARY KEY(import_id,signature));
CREATE INDEX periodic_metric_evidence ON periodic_evidence(metric_id);
'''

# label, metric, original unit, kind. Units only come from explicit field text.
FIELDS = [
 ('Audio currently in buffer (ms)','buffer','ms','gauge'),
 ('silence msecs skipped so far','silence_skipped','ms','counter'),
 ('ring current max buffer usecs (for dynamic dejittering)','dejitter_target','us','gauge'),
 ('audio samples skipped so far','samples_skipped','samples','counter'),
 ('ring hard max buffer usecs','buffer_hard_max','us','gauge'),
 ('ring min buffer usecs','buffer_min','us','gauge'),
 ('number of buffer underruns occurred on this ring for this VOD','underruns','count','counter'),
 ('silence msecs played out for buffer underruns occurred on this ring for this VOD','silence_played','ms','counter'),
 ('Total bytes read from source','bytes_read','bytes','counter'),
 ('Total bytes sent to decoder','bytes_decoder','bytes','counter'),
 ('Total packets/chunks sent to decoder','chunks_decoder','chunks','counter'),
 ('Total media read from middleware','media_read','ms','counter'),
 ('Total media sent out','media_sent','ms','counter'),
 ('Total media sent to middleware','media_middleware','ms','counter'),
 ('Number of device reset for scheduling delay','scheduling_resets','count','counter'),
]
for label, key in [('ALL','all'),('RTP','rtp'),('RTCP','rtcp'),('RTP GOOD','rtp_good'),('RTP BAD','rtp_bad')]:
    FIELDS.append((label+' Pkts received so far','packets_'+key,'packets','counter'))
for category in ('Read','Write','Encoding','Decoding'):
    FIELDS.extend([('Number of '+category+' Errors',category.lower()+'_errors','count','counter'),
                   ('Current '+category.lower()+' error event duration (msecs)',category.lower()+'_error_duration','ms','gauge')])
for category in ('GOOD','BAD'):
    FIELDS.append(('RTP last streak of '+category+' Pkts received','streak_'+category.lower(),'packets','gauge'))
FIELDS_BY_LABEL = {label.casefold(): (name,unit,kind) for label,name,unit,kind in FIELDS}
FIELD_NUMBER = re.compile(r'^\s*('+NUMBER+r')'+NUMBER_END)


def context(text):
    header = text.split('\n',1)[0]
    brackets = re.findall(r'\[([^]]+)\]',header)
    observer = brackets[1] if len(brackets)>1 else ''
    return dict(observer=observer,output_device='',input_device='',device='',line_id=None,flow='?',ssrc='')


def observations(text, parser):
    c = context(text)
    connected = False
    recent = 'READING Virtual Output Device Running Info' in text
    heartbeat = re.search(r'VD\s+(\d+)\s+\(\s*(.*?)\s*\)\s+is alive and kicking',text)
    if heartbeat:
        c['device']=heartbeat[2]
    for offset,line in enumerate(text.splitlines()):
        if 'CONNECTED INPUT DEVICE' in line.upper():
            connected = True
            c['device']=c['input_device']=''
        if 'Device name:' in line:
            c['device']=line.split('Device name:',1)[1].strip()
            c['input_device' if connected else 'output_device']=c['device']
            if not connected: c['input_device']=''
        # Scope is recomputed for every device: an unrelated input never inherits a line.
        identity = re.search(r'NA[RW]T(\d+) of Line (\d+)',c['device'])
        if not identity and c['input_device']=='Default Audio Input':
            identity = re.search(r'NAWT(\d+) of Line (\d+)',c['output_device'])
        if parser == 'rtcp':
            identity = re.search(r'LINE\s+(\d+)\s+FLOW\s+(\d+)',text,re.I)
            c['line_id']=int(identity[1]) if identity else None
            c['flow']=identity[2] if identity else '?'
            ssrc=re.search(r'SSRC of this source:\s*(\w+)',text)
            c['ssrc']=ssrc[1] if ssrc else ''
        else:
            c['line_id']=int(identity[2]) if identity else None
            c['flow']=identity[1] if identity else '?'
        def numeric(name,value,unit,kind):
            raw=float(value)
            if not math.isfinite(raw): return None
            return dict(c,name=name,value=raw/1000 if unit=='us' else raw,unit='ms' if unit=='us' else unit,
                        raw_value=raw,raw_unit=unit,sample_kind=kind,valid=int(raw>=0 and (unit not in ('count','packets','samples','bytes','chunks') or raw.is_integer())),source_offset=offset,
                        direction='outgoing' if c['device'].startswith('NAWT') or c['output_device'].startswith('NAWT') else 'incoming' if c['device'].startswith('NART') else 'unknown')
        def metadata(name,value):
            return dict(c,name=name,value_json=json.dumps(value,ensure_ascii=False),source_offset=offset)
        if parser=='vd' and (recent or heartbeat):
            label,separator,body=line.strip().partition(':')
            field=FIELDS_BY_LABEL.get(label.strip().casefold()) if separator else None
            if field:
                name,unit,kind=field
                m=FIELD_NUMBER.search(body)
                if m:
                    actual_unit=unit
                    if name.startswith('media_') and not re.match(r'\s+ms\b',body[m.end():]): actual_unit='raw'
                    result=numeric('vd.'+name,m[1],actual_unit,kind)
                    if result: yield result
            for name,pattern,unit,kind in [
                ('write_rate',r'Cumulative write rate is\s+('+NUMBER+r')\s+samples per second','samples/s','gauge'),
                ('scheduling_delay',r'Accumulated delay is\s+('+NUMBER+r')\s+ms','ms','counter'),
                ('underrun_duration',r'Currently in underrun for this VOD\s+since\s+('+NUMBER+r')\s+msecs','ms','gauge'),
                ('heartbeat_bytes_read',r'read bytes:\s*('+NUMBER+r')','bytes','reported statistic'),
                ('heartbeat_bytes_written',r'written bytes\s+('+NUMBER+r')','bytes','reported statistic'),
                ('heartbeat_window',r'Running cycles \(last\s+('+NUMBER+r')\s+ms\)','ms','interval'),
            ]:
                m=re.search(pattern,line,re.I)
                if m:
                    result=numeric('vd.'+name,m[1],unit,kind)
                    if result: yield result
            m=re.search(r'Running cycles.*? -\s*(.*?)\s*-\s*:\s*(.*)',line)
            if m:
                phases=[s.strip() for s in m[1].split(',')]
                values=m[2].strip().rstrip('.').split(',')
                if len(phases)==len(values)==5 and all(re.fullmatch(NUMBER,v.strip()) for v in values):
                    for phase,value in zip(phases,values):
                        key=re.sub(r'\W+','_',phase.lower())
                        result=numeric('vd.cycles_'+key,value,'count','reported statistic' if heartbeat else 'counter')
                        if result: yield result
            m=re.search(r'(Currently in (?:total buffer underrun|partial buffer underrun|buffer underrun on this VOD|\w+ error event)):\s*(yes|no)\b',line,re.I)
            if m: yield metadata('vd.'+re.sub(r'\W+','_',m[1].lower()),m[2].lower()=='yes')
            m=re.search(r'(Current processing stage|Last (?:read|write) processing stage known):\s*([^\s.(]+)(?:\((\d+)\))?(?:\.\s*Timestamp\s+(.*?))?\s*$',line)
            if m: yield metadata('vd.'+m[1].lower().replace(' ','_'),dict(state=m[2],code=int(m[3]) if m[3] else None,timestamp=m[4].rstrip('.') if m[4] else None))
            m=re.search(r'(Last written RTP SN|RTP (?:last pkt(?: GOOD)? (?:SN|ROC)|(?:first|last) (?:GOOD|BAD) pkt SN)):\s*(\d+)\b',line)
            if m: yield metadata('vd.'+m[1].lower().replace(' ','_'),int(m[2]))
            if heartbeat and offset==0: yield metadata('vd.heartbeat_device_id',heartbeat[1])
        if parser=='vd':
            m=re.search(r'(NART|NAWT) status:\s*([A-Z_]+)\((\d+)\)\.\s*Timestamp\s+(.*)',line)
            if m:
                # A monitor header proves the line only; never assume its hardcoded flow is a measured flow.
                lm=re.search(r'\bLine\s+(\d+)',text,re.I)
                c.update(device=m[1],line_id=int(lm[1]) if lm else None,flow='?')
                yield metadata('vd.monitor_stage',dict(state=m[2],code=int(m[3]),timestamp=m[4].rstrip('.')))
        if parser=='rtcp' and 'RTCP ARRIVED' in text:
            from .parser import metrics
            for name,value,unit,direction,flow,ssrc,stat,valid in metrics(dict(text=text.split('\n',1)[0]+' RTCP ARRIVED\n'+line,parser='rtcp')):
                result=numeric(name,value,unit,'counter' if name.endswith(('_total','packets_received')) else 'interval' if 'packets_' in name else 'sample')
                if result:
                    result.update(valid=valid,direction=direction)
                    yield result
            m=re.search(r'(RTCP Message n\.|Sender Report -\s*(?:ntp timestamp received from this source|rtp timestamp corresponding to ntp time)):\s*(.*)',line)
            if m:
                key='message_number' if m[1].startswith('RTCP') else 'ntp_timestamp' if 'ntp timestamp' in m[1] else 'rtp_timestamp'
                value=m[2].strip()
                if value: yield metadata('rtcp.'+key,int(value) if key!='ntp_timestamp' and value.isdigit() else value)


def enrich(db,iid):
    marker=VERSION+':'+str(iid)
    if db.execute('SELECT 1 FROM meta WHERE key=?',(marker,)).fetchone(): return 0
    from .enrichment import observations as legacy
    from .source_dedup import skipped_windows,skip_measurement
    perspectives=[dict(p) for p in db.execute('SELECT * FROM perspectives WHERE import_id=?',(iid,))]
    ignored=skipped_windows(db,iid)
    lifecycles={}; creations={}; added=0
    for row in db.execute('''SELECT e.*,f.name filename,f.parser FROM events e JOIN files f ON f.id=e.file_id
        WHERE e.import_id=? AND e.ts IS NOT NULL AND f.parser IN ('vd','rtcp')
        AND (e.text LIKE '%Device name:%' OR e.text LIKE '%Creating device%'
             OR e.text LIKE '%RTCP ARRIVED%' OR e.text LIKE '%RTT by this source%'
             OR e.text LIKE '%alive and kicking%' OR e.text LIKE '%status:%'
             OR e.text LIKE '%m_maxPktArrivalTimeDelay%') ORDER BY e.ts,e.id''',(iid,)):
        e=dict(row)
        created=re.search(r'Creating device\s+(.*?)\s*$',e['text'])
        if created:
            key=(created[1],e['ts'])
            lifecycles[created[1]]=creations.setdefault(key,str(e['id']))
        samples=list(observations(e['text'],e['parser']))
        # Recover missing observer-specific old metrics without re-running vd-1 inserts.
        for old in legacy(e['text'],e['filename']):
            c=context(e['text']); connected=False
            for line in e['text'].splitlines()[:old['source_offset']+1]:
                if 'CONNECTED INPUT DEVICE' in line: connected=True
                if 'Device name:' in line:
                    dev=line.split('Device name:',1)[1].strip()
                    c['input_device' if connected else 'output_device']=dev
            samples.append(dict(old,observer=c['observer'],output_device=c['output_device'],input_device=c['input_device']))
        for m in samples:
            if skip_measurement(ignored,perspectives,m['line_id'],e['ts']): continue
            candidates=[p for p in perspectives if m['line_id'] is not None and p['line_id']==m['line_id'] and p['start']<=e['ts'] and
                        (not p['end'] or (datetime.fromisoformat(e['ts'])-datetime.fromisoformat(p['end'])).total_seconds()<=.25)]
            p=candidates[0] if len(candidates)==1 else None
            lifecycle='|'.join(lifecycles.get(d,'unknown') for d in (m['output_device'],m['device']))
            # Perspective stays a separate dimension; editing an analyst window must
            # not change the source lifecycle identity or the deduplication ledger.
            m['lifecycle']=lifecycle
            source_line=e['line_no']+m['source_offset']
            signature=hashlib.sha256(json.dumps([e['ts'],m['name'],m['observer'],m['output_device'],m['input_device'],m['device'],m['line_id'],m['flow'],m['ssrc'],lifecycle,m.get('value_json',m.get('value')),m.get('direction'),m.get('unit')],ensure_ascii=False).encode()).hexdigest()
            if db.execute('SELECT 1 FROM periodic_evidence WHERE import_id=? AND signature=?',(iid,signature)).fetchone(): continue
            mid=metaid=None
            if 'value_json' in m:
                keys=('observer','output_device','input_device','device','line_id','flow','ssrc','lifecycle','name','value_json')
                metaid=db.execute('INSERT INTO periodic_metadata(event_id,import_id,perspective_id,call_id,ts,source_line,'+','.join(keys)+',extractor) VALUES('+','.join('?' for _ in range(17))+')',
                    (e['id'],iid,p['id'] if p else None,p['call_id'] if p else None,e['ts'],source_line,*(m[k] for k in keys),VERSION)).lastrowid
            else:
                existing=db.execute('''SELECT id FROM metrics WHERE event_id=? AND name=? AND value=? AND direction=? AND flow=? AND ssrc=? AND device=?
                    AND (source_line=? OR source_line IS NULL) AND NOT EXISTS
                    (SELECT 1 FROM periodic_evidence pe WHERE pe.metric_id=metrics.id)
                    ORDER BY id LIMIT 1''',(e['id'],m['name'],m['value'],m['direction'],m['flow'],m['ssrc'],m['device'],source_line)).fetchone()
                if existing:
                    mid=existing[0]
                    db.execute('UPDATE metrics SET observer=?,output_device=?,input_device=?,lifecycle=?,source_line=?,raw_value=?,raw_unit=?,sample_kind=? WHERE id=?',
                               (m['observer'],m['output_device'],m['input_device'],lifecycle,source_line,m['raw_value'],m['raw_unit'],m['sample_kind'],mid))
                else:
                    keys=('name','value','unit','direction','flow','ssrc','valid','device','raw_value','raw_unit','sample_kind','observer','output_device','input_device','lifecycle')
                    mid=db.execute('INSERT INTO metrics(event_id,perspective_id,call_id,ts,source_line,'+','.join(keys)+',extractor) VALUES('+','.join('?' for _ in range(21))+')',
                        (e['id'],p['id'] if p else None,p['call_id'] if p else None,e['ts'],source_line,*(m[k] for k in keys),VERSION)).lastrowid
                    added+=1
            db.execute('INSERT INTO periodic_evidence VALUES(?,?,?,?)',(iid,signature,mid,metaid))
    db.execute('INSERT INTO meta VALUES(?,?)',(marker,VERSION))
    return added
