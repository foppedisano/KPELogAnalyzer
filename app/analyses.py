"""Validated, versioned analysis configurations (no metric snapshots)."""
import json
import math
import re
from datetime import datetime
from .diagnostics import NAMES

METRICS=(*NAMES,'derived.silence_delta','derived.silence_played_delta','derived.buffer_sum','derived.dejitter_sum')


def validate(db, raw):
 if not isinstance(raw,dict): raise ValueError('Configurazione non valida')
 c={k:raw[k] for k in ('a','b','device_a','device_b','offset_a','offset_b','start','end','rtt_threshold','buffer_threshold','silence_unit','metrics','styles') if k in raw}
 c['schema']=1
 c['a']=int(c.get('a',0));c['b']=int(c['b']) if c.get('b') else None
 if c['a']==c['b']: raise ValueError('A e B devono essere distinti')
 for pid in (c['a'],c['b']):
  if pid is not None and not db.execute('SELECT 1 FROM perspectives WHERE id=?',(pid,)).fetchone(): raise ValueError('Prospettiva non trovata')
 for key in ('offset_a','offset_b','rtt_threshold','buffer_threshold'):
  if key in c and c[key] is not None:
   c[key]=float(c[key])
   if not math.isfinite(c[key]) or (abs(c[key])>86400 if key.startswith('offset') else c[key]<0): raise ValueError('Offset o soglia non valida')
 for key in ('start','end'):
  if c.get(key):
   d=datetime.fromisoformat(c[key])
   if d.tzinfo: raise ValueError('Orario di analisi senza fuso richiesto')
   c[key]=d.isoformat(' ',timespec='microseconds')
 if c.get('start') and c.get('end') and c['start']>=c['end']: raise ValueError('Intervallo non valido')
 for key in ('device_a','device_b'):
  c[key]=str(c.get(key,'NART0 of Line 0'))[:100]
 if c.get('silence_unit','s') not in ('ms','s'): raise ValueError('Unità silenzio non valida')
 selected=c.get('metrics',list(METRICS))
 if not isinstance(selected,list) or any(m not in METRICS for m in selected): raise ValueError('Metrica non supportata')
 c['metrics']=list(dict.fromkeys(selected))
 styles=c.get('styles',{})
 if not isinstance(styles,dict) or len(styles)>200: raise ValueError('Troppe serie')
 for key,style in styles.items():
  if len(key)>2048 or not isinstance(style,dict) or not re.fullmatch(r'#[0-9a-fA-F]{6}',str(style.get('color',''))): raise ValueError('Colore non valido')
  if not isinstance(style.get('visible',True),bool): raise ValueError('Visibilità non valida')
  if style.get('symbol','circle') not in ('circle','square','triangle','diamond'): raise ValueError('Simbolo non valido')
 return c


def save(db,obj,update=False):
 title=str(obj.get('title','')).strip()[:200]
 if not title: raise ValueError('Titolo richiesto')
 config=validate(db,obj.get('config'))
 encoded=json.dumps(config,ensure_ascii=False)
 if len(encoded)>48000: raise ValueError('Configurazione troppo grande')
 with db:
  if update:
   aid=int(obj['id']);revision=int(obj['revision'])
   cursor=db.execute('UPDATE saved_analyses SET title=?,config=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND revision=?',(title,encoded,aid,revision))
   if not cursor.rowcount: raise ValueError('Analisi modificata o non trovata: ricaricala prima di salvare')
  else:
   aid=db.execute('INSERT INTO saved_analyses(title,config) VALUES(?,?)',(title,encoded)).lastrowid
 return dict(db.execute('SELECT * FROM saved_analyses WHERE id=?',(aid,)).fetchone())
