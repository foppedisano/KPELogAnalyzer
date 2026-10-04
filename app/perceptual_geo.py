"""Point-position sampling of one-second AWT quality; no held coordinates."""
from collections import defaultdict, Counter
from datetime import datetime
from .perceptual import perspective, bounded_perspective, tick, stamp, SECOND, METHOD
from .geography import grid, iso
from .mobility import Context, filters, matches, summary
from .call_route import interpolated_samples


def aggregate(db, params):
    size=int(params.get('cell','250'));quality=params.get('quality','fresh')
    if size not in (50,100,250,500,1000,5000,10000) or quality not in ('fresh','declared'):
        raise ValueError('Filtri geografici non validi')
    if params.get('direction','downstream')!='downstream':
        raise ValueError('Perceptual Quality usa il solo AWT locale: selezionare downstream')
    start=params.get('start') or '0001-01-01 00:00:00';end=params.get('end') or '9999-12-31 23:59:59'
    for t in (start,end):
        if datetime.fromisoformat(t).tzinfo: raise ValueError('Usare gli orari originali senza fuso')
    start,end=iso(datetime.fromisoformat(start)),iso(datetime.fromisoformat(end))
    if end<=start: raise ValueError('La fine deve seguire l’inizio')
    selected=filters(params)
    positions=[dict(r) for r in db.execute("""SELECT p.*,s.speed_mps,f.name filename FROM geo_positions p
        JOIN events e ON e.id=p.event_id JOIN files f ON f.id=e.file_id
        LEFT JOIN movement_samples s ON s.position_id=p.id WHERE p.valid=1 AND p.kind!='sip_remote'
        AND p.method='geo-mos-1' AND p.ts>=? AND p.ts<? ORDER BY p.ts,p.id LIMIT 100001""",(start,end))]
    if len(positions)>100000: raise ValueError('Oltre 100.000 posizioni: restringere il periodo')
    context=Context(db,{p['import_id'] for p in positions})
    all_positions=positions
    positions_by_import=defaultdict(list)
    for pos in all_positions: positions_by_import[pos['import_id']].append(pos)
    positions=[p for p in positions if matches(context.at(p['import_id'],p['ts']),selected)]
    ps=[dict(r) for r in db.execute("""SELECT p.*,i.label,i.clock_offset FROM perspectives p JOIN imports i ON i.id=p.import_id
        LEFT JOIN observation_roles r ON r.perspective_id=p.id WHERE (r.role IS NULL OR r.role='app')
        AND p.id NOT IN (SELECT perspective_id FROM effective_duplicates) AND (p.end>? OR p.end IS NULL) AND p.start<?""",(start,end))]
    ps=[bounded_perspective(db,p) for p in ps]
    ps=[p for p in ps if p and p['end']>start]
    by_import=defaultdict(list)
    for p in ps: by_import[p['import_id']].append(p)
    locations={};candidates=defaultdict(list);reasons=Counter()
    for pos in positions:
        key,bounds=grid(pos['latitude'],pos['longitude'],size)
        locations[key]=dict(id=key,bounds=bounds)
        if pos['kind']=='cached': reasons['cached_position']+=1;continue
        if pos['kind'] in ('sip_local','sip_config') and quality!='declared': reasons['sip_excluded_by_filter']+=1;continue
        choices=[p for p in by_import[pos['import_id']] if (p['connected'] or p['start'])<=pos['ts']<p['end']
                 and (pos['call_id'] is None or p['call_id']==pos['call_id'])]
        if len(choices)!=1: reasons['no_unique_active_app_call']+=1;continue
        candidates[choices[0]['id']].append(pos)
    by_pid={p['id']:p for p in ps};cells={};total=0;weighted=0;known=0;conflicts=0;breakdown=Counter()
    calculated=0;route_count=0;estimated={}
    for pid,pp in candidates.items():
        # Split at excluded fixes rather than bridging a different call or filter.
        accepted={g['id'] for g in pp};runs=[];run=[]
        for g in positions_by_import[by_pid[pid]['import_id']]:
            if g['kind']=='cached': continue
            if g['id'] in accepted: run.append(g)
            else:
                if len(run)>1: runs.append(run)
                run=[]
        if len(run)>1: runs.append(run)
        previous_estimate=None
        for run in runs:
            result=interpolated_samples(db,by_pid[pid],run)
            by_id={g['id']:g for g in run}
            allowed=set()
            for link in result['links']:
                a,b=(by_id[link[k]] for k in ('start_id','end_id'))
                # Network state can change between fixes, too. Exclude the whole
                # link if any second does not satisfy the current filter.
                if all(matches(context.at(a['import_id'],ts),selected)
                       for ts in context.boundaries(a['import_id'],a['ts'],b['ts'])):
                    allowed.add((a['id'],b['id']))
            samples=[s for s in result['points'] if tuple(e['position_id'] for e in s['position_evidence']) in allowed]
            route_count+=len(samples)
            if route_count>100000: raise ValueError('Oltre 100.000 punti di percorso: restringere il periodo')
            for s in samples:
                key,bounds=grid(s['latitude'],s['longitude'],size)
                if s['value'] is None:
                    previous_estimate=None
                    continue
                ts=s['window_ts'];duration=s['observed_ms']/1000
                c=estimated.setdefault(key,dict(id=key,bounds=bounds,origin='estimated',seconds=0,weighted=0,
                    observations=0,minimum=100,maximum=0,days=set(),passes=0,first=ts,last=ts,
                    affected_seconds=0,underrun_ms=0,gap_min_seconds=120,gap_max_seconds=0,
                    accuracy_max=None,speed_max_mps=None,movement_exceeds_cell=False,evidence=[]))
                if previous_estimate!=(key,tick(ts)-SECOND): c['passes']+=1
                previous_estimate=(key,tick(ts))
                c['seconds']+=duration;c['weighted']+=s['value']*duration;c['observations']+=1
                c['minimum']=min(c['minimum'],s['value']);c['maximum']=max(c['maximum'],s['value'])
                c['days'].add(ts[:10]);c['first']=min(c['first'],ts);c['last']=max(c['last'],stamp(tick(ts)+SECOND))
                c['affected_seconds']+=duration if s['underrun_ms']>0 else 0;c['underrun_ms']+=s['underrun_ms']
                a,b=s['position_evidence'];gap=(tick(b['ts'])-tick(a['ts']))/SECOND
                c['gap_min_seconds']=min(c['gap_min_seconds'],gap);c['gap_max_seconds']=max(c['gap_max_seconds'],gap)
                if len(c['evidence'])<20:
                    c['evidence'].append(dict(ts=ts,value=s['value'],position=s['position_evidence'],audio=s['audio_evidence']))
        points=defaultdict(list)
        for m in perspective(db,by_pid[pid],{tick(p['ts'])//SECOND*SECOND for p in pp}):
            points[m['window_ts']].append(m);calculated+=1
            if calculated>200000: raise ValueError('Oltre 200.000 campioni AWT: restringere il periodo')
        groups=defaultdict(list)
        for pos in pp: groups[stamp((tick(pos['ts'])//SECOND)*SECOND)].append(pos)
        previous_direct=None
        for ts,group in groups.items():
            mm=points.get(ts,[])
            if len(mm)!=1:
                previous_direct=None;reasons['no_unique_evaluable_awt_second']+=len(group);continue
            # A full-second value cannot be apportioned across different cells without a path.
            keys={grid(p['latitude'],p['longitude'],size)[0] for p in group}
            if len(keys)!=1:
                previous_direct=None;conflicts+=1;reasons['multiple_cells_in_one_second']+=len(group);continue
            m=mm[0]
            if m['ts']<start or m['valid_until']>end: reasons['partial_second_outside_period']+=len(group);continue
            pos=group[0];key,bounds=grid(pos['latitude'],pos['longitude'],size)
            cell=cells.setdefault(key,dict(id=key,bounds=bounds,seconds=0,weighted=0,minimum=100,maximum=0,observations=0,
                days=set(),first=m['ts'],last=m['valid_until'],accuracy_max=None,speed_max_mps=None,evidence=[],
                origin='direct',passes=0,affected_seconds=0,underrun_ms=0))
            if previous_direct is None or previous_direct[0]!=key or tick(ts)-previous_direct[1]>120*SECOND:
                cell['passes']+=1
            previous_direct=(key,tick(ts))
            cell['affected_seconds']+=m['observed_ms']/1000 if m['underrun_ms']>0 else 0
            cell['underrun_ms']+=m['underrun_ms']
            cell['seconds']+=1;cell['weighted']+=m['value'];cell['minimum']=min(cell['minimum'],m['value']);cell['maximum']=max(cell['maximum'],m['value'])
            cell['observations']+=1;cell['days'].add(ts[:10]);cell['first']=min(cell['first'],m['ts']);cell['last']=max(cell['last'],m['valid_until'])
            for p in group:
                if p['accuracy'] is not None: cell['accuracy_max']=max(cell['accuracy_max'] or 0,p['accuracy'])
                if p['speed_mps'] is not None: cell['speed_max_mps']=max(cell['speed_max_mps'] or 0,p['speed_mps'])
            if len(cell['evidence'])<20:
                cell['evidence'].append(dict(perspective_id=pid,ts=ts,value=m['value'],position_event_ids=[p['event_id'] for p in group],
                    position=[dict(event_id=p['event_id'],filename=p['filename'],line=p['source_line'],kind=p['kind'],ts=p['ts']) for p in group[:20]],
                    position_truncated=len(group)>20,audio=m['evidence']))
            total+=1;weighted+=m['value'];cx=context.at(pos['import_id'],pos['ts'])
            known+=cx['access']!='unknown';breakdown[(cx['access'],cx['upstream'],cx['operator'])]+=1
    for cell in cells.values():
        cell['mean']=cell.pop('weighted')/cell['observations'];cell['days']=len(cell['days'])
        cell['limited']=cell['observations']<60 or cell['days']<2
        cell['movement_exceeds_cell']=cell['speed_max_mps'] is not None and cell['speed_max_mps']>size
        cell['evidence_truncated']=cell['observations']>len(cell['evidence'])
    direct_count=len(cells)
    for key,c in estimated.items():
        c['mean']=c.pop('weighted')/c['seconds'];c['days']=len(c['days'])
        c['limited']=c['seconds']<60 or c['days']<2;c['evidence_truncated']=c['observations']>len(c['evidence'])
        if key in cells: cells[key]['estimate']=c
        else: cells[key]=c
    if len(locations)>10000 or len(cells)>10000: raise ValueError('Oltre 10.000 celle: aumentare dimensione o restringere periodo')
    extent=list(db.execute("SELECT min(ts),max(ts),count(*) FROM geo_positions WHERE valid=1 AND kind!='sip_remote'").fetchone())
    return dict(metric='perceptual',metric_label='Perceptual Quality',unit='PQ',cells=list(cells.values()),locations=list(locations.values()),
        direct_cells=direct_count,estimated_cells=len(cells)-direct_count,route_samples=route_count,
        estimation_method='linear-time-cells-1',
        locations_truncated=False,conflicting_intervals=conflicts,seconds=total,samples=total,mean=weighted/total if total else None,
        extent=extent,position_counts=dict(db.execute('SELECT kind,count(*) FROM geo_positions GROUP BY kind')),cell=size,direction='downstream',quality=quality,
        model=METHOD,method=METHOD,max_age_seconds=0,filters=selected,mobility=summary(db),network_known_seconds=known,
        network_known_percent=100*known/total if total else None,exclusions=dict(reasons),
        network_breakdown=[dict(access=k[0],upstream=k[1],operator=k[2],seconds=v) for k,v in breakdown.items()])
