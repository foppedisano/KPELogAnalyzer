"""Read-only, bounded temporal profiles of an exact geographic grid cell."""
import hashlib
import json
import math
import time
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import groupby

from .db import rows
from .geography import grid, iso, VERSION as GEO_VERSION
from .mobility import Context, filters, matches, FIELDS
from .catalog import CATALOG

VERSION = 'geo-temporal-1'
MAX_ROWS = 100000
SIZES = (50,100,250,500,1000,5000,10000)
POINT_NAMES = ('rtcp.jitter','rtcp.rtt','vd.buffer','vd.dejitter_target',
               'vd.scheduling_delay','vd.scheduling_resets','vd.underruns',
               'vd.silence_played','vd.silence_skipped','vd.samples_skipped',
               'vd.underrun_duration')
METRICS = [dict(name='mos',title='MOS a profilo fisso',unit='MOS',aggregation='duration_mean'),
           dict(name='loss',title='Perdita riportata',unit='%',aggregation='duration_mean')]
for name in POINT_NAMES:
    entry=next(x for x in CATALOG if x['name']==name)
    METRICS.append(dict(name=name,title=entry['title'],unit=entry['unit'].split(' ')[0],
                        aggregation='counter_delta' if entry['kind']=='counter' else 'sample_mean'))
RULES = [
    'Profilo descrittivo, non previsione né diagnosi causale. Nessuna azione automatica sull’app.',
    'Cella esatta della griglia selezionata: nessun ampliamento automatico. Le dimensioni sono approssimate in metri; l’accuratezza del fix può essere peggiore.',
    'legacy_observed e utc sono selezioni separate. Nessun fuso, ora legale o correzione clock viene dedotto. Ore legacy = orari scritti, ore UTC = UTC, non ora locale della zona.',
    'MOS e perdita: media pesata per secondi-osservazione, non tempo civile né perdita ponderata per pacchetti. Più chiamate simultanee contribuiscono tempo distinto.',
    'I confronti di popolazione per campioni puntuali sono opt-in e richiedono uguali osservatore, device, input/output, flow, direzione, statistica e unità. Prospettive, cicli e SSRC restano in serie distinte e nel riepilogo per serie; non si fondono le identità o i contatori.',
    'Le metriche puntuali hanno media per campioni, senza durata inventata. Contatori: delta solo fra campioni validi dello stesso contesto entro 30 s; niente somma dei cumulativi.',
    'I delta non vengono distribuiti dentro l’intervallo. Se attraversano un’ora, un cambio di posizione o di contesto rete sono esclusi dal profilo temporale.',
    'day_balanced_mean pesa ugualmente ciascun giorno osservato nel gruppo; non dimostra indipendenza statistica. Giorni e sorgenti pochi producono copertura limitata, non una probabilità di affidabilità.',
    'upstream indica report del peer associati alla posizione locale dell’app, non la posizione o la causa del problema remoto. Le metriche locali VD restano indipendenti dalla direzione RTP.',
    'Sorgenti riconosciute tramite identità produttore; altrimenti conteggio per import, non persone o dispositivi verificati. Nessuna deduplicazione generale fra formati legacy e telemetria.',
    'Dati assenti restano null. Copertura = osservazioni disponibili, non percentuale di disponibilità della rete. Per previsioni servono validazione su periodi successivi e verifica dei cambiamenti di popolazione.',
]
SCHEMA = dict(type='object',properties={
    'cell':dict(type='integer',enum=list(SIZES)),
    'cell_id':dict(type='string',description='Exact id band:column returned by the geography map, together with cell size.'),
    'metric':dict(type='string',enum=[m['name'] for m in METRICS]),
    'time_basis':dict(type='string',enum=['legacy_observed','utc']),
    'grain':dict(type='string',enum=['day','week','month','year']),
    'direction':dict(type='string',enum=['downstream','upstream']),
    'quality':dict(type='string',enum=['fresh','declared']),
    'start':dict(type='string'),'end':dict(type='string'),
    'platform':dict(type='string',enum=['all','android','ios','desktop','unknown']),
    'access':dict(type='string',enum=['all','cellular','wifi','ethernet','other','unknown']),
    'upstream':dict(type='string',enum=['all','mobile_direct','tethering','onboard_wifi','fixed','unknown']),
    'operator':dict(type='string'),
    'series_id':dict(type='string',description='Select one exact metric context from the returned series list.'),
    'evidence_offset':dict(type='integer',minimum=0,maximum=MAX_ROWS),
    'evidence_limit':dict(type='integer',minimum=1,maximum=200),
},required=['cell','cell_id'],additionalProperties=False)


