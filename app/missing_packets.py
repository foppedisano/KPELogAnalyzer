"""Explicit NART sequence-gap notifications; counts are not final packet loss."""
import re
from datetime import datetime

VERSION='missing-packets-1'
PATTERN=re.compile(r'\[(NART(\d+) of Line (\d+))\].*?Packet loss occurred\.'
    r'\s*Current packet SN is\s+(\d+)\s*\.\s*Previous packet SN was\s+(\d+)'
    r'\s+SN delta is\s+(\d+)\s*\(\s*(\d+)\s+missing packets?\s*\)',re.I)


def extract(text):
    for offset,line in enumerate(text.splitlines()):
        m=PATTERN.search(line)
        if m:
            count=int(m[7])
            if 0<count<=65535:
                yield dict(device=f'NART{m[2]} of Line {m[3]}',flow=m[2],line_id=int(m[3]),
                    value=count,source_offset=offset,signature=tuple(m.group(i) for i in range(1,8)))


def enrich(db,iid):
    marker=f'{VERSION}:{iid}'
    if db.execute('SELECT 1 FROM meta WHERE key=?',(marker,)).fetchone(): return
    perspectives=[dict(p) for p in db.execute('SELECT * FROM perspectives WHERE import_id=?',(iid,))]
    seen=set()
    for e in db.execute("SELECT * FROM events WHERE import_id=? AND ts IS NOT NULL AND lower(text) LIKE '%missing packet%' ORDER BY ts,id",(iid,)):
        for m in extract(e['text']):
            key=(e['ts'],m['signature'])
            if key in seen: continue
            seen.add(key)
            candidates=[p for p in perspectives if p['line_id']==m['line_id'] and p['start']<=e['ts']
                and (not p['end'] or (datetime.fromisoformat(e['ts'])-datetime.fromisoformat(p['end'])).total_seconds()<=.25)]
            p=candidates[0] if len(candidates)==1 else None
            db.execute('''INSERT INTO metrics(event_id,perspective_id,call_id,ts,name,value,unit,direction,
                flow,ssrc,statistic,valid,device,source_line,raw_value,raw_unit,sample_kind,extractor)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (e['id'],p['id'] if p else None,p['call_id'] if p else None,e['ts'],'vd.missing_packets',
                 m['value'],'packets','incoming',m['flow'],'','sample',1,m['device'],e['line_no']+m['source_offset'],
                 m['value'],'packets','event',VERSION))
    db.execute('INSERT INTO meta VALUES(?,?)',(marker,'done'))
