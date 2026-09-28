"""Request-local analytical intervals, episode membership and observer context."""
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime

from .analytics import MAX_INTERVALS
from .metric_context import context
from .mobility import Context
from .mos import calculate


def seconds(start,end):
    return (datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()


def populate(db,ids,config):
    deadline=time.monotonic()+30
    observations={r['id']:dict(r) for r in db.execute('SELECT * FROM a_observations')}
    count=db.execute('SELECT COUNT(*) FROM network_observations WHERE import_id IN (SELECT id FROM a_sources)').fetchone()[0]
    if len(observations)>10000 or count>100000:raise ValueError('Contesto MOS troppo ampio: selezionare meno chiamate o sorgenti')
    network=Context(db,{p['import_id'] for p in observations.values()})
    network_rows={r['id']:dict(r) for r in db.execute('SELECT * FROM network_observations WHERE import_id IN (SELECT id FROM a_sources)')}
    groups=defaultdict(list)
    counter=0
    for offset in range(0,len(ids),20):
        if time.monotonic()>deadline: raise ValueError('Preparazione MOS troppo lunga: restringere il periodo')
        for m in calculate(db,ids[offset:offset+20]):
            p=observations.get(m['perspective_id'])
            if not p: continue
            start=m.get('window_start',m['ts']);end=m['valid_until']
            if config['scope']['start']:start=max(start,config['scope']['start'])
            if config['scope']['end']:end=min(end,config['scope']['end'])
            if start>=end:continue
            counter+=1
            if counter>MAX_INTERVALS or time.monotonic()>deadline: raise ValueError('MOS: limite di intervalli/tempo, restringere il periodo')
            role=p['declared_role'] or m.get('role') or 'app'
            role_basis='confirmed' if p['declared_role'] else 'telemetry' if m.get('role') else 'app_assumed'
            app_direction=context(m['name'],m['direction'],role)['category']
            local=m['direction']=='incoming'
            # Local signaling identity is not automatically the reported remote listener.
            receiver=p['local_receiver'] if local else 'peer-of:'+p['local_receiver']
            receiver_basis=p['receiver_basis'] if local else 'remote_unidentified'
            basis=m.get('clock_domain','log_unspecified')
            key=hashlib.sha256(json.dumps([p['id'],m['direction'],m['flow'],m['ssrc'],basis,m['sample_kind'],m['model']['version']]).encode()).hexdigest()[:24]
            duration=seconds(start,end)
            item=dict(id=counter,key=key,call_id=m['call_id'],pid=p['id'],direction=m['direction'],app_direction=app_direction,
                      receiver=receiver,receiver_basis=receiver_basis,time_basis=basis,flow=m['flow'],ssrc=m['ssrc'],start=start,end=end,seconds=duration,value=m['value'])
            db.execute('INSERT INTO a_mos VALUES('+','.join('?' for _ in range(21))+')',
                       (counter,key,m['call_id'],p['id'],p['import_id'],m['direction'],app_direction,role_basis,receiver,receiver_basis,
                        m['flow'],m['ssrc'],start,end,duration,m['value'],m['loss_percent'],basis,m['model']['version'],m['event_id'],m['id']))
            db.executemany('INSERT INTO a_mos_evidence VALUES(?,?,?,?,?)',
                           ((counter,e['event_id'],e.get('metric_id'),e['filename'],e['line']) for e in m['evidence']))
            groups[key].append(item)
            if basis=='UTC':
                # Structured context is already validated in monotonic source/session/boot domains.
                t=db.execute('SELECT context FROM telemetry_intervals WHERE metric_id=?',(m['id'],)).fetchone()
                ctx=json.loads(t[0]) if t else {}
                db.execute('INSERT INTO a_mos_network VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                           (counter,start,end,duration,ctx.get('access','unknown'),ctx.get('upstream','unknown'),
                            ctx.get('operator','unknown'),None,None,None,'validated_telemetry_context; Wi-Fi identity not projected'))
            else:
                boundaries=network.boundaries(p['import_id'],start,end)
                for a,b in zip(boundaries,boundaries[1:]):
                    ctx=network.at(p['import_id'],a);n=network_rows.get(ctx['network_id'],{})
                    db.execute('INSERT INTO a_mos_network VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                               (counter,a,b,seconds(a,b),ctx['access'],ctx['upstream'],ctx['operator'],n.get('wifi_identity'),
                                ctx['network_id'],n.get('event_id'),n.get('basis','unknown_or_expired')))
    episode_id=0
    for key,items in groups.items():
        items.sort(key=lambda x:(x['start'],x['end'],x['id']))
        # A series with overlapping intervals has no defensible elapsed-time denominator.
        if any(a['end']>b['start'] for a,b in zip(items,items[1:])):
            raise ValueError('Intervalli MOS sovrapposti nella stessa serie: analizzare le evidenze separatamente')
        first=items[0];p=observations[first['pid']]
        episodes=[];active=[]
        for item in items:
            bad=item['value']<config['threshold']
            if active and (not bad or active[-1]['end']!=item['start']):
                episodes.append(active);active=[]
            if bad:active.append(item)
        if active:episodes.append(active)
        episode_count=0
        for episode in episodes:
            duration=sum(x['seconds'] for x in episode)
            if duration<config['min_episode_seconds']:continue
            episode_id+=1;episode_count+=1
            db.execute('INSERT INTO a_mos_episodes VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (episode_id,key,first['call_id'],first['pid'],first['direction'],episode[0]['start'],episode[-1]['end'],duration,
                        min(x['value'] for x in episode),sum(x['value']*x['seconds'] for x in episode)/duration,len(episode)))
            db.executemany('INSERT INTO a_episode_intervals VALUES(?,?)',((episode_id,x['id']) for x in episode))
        covered=sum(x['seconds'] for x in items)
        bad_seconds=sum(x['seconds'] for x in items if x['value']<config['threshold'])
        begin=p['connected'] or p['start'];end=p['end']
        if begin and config['scope']['start']:begin=max(begin,config['scope']['start'])
        if end and config['scope']['end']:end=min(end,config['scope']['end'])
        window=max(0,seconds(begin,end)) if begin and end else None
        db.execute('INSERT INTO a_mos_summary VALUES('+','.join('?' for _ in range(20))+')',
                   (key,first['call_id'],first['pid'],first['direction'],first['app_direction'],first['receiver'],first['receiver_basis'],
                    covered,window,100*covered/window if window else None,bad_seconds,100*bad_seconds/covered,episode_count,
                    min(x['value'] for x in items),sum(x['seconds']*x['value'] for x in items)/covered,max(x['value'] for x in items),len(items),first['time_basis'],first['flow'],first['ssrc']))