CELL_SCHEMA=dict(type='object',properties={k:SCHEMA['properties'][k] for k in
    ('cell','direction','quality','start','end','platform','access','upstream','operator')},required=[],additionalProperties=False)
CELL_SCHEMA['properties']['metric']=dict(type='string',enum=['mos','perceptual'],default='mos',
    description='PQ returns direct-priority cells and separate estimates; temporal MOS profiles do not describe PQ.')


def cells(db,raw):
    from .geography import aggregate
    if not isinstance(raw,dict) or set(raw)-set(CELL_SCHEMA['properties']):raise ValueError('Filtri celle non validi')
    for k,v in raw.items():
        if (k=='cell' and (type(v) is not int or v not in SIZES)) or (k!='cell' and not isinstance(v,str)):
            raise ValueError('Filtro celle non valido')
    return aggregate(db,raw)


def contract():
    return dict(version=VERSION,metrics=METRICS,request_schema=SCHEMA,cell_discovery_schema=CELL_SCHEMA,rules=RULES,
                limits=dict(input_rows=MAX_ROWS,series=100,history_bins=5000,evidence_page=200,seconds=20),
                endpoint='/api/analytics/geo-temporal',tool='analytics_geo_temporal')


def validate(raw):
    if not isinstance(raw,dict) or set(raw)-set(SCHEMA['properties']):raise ValueError('Parametri temporali non validi')
    if type(raw.get('cell')) is not int or raw['cell'] not in SIZES:raise ValueError('Dimensione cella non valida')
    cell_id=raw.get('cell_id')
    if not isinstance(cell_id,str) or len(cell_id)>40:raise ValueError('Identificativo cella mancante')
    try:
        band,col=map(int,cell_id.split(':'))
        step=raw['cell']/111195.08
        south=band*step-90;north=min(90,south+step)
        width=min(360,step/max(.00001,math.cos(math.radians((south+north)/2))))
        west=col*width-180;east=min(180,west+width)
        if band<0 or col<0 or not -90<=south<90 or not -180<=west<180 or cell_id!=f'{band}:{col}':raise ValueError()
    except (ValueError,OverflowError):raise ValueError('Identificativo cella non valido') from None
    out=dict(cell=raw['cell'],cell_id=cell_id,metric='mos',time_basis='legacy_observed',grain='day',
             direction='downstream',quality='fresh',start='',end='',series_id='',evidence_offset=0,evidence_limit=50)
    out.update(raw)
    for key in ('metric','time_basis','grain','direction','quality'):
        if out[key] not in SCHEMA['properties'][key]['enum']:raise ValueError('Filtro '+key+' non valido')
    for key in ('start','end','series_id'):
        if not isinstance(out[key],str) or len(out[key])>100:raise ValueError('Filtro '+key+' non valido')
    for key in ('start','end'):
        if out[key]:
            dt=datetime.fromisoformat(out[key])
            if dt.tzinfo:raise ValueError('Usare coordinate temporali senza suffisso di fuso e selezionare time_basis')
            out[key]=iso(dt)
    if out['start'] and out['end'] and out['end']<=out['start']:raise ValueError('Fine precedente all’inizio')
    for key,maximum in [('evidence_offset',MAX_ROWS),('evidence_limit',200)]:
        if type(out[key]) is not int or not (0 if key.endswith('offset') else 1)<=out[key]<=maximum:raise ValueError('Paginazione non valida')
    for key in ('platform','access','upstream','operator'):
        if key in raw and not isinstance(raw[key],str):raise ValueError('Filtro rete non valido')
    out.update(filters(out))
    return out,[west,south,east,north]


