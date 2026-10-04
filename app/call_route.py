"""Source-local call routes, with evidence and point-sampled AWT quality."""
from collections import defaultdict
from .geography import grid
from .perceptual import bounded_perspective, perspective, tick, stamp, SECOND, METHOD


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
        gap_seconds=30)
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
