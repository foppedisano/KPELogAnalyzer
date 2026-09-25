"""Reconstruct audio incidents from explicit lifecycle messages, never counters."""
import re
from datetime import datetime

NUM = r'(\d+(?:\.\d+)?)'
UNIT = r'(microseconds|usecs|msecs|milliseconds|ms|seconds|secs|sec|s)\b'


def epoch(ts):
    return (datetime.fromisoformat(ts) - datetime(1970, 1, 1)).total_seconds()


def duration_ms(value, unit):
    return float(value) * (.001 if unit in ('microseconds', 'usecs') else 1 if unit in ('msecs','milliseconds','ms') else 1000)


def signal(event, selected_device, line_id):
    text = event['text'].split('\n', 1)[0]
    proof = dict(event_id=event['id'], filename=event['filename'], line=event['line_no'])
    media = re.search(r'Line\s+(\d+)\s+reported that flow\s+(\d+)\s+(.*)', text, re.I)
    if media and int(media[1]) == line_id:
        missing = re.search(r'has not received RTP media for more than\s+'+NUM+r'\s*'+UNIT, media[3], re.I)
        recovery = re.search(r'has (?:re-started receiving RTP media|started receiving RTP media again)', media[3], re.I)
        if missing or recovery:
            return dict(kind='media_missing', phase='missing' if missing else 'end', key=('media_missing',media[2]),
                        observer='RTP flow '+media[2], device='Linea '+str(line_id), flow=media[2],
                        duration_ms=duration_ms(missing[1],missing[2].lower()) if missing else None,
                        t=epoch(event['ts']), evidence=proof)
    device_line=re.search(r'of Line (\d+)',selected_device,re.I)
    if device_line and int(device_line[1])!=line_id: return None
    if 'buffer underrun' not in text.lower():
        return None
    source = re.search(r'input device\s+(.*?)\s*\.(?:\s|$)', text, re.I)
    if not source or source[1].strip().lower() != selected_device.lower():
        return None
    headers = re.findall(r'\[([^\]]+)\]', text)
    observer = headers[1] if len(headers)>1 else 'Sconosciuto'
    phase = 'start' if 'Buffer underrun occurred' in text else 'end' if 'Buffer underrun event terminated' in text else 'ongoing' if 'Still in buffer underrun' in text else None
    if not phase:
        return None
    elapsed = re.search(r'Event (?:was|is currently)\s+'+NUM+r'\s*'+UNIT, text, re.I)
    return dict(kind='buffer_underrun',phase=phase,key=('buffer_underrun',selected_device,observer),
                observer='Registrazione VD' if observer.startswith('VD ') else observer,
                device=selected_device,flow='',duration_ms=duration_ms(elapsed[1],elapsed[2].lower()) if elapsed else None,
                t=epoch(event['ts']),evidence=proof)


