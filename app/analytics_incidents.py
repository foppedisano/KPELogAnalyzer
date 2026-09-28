"""Audio lifecycle evidence and duration occupancy, without exposing log text."""
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from .incidents import incidents, epoch

METHOD='incident-occupancy-1'
TABLES={
 'a_incidents': ('Audio lifecycle episodes, separately by observer (AWT/VD/RTP) and input device. Request datasets=["incidents"]. start/end are log coordinates; placed_start/end use the selected placement convention, not sample-accurate truth.',
   'id INTEGER,series_key TEXT,call_id INTEGER,perspective_id INTEGER,import_id INTEGER,kind TEXT,observer TEXT,device TEXT,flow TEXT,start TEXT,end TEXT,last_observed TEXT,detected_at TEXT,duration_ms REAL,wall_span_ms REAL,duration_basis TEXT,start_basis TEXT,status TEXT,placed_start TEXT,placed_end TEXT,placement_basis TEXT,method TEXT'),
 'a_incident_evidence': ('Original events for each episode; incident_id joins a_incidents.id. All references retained independently of period clipping.',
   'incident_id INTEGER,event_id INTEGER,filename TEXT,line_no INTEGER'),
 'a_incident_windows': ('Fixed bins anchored at perspective connection (else first evidence). Union of closed underrun intervals per series, never sum overlapping durations. percent is NULL for unresolved episodes; known_percent is only documented closed occupancy. Zero means no reconstructed closed underrun, not proven healthy audio. Last/clipped bin uses its actual duration.',
   'series_key TEXT,call_id INTEGER,perspective_id INTEGER,observer TEXT,device TEXT,anchor TEXT,window_index INTEGER,start TEXT,end TEXT,window_ms REAL,underrun_ms REAL,known_percent REAL,percent REAL,incomplete INTEGER,episode_count INTEGER,placement_basis TEXT,method TEXT'),
 'a_incident_window_members': ('Evidence bridge: series_key/window_index to incident_id; includes uncertain open episodes touching a bin.',
   'series_key TEXT,window_index INTEGER,incident_id INTEGER'),
 'a_incident_coverage': ('One selected perspective, including those without attributable episodes; absence is not proof of healthy audio.',
   'perspective_id INTEGER,call_id INTEGER,line_id INTEGER,episode_count INTEGER,warning TEXT'),
}


def us(value):
    return round(value*1000000)


def stamp(value):
    if value is None:return None
    return (datetime(1970,1,1)+timedelta(microseconds=value)).isoformat(' ',timespec='microseconds')


def union_length(intervals):
    total=0;right=None
    for a,b in sorted(intervals):
        if b<=a:continue
        total+=b-max(a,right) if right is not None and b>right else b-a if right is None else 0
        right=max(right,b) if right is not None else b
    return total


def placement(e,policy):
    right=e['end']
    if e['status']!='closed':return None,None,'open_excluded'
    if policy=='reported_end':
        if e['duration_basis']!='reported' or e['duration_ms'] is None:return None,None,'no_reported_duration'
        return us(right)-round(e['duration_ms']*1000),us(right),'reported_duration_anchored_at_end'
    if e['start_basis']=='unknown':return None,None,'unknown_start'
    return us(e['start']),us(right),'log_message_span'


def populate(db,config):
    ps=[dict(r) for r in db.execute('SELECT * FROM a_observations')]
    if len(ps)>100:raise ValueError('Episodi: massimo 100 prospettive; selezionare call_ids nello scope')
    width=round(config['incident_window_seconds']*1000000)
    policy=config['incident_time_basis'];groups=defaultdict(list);counter=0
    lower=us(epoch(config['scope']['start'])) if config['scope']['start'] else None
    upper=us(epoch(config['scope']['end'])) if config['scope']['end'] else None
    for p in ps:
        audio=incidents(db,p['id'])
        db.execute('INSERT INTO a_incident_coverage VALUES(?,?,?,?,?)',(p['id'],p['call_id'],p['line_id'],len(audio['episodes']),audio['warning']))
        for e in audio['episodes']:
            counter+=1
            if counter>100000:raise ValueError('Troppi episodi: restringere le chiamate')
            key=hashlib.sha256(str((p['id'],e['stream'])).encode()).hexdigest()[:24]
            a,b,basis=placement(e,policy)
            db.execute('INSERT INTO a_incidents VALUES('+','.join('?' for _ in range(22))+')',
                (counter,key,p['call_id'],p['id'],p['import_id'],e['kind'],e['observer'],e['device'],e['flow'],
                 stamp(us(e['start'])),stamp(us(e['end'])) if e['end'] is not None else None,
                 stamp(us(e['last_observed'])),stamp(us(e['detected_at'])),e['duration_ms'],e.get('wall_span_ms'),
                 e['duration_basis'],e['start_basis'],e['status'],stamp(a),stamp(b),basis,METHOD))
            db.executemany('INSERT INTO a_incident_evidence VALUES(?,?,?,?)',
                ((counter,r['event_id'],r['filename'],r['line']) for r in e['evidence']))
            if e['kind']=='buffer_underrun':groups[(p['id'],key)].append((counter,e,a,b))
    by_id={p['id']:p for p in ps};n=0;members=0
    for (pid,key),items in groups.items():
        p=by_id[pid];anchor=us(epoch(p['connected'] or p['start']))
        # No invented call end. An unfinished perspective stops at last evidence.
        stop=us(epoch(p['end'])) if p['end'] else max(us(e['last_observed']) for _,e,_,_ in items)
        begin=max(anchor,lower) if lower is not None else anchor
        end=min(stop,upper) if upper is not None else stop
        if end<=begin:continue
        first=(begin-anchor)//width;last=(end-anchor+width-1)//width
        if n+last-first>100000:raise ValueError('Oltre 100.000 finestre; restringere periodo o aumentare incident_window_seconds')
        bins={i:dict(intervals=[],members=set(),uncertain=False) for i in range(first,last)}
        for eid,e,a,b in items:
            uncertain=a is None or b is None
            if uncertain:
                a=us(e['start']);b=us(e['end']) if e['end'] is not None else stop
                if e['start_basis']=='unknown':a=anchor
            a=max(a,begin);b=min(b,end)
            if b<=a:continue
            for i in range(max(first,(a-anchor)//width),min(last,(b-anchor+width-1)//width)):
                members+=1
                if members>200000:raise ValueError('Oltre 200.000 associazioni episodio/finestra; restringere periodo o chiamate')
                slot=bins[i];slot['members'].add(eid)
                if uncertain:slot['uncertain']=True
                else:slot['intervals'].append((max(a,anchor+i*width),min(b,anchor+(i+1)*width)))
        example=items[0][1]
        for i,slot in bins.items():
            a=max(begin,anchor+i*width);b=min(end,anchor+(i+1)*width)
            duration=b-a;occupied=union_length(slot['intervals']);percent=100*occupied/duration
            db.execute('INSERT INTO a_incident_windows VALUES('+','.join('?' for _ in range(17))+')',
                (key,p['call_id'],pid,example['observer'],example['device'],stamp(anchor),i,stamp(a),stamp(b),duration/1000,
                 occupied/1000,percent,None if slot['uncertain'] else percent,int(slot['uncertain']),len(slot['members']),policy,METHOD))
            db.executemany('INSERT INTO a_incident_window_members VALUES(?,?,?)',((key,i,eid) for eid in sorted(slot['members'])))
            n+=1
