"""On-demand single-perspective calculations for call and comparison charts."""
from datetime import datetime, timedelta
from .db import rows
from .incidents import incidents

SINGLE_DERIVED = ('derived.mos_reference', 'derived.silence_delta', 'derived.silence_played_delta', 'incident.buffer_underrun', 'incident.media_missing')


def silence_delta(points, max_gap=30):
    from collections import Counter
    simultaneous=Counter(p['t'] for p in points)
    output=[]
    for previous,current in zip(points,points[1:]):
        elapsed=current['t']-previous['t']
        if simultaneous[previous['t']]==simultaneous[current['t']]==1 and previous.get('valid',1) and current.get('valid',1) and 0<elapsed<=max_gap and current['value']>=previous['value']:
            output.append(dict(t=current['t'],value=current['value']-previous['value'],
                interval_seconds=elapsed,evidence=[previous['evidence'],current['evidence']]))
    return output


def calculate(db, ids, name):
    if name == 'derived.mos_reference':
        from .mos import calculate as mos
        return mos(db, ids)
    marks=','.join('?' for _ in ids)
    if name in ('derived.silence_delta','derived.silence_played_delta'):
        source='vd.silence_played' if name=='derived.silence_played_delta' else 'vd.silence_skipped'
        data=rows(db,f'''SELECT m.*,i.label,i.clock_offset,p.start,p.line_id,f.name filename,
            COALESCE(m.source_line,e.line_no) line_no FROM metrics m
            JOIN perspectives p ON p.id=m.perspective_id JOIN imports i ON i.id=p.import_id
            JOIN events e ON e.id=m.event_id JOIN files f ON f.id=e.file_id
            WHERE m.call_id IN ({marks}) AND m.name=?
            AND m.statistic='sample' AND m.unit='ms'
            ORDER BY m.ts,m.id LIMIT 100001''',(*ids,source))
        if len(data)>100000: raise ValueError('Oltre 100.000 campioni: restringi la selezione')
        groups={}
        for m in data:
            key=tuple(m[k] for k in ('perspective_id','device','flow','ssrc','direction','unit','sample_kind','observer','output_device','input_device','lifecycle'))
            groups.setdefault(key,[]).append(m)
        output=[]
        for group in groups.values():
            points=[dict(t=(datetime.fromisoformat(m['ts'])-datetime(1970,1,1)).total_seconds(),value=m['value'],valid=m['valid'],
                evidence=dict(event_id=m['event_id'],metric_id=m['id'],filename=m['filename'],line=m['line_no'])) for m in group]
            originals={m['id']:m for m in group}
            for d in silence_delta(points):
                original=originals[d['evidence'][1]['metric_id']]
                output.append(dict(original,name=name,value=d['value'],sample_kind='interval',
                    interval_seconds=d['interval_seconds'],evidence=d['evidence'],extractor='derived-on-demand'))
        return sorted(output,key=lambda m:(m['ts'],m['id']))
    output=[]
    for p in rows(db,f'''SELECT p.*,i.label,i.clock_offset FROM perspectives p
        JOIN imports i ON i.id=p.import_id WHERE p.call_id IN ({marks})''',ids):
        devices=[r[0] for r in db.execute("SELECT DISTINCT device FROM metrics WHERE perspective_id=? AND device LIKE 'NART%'",(p['id'],))]
        if not devices: devices=[f"NART0 of Line {p['line_id']}"]
        seen=set()
        for device in devices:
            for episode in incidents(db,p['id'],device)['episodes']:
                if 'incident.'+episode['kind']!=name: continue
                key=tuple(e['event_id'] for e in episode['evidence'])
                if key in seen: continue
                seen.add(key)
                proof=episode['evidence'][-1]
                output.append(dict(id=proof['event_id'],event_id=proof['event_id'],perspective_id=p['id'],
                    call_id=p['call_id'],label=p['label'],clock_offset=p['clock_offset'],start=p['start'],
                    ts=(datetime(1970,1,1)+timedelta(seconds=episode['detected_at'])).isoformat(' ',timespec='microseconds'),
                    name=name,value=episode['duration_ms'],unit='ms',statistic='sample',valid=1,
                    direction='incoming',flow=episode['flow'],ssrc='',device=episode['device'],
                    sample_kind='episode',filename=proof['filename'],line_no=proof['line'],
                    observer=episode['observer'],evidence=episode['evidence'],episode=episode))
                if len(output)>100000: raise ValueError('Troppi episodi: restringi la selezione')
    return sorted(output,key=lambda m:(m['ts'],m['id']))
