"""Deterministic diagnostics. All observations retain their evidence."""

from bisect import bisect_left

from datetime import datetime, timedelta

from .db import rows



NAMES = ('rtcp.rtt','vd.max_arrival_delay','vd.dejitter_target','vd.buffer','vd.silence_skipped','rtcp.jitter','rtcp.loss','vd.missing_packets','vd.silence_played','vd.underruns','vd.underrun_duration')

MAX_GAP = 30





def seconds(ts):

 date=datetime.fromisoformat(ts)
 if date.tzinfo: raise ValueError('Usa orari senza fuso, come nei log')
 return (date - datetime(1970,1,1)).total_seconds()





def evidence(m):

 return dict(event_id=m['event_id'],filename=m['filename'],line=m.get('source_line') or m['line_no'],metric_id=m['id'])





def interpolate(points, t):

 i = bisect_left(points, t, key=lambda p:p['t'])

 if i < len(points) and points[i]['t'] == t:

  return points[i]['value'], [points[i]['evidence']]

 if i == 0 or i == len(points) or points[i]['t']-points[i-1]['t'] > MAX_GAP:

  return None

 a,b=points[i-1],points[i]

 return a['value']+(b['value']-a['value'])*(t-a['t'])/(b['t']-a['t']), [a['evidence'],b['evidence']]





