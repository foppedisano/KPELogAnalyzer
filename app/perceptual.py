"""AWT occupancy in wall-clock seconds, derived read-only from original evidence."""
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta
from .incidents import signal, reconstruct
from .transients import observed_timestamp

NAME = 'derived.perceptual_quality'
METHOD = 'awt-occupancy-4'
SECOND = 1000000
LIMIT = 100000


def tick(ts):
    return round((datetime.fromisoformat(ts)-datetime(1970, 1, 1)).total_seconds()*SECOND)


def stamp(t):
    return (datetime(1970, 1, 1)+timedelta(microseconds=t)).isoformat(' ', timespec='microseconds')


def union(spans):
    out = []
    for a, b in sorted(spans):
        if b <= a: continue
        if out and a <= out[-1][1]: out[-1] = (out[-1][0], max(b, out[-1][1]))
        else: out.append((a, b))
    return out


def overlap(spans, a, b):
    return sum(max(0, min(y,b)-max(x,a)) for x,y in union(spans))


def windows(episodes, counters, start, end, seconds=None):
    """State occupancy: outside episodes is 100, assuming complete AWT logging."""
    spans=[]; evidence=[]
    baseline=[proof for m in counters[:1] for proof in m['evidence']]
    if not baseline and episodes: baseline=episodes[0]['evidence'][:1]
    for e in episodes:
        b=round(e['end']*SECOND) if e['end'] is not None else end
        b=min(b,e.get('active_until',end))
        if e.get('start_basis')=='unknown': continue
        if e.get('start_basis')=='observed' or e['status']!='closed':
            a=round(e['start']*SECOND)
        elif e['duration_ms'] is not None and math.isfinite(e['duration_ms']) and e['duration_ms']>=0:
            a=b-round(e['duration_ms']*1000)
        else:
            a=round(e['start']*SECOND)
        a=max(a,start);b=min(b,end)
        if a<b: spans.append((a,b));evidence.append((a,b,e['evidence']))
    spans=union(spans)
    if seconds is None and end-start > LIMIT*SECOND: raise ValueError('Oltre 100.000 secondi: restringere la chiamata')
    out=[]
    bins=range(start//SECOND*SECOND, end, SECOND) if seconds is None else sorted(set(seconds))
    for bucket in bins:
        a=max(bucket,start);b=min(bucket+SECOND,end)
        if b<=a: continue
        ms=overlap(spans,a,b)/1000
        percent=100*ms/((b-a)/1000)
        proofs={(p['event_id'],p.get('metric_id'),p['line']):p for p in baseline}
        for x,y,pp in evidence:
            if x<b and y>a:
                for p in pp: proofs[(p['event_id'],p.get('metric_id'),p['line'])]=p
        out.append(dict(ts=stamp(a),valid_until=stamp(b),value=100-percent,
                        window_ts=stamp(bucket),observed_ms=(b-a)/1000,
                        underrun_ms=ms,underrun_percent=percent,evidence=list(proofs.values()),
                        coverage_basis='complete_awt_log_assumed'))
    return out


def bounded_perspective(db, p):
    """Bound an unclosed call by its own last source-local evidence, never now."""
    p=dict(p)
    p.setdefault('end_basis','observed_termination')
    if not p['end']:
        last=db.execute('SELECT max(ts) FROM events WHERE import_id=? AND call_id=?',
                        (p['import_id'],p['call_id'])).fetchone()[0]
        if not last: return None
        p['end']=stamp(tick(last)+1)
        p['end_basis']='last_call_evidence'
    return p


def perspective(db, p, seconds=None):
    p=bounded_perspective(db,p)
    if not p: return []
    start=tick(p['connected'] or p['start']);end=tick(p['end'])
    counters=defaultdict(list)
    raw=list(db.execute("""SELECT m.*,e.text,f.name filename FROM metrics m JOIN events e ON e.id=m.event_id
        JOIN files f ON f.id=e.file_id WHERE m.perspective_id=? AND m.name IN ('vd.silence_played','vd.buffer')
        AND m.unit='ms' AND m.statistic='sample'
        ORDER BY m.ts,m.id LIMIT 100001""",(p['id'],)))
    if len(raw)>LIMIT: raise ValueError('Troppi campioni AWT')
    for r in raw:
        if not re.fullmatch(r'NART\d+ of Line '+str(p['line_id']),r['input_device']): continue
        observers=re.findall(r'\[(AWT(?: - [^\]]+)?)\]',r['text'].split('\n',1)[0])
        if len(observers)!=1: continue
        key=(observers[0],r['input_device'])
        counters[key].append(dict(t=tick(observed_timestamp(r['text'],r['ts'])[0]),value=r['value'],valid=r['valid'],
            lifecycle=r['lifecycle'],evidence=[dict(event_id=r['event_id'],metric_id=r['id'],filename=r['filename'],line=r['source_line'])]))
    events=list(db.execute("""SELECT e.*,f.name filename FROM events e JOIN files f ON f.id=e.file_id
        WHERE e.import_id=? AND e.ts>=? AND e.ts<=? AND (e.call_id=? OR e.call_id IS NULL)
        AND (e.text LIKE '%buffer underrun%' AND e.text LIKE '%input device%' OR e.text LIKE '%Creating device%')
        ORDER BY e.ts,e.id LIMIT 100001""",(p['import_id'],p['start'],p['end'],p['call_id'])))
    if len(events)>LIMIT or sum(map(len,counters.values()))>LIMIT: raise ValueError('Troppi eventi AWT')
    signals=[];unassigned=[];life={};creations=[]
    for row in events:
        row=dict(row);row['ts']=observed_timestamp(row['text'],row['ts'])[0]
        header=row['text'].split('\n',1)[0]
        created=re.search(r'Creating device\s+(.*?)\s*$',header)
        if created:
            life[created[1]]=str(row['id']);creations.append((created[1],tick(row['ts'])));continue
        source=re.search(r'input device\s+(NART\d+ of Line \d+)\s*\.',header)
        if not source: continue
        observers=re.findall(r'\[(AWT(?: - [^\]]+)?)\]',header)
        if len(observers)!=1: continue
        # signal expects a bracketed timestamp; Android's outer timestamp is not bracketed.
        row['text']='['+row['ts']+'] '+header[header.index('['+observers[0]+']'):]
        source_line=int(re.search(r'of Line (\d+)',source[1])[1])
        s=signal(row,source[1],p['line_id'] if p['line_id'] is not None else source_line)
        if not s or not re.fullmatch(r'AWT(?: - .+)?',s['observer']): continue
        if s['duration_ms'] is not None and not math.isfinite(s['duration_ms']): s['duration_ms']=None
        if p['line_id'] is None and row['call_id'] != p['call_id']:
            # Potential local incidents are not silently converted to healthy audio.
            # Keep the uncertain intervals separate; no time-only call association.
            unassigned.append(s)
            continue
        # An unassigned line is usable only in one unambiguous source-local window.
        count=db.execute('SELECT count(*) FROM perspectives WHERE import_id=? AND line_id=? AND start<=? AND (end IS NULL OR end>=?)',
                         (p['import_id'],p['line_id'],row['ts'],row['ts'])).fetchone()[0]
        if count!=1:
            unassigned.append(s)
            continue
        output=s['observer'].removeprefix('AWT - ') if s['observer']!='AWT' else 'Default Audio Output'
        s['key']+=(life.get(output,'unknown'),life.get(s['device'],'unknown'))
        signals.append(s)
    episodes=defaultdict(list)
    for e in reconstruct(signals):
        output=e['observer'].removeprefix('AWT - ') if e['observer']!='AWT' else 'Default Audio Output'
        e['active_until']=min([t for d,t in creations if d in (output,e['device']) and t>round(e['detected_at']*SECOND)]+[end])
        episodes[(e['observer'],e['device'])].append(e)
    result=[]
    keys=counters.keys()|episodes.keys()
    if not keys:
        keys={('AWT (assunto durante la chiamata)','')}
    call_proofs=[dict(event_id=r['id'],filename=r['filename'],line=r['line_no'],basis='call_lifecycle') for r in db.execute('''
        SELECT e.id,e.line_no,f.name filename FROM events e JOIN files f ON f.id=e.file_id
        WHERE e.import_id=? AND e.call_id=? ORDER BY e.ts,e.id LIMIT 1''',(p['import_id'],p['call_id']))]
    uncertain=[]
    for e in reconstruct(unassigned):
        a=start if e.get('start_basis')=='unknown' else round(e['start']*SECOND)
        b=round(e['end']*SECOND) if e['end'] is not None else end
        uncertain.append((a,max(a+1,b)))
    for key in keys:
        for w in windows(episodes[key],counters[key],start,end,seconds):
            if overlap(uncertain,tick(w['ts']),tick(w['valid_until'])): continue
            if not w['evidence']: w['evidence']=call_proofs
            if not w['evidence']: continue
            proof=w['evidence'][0]
            result.append(dict(w,id=proof['event_id'],event_id=proof['event_id'],name=NAME,unit='PQ',statistic='sample',valid=1,
                perspective_id=p['id'],call_id=p['call_id'],import_id=p['import_id'],start=p['start'],label=p['label'],clock_offset=p['clock_offset'],
                filename=proof['filename'],line_no=proof['line'],direction='incoming',flow='',ssrc='',device=key[1],input_device=key[1],
                output_device=key[0].removeprefix('AWT - ') if key[0]!='AWT' else 'Default Audio Output',observer=key[0],
                sample_kind='interval',interval_seconds=w['observed_ms']/1000,end_basis=p['end_basis'],
                extractor=METHOD,placement_basis='observed_state_or_reported_start'))
    return sorted(result,key=lambda r:(r['ts'],r['observer'],r['device']))


def calculate(db, ids):
    if not ids: return []
    ps=db.execute('SELECT p.*,i.label,i.clock_offset FROM perspectives p JOIN imports i ON i.id=p.import_id WHERE p.call_id IN ('+','.join('?' for _ in ids)+')',ids).fetchall()
    result=[]
    for p in ps:
        result.extend(perspective(db,p))
        if len(result)>LIMIT: raise ValueError('Oltre 100.000 campioni Perceptual Quality: restringere la selezione')
    return result