def reconstruct(signals):
    pending = {}; episodes = []; seen = set()
    for s in sorted(signals,key=lambda s:s['t']):
        signature = (s['key'],s['phase'],s['t'],s['duration_ms'])
        if signature in seen: continue
        seen.add(signature)
        key=s['key']; t=s['t']; reported=s['duration_ms']
        current=pending.get(key)
        if s['phase'] in ('start','missing'):
            if current is not None:
                # Repeated missing notifications do not start another overlapping outage.
                if s['phase']=='missing':
                    current['evidence'].append(s['evidence'])
                    current['start']=min(current['start'],t-reported/1000)
                    current['last_observed']=t
                    current['duration_ms']=(t-current['start'])*1000
                    continue
                episodes.append(current)
            inferred = s['phase']=='missing'
            current=dict(kind=s['kind'],observer=s['observer'],device=s['device'],flow=s['flow'],
                         start=t-reported/1000 if inferred else t,end=None,last_observed=t,
                         duration_ms=reported if inferred else None, duration_basis='minimum' if inferred else 'unknown',
                         start_basis='threshold' if inferred else 'observed',status='open',evidence=[s['evidence']],
                         detected_at=t,stream=repr(key))
            pending[key]=current
        elif s['phase']=='ongoing':
            if current is None:
                current=dict(kind=s['kind'],observer=s['observer'],device=s['device'],flow=s['flow'],
                             start=t-reported/1000 if reported is not None else t,end=None,last_observed=t,
                             duration_ms=reported,duration_basis='minimum' if reported is not None else 'unknown',
                             start_basis='reported_elapsed',status='open',evidence=[],detected_at=t,stream=repr(key))
                pending[key]=current
            current['last_observed']=t
            if reported is not None: current['duration_ms']=reported;current['duration_basis']='minimum'
            current['evidence'].append(s['evidence'])
        else:
            if current is None:
                current=dict(kind=s['kind'],observer=s['observer'],device=s['device'],flow=s['flow'],
                             start=t-reported/1000 if reported is not None else t,end=None,last_observed=t,
                             duration_ms=None,duration_basis='unknown',start_basis='reported_duration' if reported is not None else 'unknown',
                             status='closed',evidence=[],detected_at=t,stream=repr(key))
            current['end']=t;current['last_observed']=t;current['status']='closed';current['evidence'].append(s['evidence'])
            if reported is not None:
                current['duration_ms']=reported;current['duration_basis']='reported'
            elif current['start_basis']=='threshold':
                current['duration_ms']=max(0,(t-current['start'])*1000);current['duration_basis']='minimum'
            elif current['start_basis']=='observed':
                current['duration_ms']=max(0,(t-current['start'])*1000);current['duration_basis']='timestamps'
            else: current['duration_ms']=None;current['duration_basis']='unknown'
            current['wall_span_ms']=max(0,(t-current['start'])*1000) if current['start_basis']!='unknown' else None
            episodes.append(current);pending.pop(key,None)
    episodes.extend(pending.values())
    return episodes


def incidents(db, perspective_id, device, offset=0, start=None, end=None):
    p=db.execute('SELECT * FROM perspectives WHERE id=?',(perspective_id,)).fetchone()
    if p['line_id'] is None:
        return dict(episodes=[],warning='Linea non nota: episodi non attribuibili con certezza.')
    # Entire lifecycle before clipping: never lose a start just outside the display window.
    args=[p['import_id'],p['start']]
    upper=''
    if p['end']: upper=' AND e.ts<=?';args.append(p['end'])
    cursor=db.execute('''SELECT e.id,e.ts,e.text,e.line_no,e.call_id,f.name filename FROM events e JOIN files f ON f.id=e.file_id
        WHERE e.import_id=? AND e.ts>=? '''+upper+''' AND ((e.text LIKE '%underrun%' AND e.text LIKE '%input device%')
        OR e.text LIKE '%reported that%flow%') ORDER BY e.ts,e.id LIMIT 100001''',args)
    signals=[];count=0
    for row in cursor:
        count+=1
        if count>100000: raise ValueError('Troppi eventi audio nella chiamata: massimo 100.000')
        # Never borrow events explicitly assigned to another call; line scope also checked in signal().
        if row['call_id'] is not None and row['call_id'] != p['call_id']: continue
        s=signal(dict(row),device,p['line_id'])
        if s: signals.append(s)
    out=[]
    for episode in reconstruct(signals):
        for key in ('start','end','last_observed','detected_at'):
            if episode.get(key) is not None: episode[key]+=offset
        right=episode['end'] if episode['end'] is not None else episode['last_observed']
        if (start is not None and right<start) or (end is not None and episode['start']>end): continue
        episode['plot_start']=max(episode['start'],start) if start is not None else episode['start']
        episode['plot_end']=min(right,end) if end is not None else right
        episode['clipped']=episode['plot_start']!=episode['start'] or episode['plot_end']!=right
        episode['perspective_id']=perspective_id
        out.append(episode)
    return dict(episodes=out,warning='Underrun riferiti al device selezionato, separati per osservatore. Media missing: durata minima ricavata dalla soglia; senza ripresa resta aperto. Contatori e riepiloghi non sono nuovi episodi.')