def source_key(row):
    return row['producer_key'] or 'import:'+str(row['import_id'])


def bounded(data):
    if len(data)>MAX_ROWS:raise ValueError('Oltre 100.000 osservazioni: restringere il periodo')
    return data


def mos_observations(db,c,guard,excluded):
    lo=c['start'] or '0001';hi=c['end'] or '9999'
    data=bounded(rows(db,'''SELECT g.*,t.context FROM geo_mos g
        LEFT JOIN telemetry_geo_context t ON t.observation_id=g.id
        WHERE g.direction=? AND g.quality=? AND g.end>? AND g.start<?
        AND ((?='legacy_observed' AND g.method=?) OR (?='utc' AND t.observation_id IS NOT NULL))
        ORDER BY g.signature,g.start LIMIT 100001''',(c['direction'],c['quality'],lo,hi,c['time_basis'],GEO_VERSION,c['time_basis'])))
    evidence=defaultdict(list)
    for i in range(0,len(data),400):
        guard();ids=[r['id'] for r in data[i:i+400]]
        for r in rows(db,f'''SELECT ev.observation_id,m.id metric_id,m.event_id,m.perspective_id,m.call_id,
            p.import_id,ip.producer_key,e.file_id,ev.position_id,gp.event_id position_event_id,gp.source_line position_line,
            COALESCE(m.source_line,e.line_no) line_no FROM geo_mos_evidence ev
            JOIN metrics m ON m.id=ev.metric_id JOIN events e ON e.id=m.event_id
            JOIN perspectives p ON p.id=m.perspective_id JOIN geo_positions gp ON gp.id=ev.position_id
            LEFT JOIN import_producers ip ON ip.import_id=p.import_id
            LEFT JOIN observation_roles role ON role.perspective_id=p.id
            WHERE ev.observation_id IN ({','.join('?' for _ in ids)})
            AND (role.role IS NULL OR role.role='app')
            AND NOT EXISTS(SELECT 1 FROM effective_duplicates d WHERE d.perspective_id=p.id)''',ids):
            evidence[r['observation_id']].append(r)
    data=[r for r in data if evidence[r['id']]]
    if c['time_basis']=='legacy_observed':
        network=Context(db,{x['import_id'] for refs in evidence.values() for x in refs})
        expanded=[]
        for r in data:
            guard()
            for iid in {x['import_id'] for x in evidence[r['id']]}:
                boundaries=network.boundaries(iid,r['start'],r['end'])
                for a,b in zip(boundaries,boundaries[1:]):
                    expanded.append(dict(r,start=a,end=b,context=network.at(iid,a)))
                    bounded(expanded)
        data=expanded
    else:
        for r in data:r['context']=json.loads(r['context'])
    output=[]
    for _,group in groupby(sorted(data,key=lambda r:r['signature']),key=lambda r:r['signature']):
        guard();group=list(group)
        boundaries=sorted({max(r['start'],lo) for r in group}|{min(r['end'],hi) for r in group})
        for a,b in zip(boundaries,boundaries[1:]):
            active=[r for r in group if r['start']<b and r['end']>a]
            if not active:continue
            if len({(r['latitude'],r['longitude'],r['mos'],r['loss']) for r in active})!=1:
                excluded['conflicting_intervals']+=1;continue
            r=active[0]
            if grid(r['latitude'],r['longitude'],c['cell'])[0]!=c['cell_id']:continue
            context={}
            for field in FIELDS:
                values={x['context'].get(field,'unknown') for x in active}
                context[field]=values.pop() if len(values)==1 else 'unknown'
            if not matches(context,filters(c)):continue
            refs={ (x['metric_id'],x['position_id']):x for item in active for x in evidence[item['id']] }
            refs=list(refs.values())
            output.append(dict(start=a,end=b,value=r[c['metric']],context=context,
                series='intervals',series_context=dict(direction=c['direction'],model=r['model']),
                sources={source_key(x) for x in refs},calls={x['call_id'] for x in refs},
                accuracy=r['accuracy'],evidence=refs,observation_ids=sorted({x['id'] for x in active})))
    return bounded(output)


