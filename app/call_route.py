"""Source-local call routes, with evidence and point-sampled AWT quality."""
from collections import defaultdict
from .geography import grid
from .perceptual import bounded_perspective, perspective, tick, stamp, SECOND, METHOD


def interpolated_samples(db, selected, positions):
    """One midpoint per complete clock second bracketed by unambiguous positions.

    Geometry is estimated at constant speed; quality is calculated from AWT,
    never interpolated from the values at the two position messages.
    """
    groups=defaultdict(list)
    for g in positions:
        if g['kind']!='cached': groups[tick(g['ts'])].append(g)
    anchors=[]
    for t,group in sorted(groups.items()):
        anchors.append((t,group[0] if len({(g['latitude'],g['longitude']) for g in group})==1 else None))
    pending=[];links=[];seconds=set()
    for (a,left),(b,right) in zip(anchors,anchors[1:]):
        if left is None or right is None or not 0<b-a<=120*SECOND: continue
        links.append(dict(start_id=left['id'],end_id=right['id']))
        for bucket in range(((a+SECOND-1)//SECOND)*SECOND,b-SECOND+1,SECOND):
            pending.append((bucket,left,right,a,b));seconds.add(bucket)
            if len(pending)>100000: raise ValueError('Oltre 100.000 punti interpolati: restringere la chiamata')
    values=defaultdict(list)
    if seconds:
        for m in perspective(db,selected,seconds): values[m['window_ts']].append(m)
    samples=[]
    for bucket,left,right,a,b in pending:
        t=bucket+SECOND//2;fraction=(t-a)/(b-a)
        mm=values[stamp(bucket)];m=mm[0] if len(mm)==1 else None
        # Shortest longitude arc also handles a crossing of the antimeridian.
        delta=(right['longitude']-left['longitude']+180)%360-180
        samples.append(dict(id=f'interpolated-{bucket}',ts=stamp(t),window_ts=stamp(bucket),
            latitude=left['latitude']+fraction*(right['latitude']-left['latitude']),
            longitude=(left['longitude']+fraction*delta+180)%360-180,
            kind='interpolated',value=m['value'] if m else None,
            reason=None if m else 'Secondo AWT non valutabile o ambiguo',
            underrun_ms=m['underrun_ms'] if m else None,observed_ms=m['observed_ms'] if m else None,
            position_evidence=[dict(position_id=g['id'],ts=g['ts'],kind=g['kind'],event_id=g['event_id'],
                filename=g['filename'],line=g['source_line']) for g in (left,right)],
            audio_evidence=m['evidence'] if m else []))
    valid=[s for s in samples if s['value'] is not None]
    duration=sum(s['observed_ms'] for s in valid)
    return dict(points=samples,links=links,max_gap_seconds=120,method='linear-time-1',
        mean=sum(s['value']*s['observed_ms'] for s in valid)/duration if duration else None,
        minimum=min((s['value'] for s in valid),default=None),evaluated_seconds=duration/1000)


def route(db, call_id, perspective_id=None, cell=50):
    if cell not in (50,100,250,500,1000,5000,10000):
        raise ValueError('Dimensione cella non valida')
    sources=[dict(r) for r in db.execute('''SELECT p.*,i.label,i.clock_offset
        FROM perspectives p JOIN imports i ON i.id=p.import_id
        LEFT JOIN observation_roles r ON r.perspective_id=p.id
        WHERE p.call_id=? AND (r.role IS NULL OR r.role='app')
        AND p.id NOT IN (SELECT perspective_id FROM effective_duplicates) ORDER BY p.id''',(call_id,))]
    if perspective_id is not None and not any(p['id']==perspective_id for p in sources):
        raise ValueError('Prospettiva non appartenente alla chiamata o non locale app')
    selected=next((p for p in sources if p['id']==perspective_id),sources[0] if sources else None)
    data=dict(metric='perceptual',metric_label='Perceptual Quality',unit='PQ',cell=cell,
        direction='downstream',quality='declared',method=METHOD,call_id=call_id,
        sources=[dict(id=p['id'],label=p['label'],import_id=p['import_id']) for p in sources],
        perspective_id=selected['id'] if selected else None,points=[],cells=[],locations=[],
        extent=[None,None,0],mean=None,seconds=0,samples=0,conflicting_intervals=0,
        locations_truncated=False,mobility=dict(operators=[]),network_known_percent=None,
        gap_seconds=30,interpolation=dict(points=[],links=[],max_gap_seconds=120,mean=None,minimum=None,evaluated_seconds=0))
    if not selected: return data
    p=bounded_perspective(db,selected)
    if not p: return data
    data['end_basis']=p['end_basis']
    # Explicit call identity wins; unassigned location fixes require one source-local window.
    positions=[dict(r) for r in db.execute('''SELECT g.*,f.name filename FROM geo_positions g
        JOIN events e ON e.id=g.event_id JOIN files f ON f.id=e.file_id
        WHERE g.import_id=? AND g.valid=1 AND g.method='geo-mos-1' AND g.kind!='sip_remote'
        AND g.ts>=? AND g.ts<=? AND (g.call_id=? OR g.call_id IS NULL)
        ORDER BY g.ts,g.id LIMIT 10001''',(p['import_id'],p['start'],p['end'],call_id))]
    if len(positions)>10000: raise ValueError('Oltre 10.000 posizioni nella chiamata')
    peers=[bounded_perspective(db,r) for r in db.execute('''SELECT * FROM perspectives
        WHERE import_id=? AND id NOT IN (SELECT perspective_id FROM effective_duplicates)
        AND start<=? AND (end>=? OR end IS NULL)''',(p['import_id'],p['end'],p['start']))]
    positions=[g for g in positions if g['call_id']==call_id or
        [q['id'] for q in peers if q and q['start']<=g['ts']<q['end']]==[p['id']]]
    data['interpolation']=interpolated_samples(db,selected,[g for g in positions
        if (p['connected'] or p['start'])<=g['ts']<=p['end']])
    seconds={tick(g['ts'])//SECOND*SECOND for g in positions if g['kind']!='cached'}
    values=defaultdict(list)
    for m in perspective(db,selected,seconds): values[m['window_ts']].append(m)
    cell_bins=defaultdict(set)
    for g in positions:
        if g['kind']!='cached': cell_bins[stamp(tick(g['ts'])//SECOND*SECOND)].add(grid(g['latitude'],g['longitude'],cell)[0])
    cells={};locations={};seen=set();sample_values=[];previous=None;segment=0
    for g in positions:
        key,bounds=grid(g['latitude'],g['longitude'],cell)
        locations[key]=dict(id=key,bounds=bounds)
        bucket=stamp(tick(g['ts'])//SECOND*SECOND);mm=values[bucket]
        reason=None
        if g['kind']=='cached': reason='Posizione recuperata dalla cache: non è un nuovo fix'
        elif g['ts']<(p['connected'] or p['start']): reason='Prima della connessione'
        elif g['ts']>=p['end']: reason='Alla fine o dopo la chiamata'
        elif len(cell_bins[bucket])>1: reason='Più celle nello stesso secondo: posizione del campione ambigua'
        elif len(mm)!=1: reason='Underrun non attribuibile o più lettori AWT: campione ambiguo'
        m=mm[0] if reason is None else None
        if g['kind']!='cached':
            if previous is None or tick(g['ts'])-previous>30*SECOND: segment+=1
            previous=tick(g['ts'])
        point=dict(id=g['id'],ts=g['ts'],latitude=g['latitude'],longitude=g['longitude'],
            kind=g['kind'],cell_id=key,segment=segment if g['kind']!='cached' else None,
            value=m['value'] if m else None,reason=reason,
            underrun_ms=m['underrun_ms'] if m else None,observed_ms=m['observed_ms'] if m else None,
            evidence=dict(event_id=g['event_id'],filename=g['filename'],line=g['source_line']),
            audio_evidence=m['evidence'] if m else [])
        data['points'].append(point)
        if m and (key,bucket) not in seen:
            seen.add((key,bucket));sample_values.append(m['value'])
            c=cells.setdefault(key,dict(id=key,bounds=bounds,values=[],seconds=0,minimum=100,maximum=0,
                observations=0,days=1,first=m['ts'],last=m['valid_until'],accuracy_max=None,
                speed_max_mps=None,movement_exceeds_cell=False,limited=False))
            c['values'].append(m['value']);c['seconds']+=m['observed_ms']/1000;c['observations']+=1
            c['minimum']=min(c['minimum'],m['value']);c['maximum']=max(c['maximum'],m['value']);c['last']=m['valid_until']
            if g['accuracy'] is not None:c['accuracy_max']=max(c['accuracy_max'] or 0,g['accuracy'])
    for c in cells.values(): c['mean']=sum(c.pop('values'))/c['observations']
    data.update(cells=list(cells.values()),locations=list(locations.values()),
        mean=sum(sample_values)/len(sample_values) if sample_values else None,
        seconds=sum(c['seconds'] for c in cells.values()),samples=len(sample_values),
        extent=[positions[0]['ts'],positions[-1]['ts'],len(positions)] if positions else [None,None,0])
    return data