def diagnostics(db, a, b=None, device_a='NART0 of Line 0', device_b='NART0 of Line 0', rtt_threshold=200, buffer_threshold=500, start=None, end=None, offset_a=None, offset_b=None):

 if b == a:

  raise ValueError('A e B devono essere prospettive distinte')

 lower = seconds(start) if start else None

 upper = seconds(end) if end else None

 if lower is not None and upper is not None and lower >= upper: raise ValueError('Inizio analisi deve precedere la fine')

 series=[]; coverage=[]; findings=[]; audio_episodes=[]; incident_warnings=[]

 for side,pid,device in [('A',a,device_a),('B',b,device_b)]:

  if pid is None: continue

  p=db.execute('SELECT p.*,i.label,i.clock_offset FROM perspectives p JOIN imports i ON i.id=p.import_id WHERE p.id=?',(pid,)).fetchone()

  if not p: raise ValueError('Prospettiva non trovata')

  from .topology import decorate
  p=decorate(db,[dict(p)])[0]

  offset = (offset_a if side == 'A' else offset_b)

  if offset is None: offset = p['clock_offset']

  import math

  if not math.isfinite(offset) or abs(offset)>86400: raise ValueError('Offset massimo ±86400 secondi')

  conditions=[]; args=[pid,*NAMES]
  for bound,operator in ((lower,'>='),(upper,'<=')):
   if bound is not None:
    conditions.append('m.ts'+operator+'?')
    args.append((datetime(1970,1,1)+timedelta(seconds=bound-offset)).isoformat(' ',timespec='microseconds'))
  where=' AND '+' AND '.join(conditions) if conditions else ''
  data=rows(db,f'''SELECT m.*,e.line_no,f.name filename FROM metrics m JOIN events e ON e.id=m.event_id JOIN files f ON f.id=e.file_id
   WHERE m.perspective_id=? AND (m.valid=1 OR m.name IN ('vd.silence_skipped','vd.silence_played')) AND m.statistic='sample' AND m.name IN ({','.join('?' for _ in NAMES)}) {where} ORDER BY m.ts,m.id LIMIT 100001''',args)
  if len(data)>100000: raise ValueError('Oltre 100.000 campioni per prospettiva')

  groups={}

  for m in data:

   if m['name'].startswith('vd.') and m['device'] != device: continue

   t = seconds(m['ts']) + offset

   if (lower is not None and t < lower) or (upper is not None and t > upper): continue

   key=(m['name'],m['flow'],m['ssrc'],m['device'],m['sample_kind'],m['direction'],m['unit'],m['observer'],m['output_device'],m['input_device'],m['lifecycle'])

   groups.setdefault(key,[]).append(dict(t=t,value=m['value'],valid=m['valid'],evidence=evidence(m)))

  observed=set()

  for (name,flow,ssrc,dev,kind,direction,unit,observer,output_device,input_device,lifecycle),points in groups.items():

   observed.add(name)

   valid_points=[point for point in points if point['valid']]
   if not valid_points: continue
   item=dict(side=side,perspective_id=pid,label=p['label'],name=name,flow=flow,ssrc=ssrc,device=dev,observer=observer,output_device=output_device,input_device=input_device,lifecycle=lifecycle,kind=kind,points=valid_points,direction=direction,unit=unit)

   series.append(item)

   peak=max(valid_points,key=lambda x:x['value'])

   if name != 'vd.silence_skipped':

    findings.append(dict(side=side,name=name,device=dev,peak=peak,threshold=rtt_threshold if name=='rtcp.rtt' else None,exceeded=name=='rtcp.rtt' and peak['value']>rtt_threshold,flow=flow,ssrc=ssrc,direction=direction,unit=unit,observer=observer,output_device=output_device,input_device=input_device,lifecycle=lifecycle))

   if name in ('vd.silence_skipped','vd.silence_played') and unit == 'ms':

    from .single_metrics import silence_delta
    deltas=silence_delta(points,MAX_GAP)
    resets=sum(current['value']<previous['value'] for previous,current in zip(points,points[1:]))

    derived='derived.silence_played_delta' if name=='vd.silence_played' else 'derived.silence_delta'
    series.append(dict(item,name=derived,kind='interval',points=deltas))

    if deltas: findings.append(dict(side=side,name=derived,device=dev,kind='interval',peak=max(deltas,key=lambda x:x['value']),resets=resets,unit="ms",direction=direction,observer=observer,output_device=output_device,input_device=input_device,lifecycle=lifecycle))

  from .incidents import incidents
  audio=incidents(db,pid,device,offset,lower,upper)
  for episode in audio['episodes']: episode['side']=side
  audio_episodes.extend(audio['episodes'])
  incident_warnings.append(side+': '+audio['warning'])

  version=db.execute('SELECT version,event_id,ts FROM app_versions WHERE import_id=? AND ts<=? ORDER BY ts DESC,event_id DESC LIMIT 1',(p['import_id'],p['start'])).fetchone()

  coverage.append(dict(side=side,perspective_id=pid,label=p['label'],device=device,missing=[n for n in NAMES if n not in observed],version=dict(version) if version else None,clock_offset=offset,start=seconds(p['start'])+offset,end=seconds(p['end'])+offset if p['end'] else None))

 for source,derived,title in [('vd.buffer','derived.buffer_sum','Audio nei buffer A+B'),('vd.dejitter_target','derived.dejitter_sum','Limiti dinamici A+B')]:

  candidates=[[s for s in series if s['side']==side and s['name']==source and s['unit']=='ms'] for side in ('A','B')]
  buffers=[ss[0] if len(ss)==1 else None for ss in candidates]

  if all(buffers):

   points=[]

   for t in sorted({p['t'] for s in buffers for p in s['points']}):

    values=[interpolate(s['points'],t) for s in buffers]

    if all(v is not None for v in values): points.append(dict(t=t,value=sum(v[0] for v in values),evidence=[e for v in values for e in v[1]]))

   series.append(dict(side='A+B',name=derived,label=title,kind='derived',points=points,flow='',ssrc='',device='',direction='combined',unit='ms'))

   if points:

    peak=max(points,key=lambda p:p['value'])

    findings.append(dict(side='A+B',name=derived,peak=peak,threshold=buffer_threshold if source=='vd.buffer' else None,exceeded=source=='vd.buffer' and peak['value']>buffer_threshold,unit='ms',direction='combined'))

 from .metric_context import annotate
 annotate(db,series)
 for f in findings: f['perspective_id']=next((c['perspective_id'] for c in coverage if c['side']==f['side']),None)
 annotate(db,findings)
 return dict(incidents=audio_episodes,incident_warnings=incident_warnings,window=dict(start=lower,end=upper),series=series,coverage=coverage,findings=findings,max_gap_seconds=MAX_GAP,warning='Picchi e soglie sono indizi da verificare nei log. RTT non localizza da solo la rete guasta; la somma dei buffer non misura il ritardo conversazionale. Unità KPE raw escluse.')