def point_observations(db,c,guard,excluded):
    if c['time_basis']=='utc':return []  # No inferred bridge from legacy clocks to structured telemetry.
    lo=c['start'] or '0001';hi=c['end'] or '9999'
    data=bounded(rows(db,'''SELECT m.*,p.import_id,ip.producer_key,e.file_id,COALESCE(m.source_line,e.line_no) line_no
        FROM metrics m JOIN perspectives p ON p.id=m.perspective_id JOIN events e ON e.id=m.event_id
        JOIN files f ON f.id=e.file_id LEFT JOIN import_producers ip ON ip.import_id=p.import_id
        LEFT JOIN observation_roles role ON role.perspective_id=p.id
        WHERE m.name=? AND m.ts>=? AND m.ts<? AND f.parser!='telemetry'
        AND (role.role IS NULL OR role.role='app')
        AND NOT EXISTS(SELECT 1 FROM effective_duplicates d WHERE d.perspective_id=p.id)
        ORDER BY m.ts,m.id LIMIT 100001''',(c['metric'],lo,hi)))
    sources={r['import_id'] for r in data};network=Context(db,sources)
    points={};times={}
    for iid in sources:
        guard()
        pp=bounded(rows(db,'''SELECT * FROM geo_positions WHERE import_id=? AND method=?
            AND kind IN ('fresh','sip_local') ORDER BY ts,id LIMIT 100001''',(iid,GEO_VERSION)))
        grouped=defaultdict(list)
        for p in pp:
            if p['kind']=='fresh' or c['quality']=='declared':grouped[p['ts']].append(p)
        points[iid]=grouped;times[iid]=sorted(grouped)
    def locate(r,ts):
        tt=times[r['import_id']];j=bisect_right(tt,ts)-1
        if j<0:return None
        stamp=tt[j];pp=[p for p in points[r['import_id']][stamp] if p['kind']=='fresh' or p['call_id']==r['call_id']]
        if not pp or any(not p['valid'] for p in pp) or len({(p['latitude'],p['longitude']) for p in pp})!=1:return None
        if (datetime.fromisoformat(ts)-datetime.fromisoformat(stamp)).total_seconds()>=120:return None
        p=pp[0]
        return p if grid(p['latitude'],p['longitude'],c['cell'])[0]==c['cell_id'] else None
    context_fields=('perspective_id','observer','device','output_device','input_device','lifecycle','flow','ssrc','direction','statistic','unit')
    grouped=defaultdict(list)
    for r in data:
        # RTCP outgoing remains explicitly a peer report at the app position.
        if c['metric'].startswith('rtcp.') and r['direction']!=('incoming' if c['direction']=='downstream' else 'outgoing'):continue
        grouped[tuple(r[k] for k in context_fields)].append(r)
    counter=next(m for m in METRICS if m['name']==c['metric'])['aggregation']=='counter_delta'
    output=[]
    for identity,group in grouped.items():
        previous=None
        sid=hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:20]
        for ts,batch in groupby(group,key=lambda r:r['ts']):
            guard();batch=list(batch);r=batch[0]
            if any(not x['valid'] for x in batch) or len({x['value'] for x in batch})!=1:
                excluded['invalid_or_conflicting_samples']+=len(batch);previous=None;continue
            p=locate(r,ts);ctx=network.at(r['import_id'],ts)
            old=previous;previous=r
            if not p or not matches(ctx,filters(c)):
                excluded['unlocated_or_filtered_samples']+=1;continue
            a=ts;value=r['value'];refs=[r]
            if counter:
                if old is None:excluded['initial_counter']+=1;continue
                seconds=(datetime.fromisoformat(ts)-datetime.fromisoformat(old['ts'])).total_seconds()
                if seconds<=0 or seconds>30 or r['value']<old['value']:
                    excluded['counter_reset_or_gap']+=1;continue
                before=locate(old,old['ts']);oldctx=network.at(old['import_id'],old['ts'])
                if not before or before['id']!=p['id'] or old['ts'][:13]!=ts[:13] or any(oldctx.get(k)!=ctx.get(k) for k in FIELDS) or len(network.boundaries(r['import_id'],old['ts'],ts))>2:
                    excluded['counter_crosses_time_position_or_network']+=1;continue
                a=old['ts'];value-=old['value'];refs=[old,r]
            ev=[dict(metric_id=x['id'],event_id=x['event_id'],file_id=x['file_id'],line_no=x['line_no'],position_id=p['id'],
                     position_event_id=p['event_id'],position_line=p['source_line']) for x in refs]
            output.append(dict(start=a,end=ts,value=value,context=ctx,series=sid,
                series_context={k:r[k] for k in context_fields},sources={source_key(r)},calls={r['call_id']},
                accuracy=p['accuracy'],evidence=ev,observation_ids=[]))
    return bounded(output)


