"""Local SIP-header configuration snapshots, not transmitted SIP or fresh GPS fixes."""
import json
import math
import re
from datetime import datetime

VERSION = 'ios-location-config-1'


def extract(text, ts):
    if not ts: return []
    match=re.search(r'^\[[^\]\n]+\] \[(?:KPECORE|CORE)\] \[INFO\] Adding extra headers to sip messages:\s*(\{)',text)
    if not match: return []
    try:
        body=json.loads(text[match.start(1):])
        headers=body.get('extraHeaders',[])
        if not isinstance(headers,list): return []
    except (ValueError,TypeError,AttributeError): return []
    out={}
    for header in headers:
        if not isinstance(header,dict) or not isinstance(header.get('headerName'),str) or header['headerName'].lower()!='x-location': continue
        values=header.get('values',[])
        if not isinstance(values,list): continue
        for value in values:
            if not isinstance(value,dict) or not isinstance(value.get('headerVal'),str): continue
            m=re.fullmatch(r'geo:([+-]?[\d.eE+-]+),([+-]?[\d.eE+-]+)(?:;[^\r\n]*)?',value['headerVal'])
            if not m: continue
            try:lat,lon=map(float,m.groups())
            except ValueError:continue
            if not math.isfinite(lat) or not math.isfinite(lon): continue
            out[(lat,lon)]=dict(ts=datetime.fromisoformat(ts).isoformat(' ',timespec='microseconds'),
                latitude=lat,longitude=lon,valid=int(-90<=lat<=90 and -180<=lon<=180))
    return list(out.values())


def enrich(db,iid):
    marker=f'{VERSION}:{iid}'
    if db.execute('SELECT 1 FROM meta WHERE key=?',(marker,)).fetchone():return 0
    previous={};added=0
    for e in db.execute("""SELECT * FROM events WHERE import_id=?
        AND instr(text,'Adding extra headers to sip messages:')>0
        ORDER BY ts,id""",(iid,)):
        for p in extract(e['text'],e['ts']):
            # Same configuration is logged by multiple layers and for several SIP methods.
            # Anchor the one-second dedup window; do not collapse stationary minute updates.
            key=(e['call_id'],p['latitude'],p['longitude'],p['valid'])
            t=datetime.fromisoformat(p['ts'])
            if key in previous and (t-previous[key]).total_seconds()<=1:continue
            previous[key]=t
            cursor=db.execute('''INSERT OR IGNORE INTO geo_positions
                (event_id,import_id,call_id,source_line,ts,latitude,longitude,accuracy,elapsed,kind,valid,method)
                VALUES(?,?,?,?,?,?,?,NULL,NULL,'sip_config',?,'geo-mos-1')''',
                (e['id'],iid,e['call_id'],e['line_no'],p['ts'],p['latitude'],p['longitude'],p['valid']))
            added+=cursor.rowcount
    db.execute('INSERT INTO meta VALUES(?,?)',(marker,VERSION))
    return added