def profile(db,raw):
    c,bounds=validate(raw);started=time.monotonic()
    def guard():
        if time.monotonic()-started>20:raise ValueError('Analisi oltre 20 secondi: restringere il periodo')
    excluded=defaultdict(int)
    db.set_progress_handler(lambda:int(time.monotonic()-started>20),10000)
    try:
        db.execute('BEGIN')
        observations=mos_observations(db,c,guard,excluded) if c['metric'] in ('mos','loss') else point_observations(db,c,guard,excluded)
        return summarize(c,bounds,observations,excluded,guard)
    finally:
        db.set_progress_handler(None,0);db.rollback()


def summarize(c,bounds,observations,excluded,guard):
    metric=next(m for m in METRICS if m['name']==c['metric'])
    series={r['series']:r['series_context'] for r in observations}
    if len(series)>100:raise ValueError('Oltre 100 serie: restringere il periodo o i filtri')
    populations={}
    # Explicit descriptive comparisons across calls; raw series and derivation identities stay separate.
    if metric['aggregation']=='sample_mean':
        groups=defaultdict(list)
        for sid,ctx in series.items():
            group_context={k:v for k,v in ctx.items() if k not in ('perspective_id','lifecycle','ssrc')}
            key=hashlib.sha256(json.dumps(group_context,sort_keys=True).encode()).hexdigest()[:20]
            groups[key].append(sid)
        for key,members in groups.items():
            if len(members)>1:populations['population:'+key]=dict(members=members,context={k:v for k,v in series[members[0]].items() if k not in ('perspective_id','lifecycle','ssrc')})
    if c['series_id'] and c['series_id'] not in series and c['series_id'] not in populations:raise ValueError('Serie non disponibile nei filtri correnti')
    chosen=c['series_id'] or (next(iter(series)) if len(series)==1 else '')
    members=populations.get(chosen,{}).get('members',[chosen])
    selected=sorted((r for r in observations if r['series'] in members),key=lambda r:(r['start'],r['end'],r['value']))
    bins={};coverage={};network={};per_series={};history=set();counter=metric['aggregation']=='counter_delta'
    def add(target,key,r,a,b,weight):
        bucket=target.setdefault(key,dict(total=0,weight=0,seconds=0,values=[],days=defaultdict(lambda:[0,0]),
            calls=set(),sources=set(),observations=set(),minimum=None,maximum=None,accuracy_max=None))
        value=r['value'];day=str(a.date());seconds=(b-a).total_seconds()
        bucket['total']+=value*weight;bucket['weight']+=weight;bucket['seconds']+=seconds
        bucket['days'][day][0]+=value*weight;bucket['days'][day][1]+=weight
        bucket['calls'].update(r['calls']);bucket['sources'].update(r['sources']);bucket['observations'].add(id(r))
        bucket['minimum']=value if bucket['minimum'] is None else min(bucket['minimum'],value)
        bucket['maximum']=value if bucket['maximum'] is None else max(bucket['maximum'],value)
        if r['accuracy'] is not None:bucket['accuracy_max']=max(bucket['accuracy_max'] or 0,r['accuracy'])
    pieces=0
    for r in selected:
        guard();a=datetime.fromisoformat(r['start']);end=datetime.fromisoformat(r['end'])
        while True:
            b=min(end,a.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)) if end>a else a
            weight=(b-a).total_seconds() if metric['aggregation']=='duration_mean' else 1
            if c['grain']=='day':h=str(a.date())
            elif c['grain']=='week':h=str((a-timedelta(days=a.weekday())).date())
            elif c['grain']=='month':h=a.strftime('%Y-%m')
            else:h=str(a.year)
            history.add(h)
            if len(history)>5000:raise ValueError('Oltre 5.000 periodi storici: usare settimana/mese/anno')
            for kind,key in [('history',h),('hour',a.hour),('weekday',a.weekday()),('week_hour',a.weekday()*24+a.hour),('month',a.month)]:
                add(bins,(kind,key),r,a,b,weight)
            add(coverage,'all',r,a,b,weight)
            add(per_series,r['series'],r,a,b,weight)
            add(network,tuple(r['context'].get(k,'unknown') for k in FIELDS),r,a,b,weight)
            pieces+=1
            if pieces>300000:raise ValueError('Troppi segmenti orari: restringere il periodo')
            if b>=end:break
            a=b
    def finish(bucket=None):
        if not bucket:return dict(mean=None,day_balanced_mean=None,total_delta=None,rate_per_second=None,
            observed_seconds=0,observations=0,days=0,calls=0,sources=0,limited=True,minimum=None,maximum=None,accuracy_max=None)
        days=bucket['days'];seconds=bucket['seconds']
        return dict(mean=None if counter else bucket['total']/bucket['weight'],
            day_balanced_mean=None if counter else sum(v/w for v,w in days.values())/len(days),
            total_delta=bucket['total'] if counter else None,
            rate_per_second=bucket['total']/seconds if counter and seconds else None,
            observed_seconds=seconds,observations=len(bucket['observations']),days=len(days),
            calls=len(bucket['calls']),sources=len(bucket['sources']),
            limited=len(days)<7 or len(bucket['sources'])<3 or len(bucket['calls'])<10,
            minimum=bucket['minimum'],maximum=bucket['maximum'],accuracy_max=bucket['accuracy_max'])
    grouped={}
    for kind,keys in [('history',sorted(history)),('hour',range(24)),('weekday',range(7)),('week_hour',range(168)),('month',range(1,13))]:
        grouped[kind]=[dict(key=k,**finish(bins.get((kind,k)))) for k in keys]
    offset=c['evidence_offset'];limit=c['evidence_limit']
    evidence=[dict(start=r['start'],end=r['end'],value=r['value'],references=r['evidence'][:100],references_total=len(r['evidence']),references_truncated=len(r['evidence'])>100,observation_ids=r['observation_ids'][:100]) for r in selected[offset:offset+limit]]
    snapshot=hashlib.sha256(json.dumps([(r['start'],r['end'],r['value'],r['evidence']) for r in selected],sort_keys=True).encode()).hexdigest()
    result=dict(version=VERSION,definition=c,cell=dict(id=c['cell_id'],size=c['cell'],bounds=bounds),
        metric=metric,time_basis=c['time_basis'],series=[dict(id=k,context=v) for k,v in series.items()],
        populations=[dict(id=k,**v) for k,v in populations.items()],
        series_breakdown=[dict(id=k,context=series[k],**finish(v)) for k,v in per_series.items()],
        selected_series=chosen,selection_required=len(series)>1 and not chosen,summary=finish(coverage.get('all')),
        profiles=grouped,network_breakdown=[dict(context=dict(zip(FIELDS,k)),**finish(v)) for k,v in network.items()],
        exclusions=dict(excluded),evidence=evidence,evidence_total=len(selected),evidence_offset=offset,
        evidence_more=offset+limit<len(selected),snapshot=snapshot,rules=RULES,
        coverage_policy=dict(min_days=7,min_sources=3,min_calls=10,meaning='Soglie esplorative di copertura, non intervalli di confidenza né validazione predittiva.'),
        forecast=dict(status='not_implemented',reason='Solo descrizione storica; nessuna previsione validata o modifica automatica dell’app.'))
    if len(json.dumps(result,ensure_ascii=False).encode())>4*1024*1024:raise ValueError('Risposta oltre 4 MiB: restringere il periodo')
    return result
