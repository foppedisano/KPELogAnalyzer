"""Explicit analyst windows for exports without call lifecycle evidence."""
import io
import zipfile
from datetime import datetime
from .parser import ingest, MAX_FILE, MAX_EXPANDED


def import_text(db, obj):
 files=obj.get('files',[])
 if not isinstance(files,list) or not 1<=len(files)<=20:
  raise ValueError('Seleziona da 1 a 20 file dello stesso dispositivo')
 buffer=io.BytesIO();total=0
 with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
  for f in files:
   name=f['name'];text=f['text']
   if not isinstance(name,str) or not isinstance(text,str): raise ValueError('File testuale non valido')
   raw=text.encode('utf-8');total+=len(raw)
   if len(raw)>MAX_FILE or total>MAX_EXPANDED: raise ValueError('File oltre i limiti di importazione')
   info=zipfile.ZipInfo(name,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
   z.writestr(info,raw)
 return ingest(db,buffer.getvalue(),'text-files.zip',str(obj.get('label','File testuali'))[:120])


def manual_window(db,obj, edit=False):
 import json
 old = None
 if edit:
  old=db.execute("SELECT p.*,c.call_key,c.caller title FROM perspectives p JOIN calls c ON c.id=p.call_id WHERE p.id=?",(int(obj['perspective_id']),)).fetchone()
  if not old or not old['call_key'].startswith('manual:'): raise ValueError('Solo finestre manuali modificabili')
 iid=old['import_id'] if old else int(obj['import_id']);line=int(obj.get('line_id',0))
 start_date=datetime.fromisoformat(obj['start']);end_date=datetime.fromisoformat(obj['end'])
 if start_date.tzinfo or end_date.tzinfo: raise ValueError('Usa orari senza fuso, come nei log')
 start=start_date.isoformat(' ',timespec='microseconds')
 end=end_date.isoformat(' ',timespec='microseconds')
 if line<0 or start>=end or '+' in start or '+' in end: raise ValueError('Finestra o linea non valida; usa gli orari locali dei log senza fuso')
 if not db.execute('SELECT 1 FROM imports WHERE id=?',(iid,)).fetchone(): raise ValueError('Importazione non trovata')
 if db.execute('SELECT 1 FROM perspectives WHERE import_id=? AND line_id=? AND id<>? AND start<=? AND (end IS NULL OR end>=?)',(iid,line,old['id'] if old else -1,end,start)).fetchone():
  raise ValueError('La finestra si sovrappone a una chiamata della stessa linea; scegli una finestra non ambigua')
 with db:
  if old:
   pid,cid=old['id'],old['call_id']
   db.execute('INSERT INTO window_revisions(perspective_id,snapshot) VALUES(?,?)',(pid,json.dumps(dict(old))))
   db.execute('UPDATE metrics SET call_id=NULL,perspective_id=NULL WHERE perspective_id=?',(pid,))
   db.execute('UPDATE periodic_metadata SET call_id=NULL,perspective_id=NULL WHERE perspective_id=?',(pid,))
   db.execute('UPDATE events SET call_id=NULL,perspective_id=NULL WHERE perspective_id=?',(pid,))
   db.execute('UPDATE perspectives SET line_id=?,start=?,end=? WHERE id=?',(line,start,end,pid))
   db.execute('UPDATE calls SET caller=?,start=?,end=? WHERE id=?',(str(obj.get('title',old['title']))[:200],start,end,cid))
  else:
   from uuid import uuid4
   key=f'manual:{iid}:{uuid4()}'
   cid=db.execute('INSERT INTO calls(call_key,caller,start,end) VALUES(?,?,?,?)',(key,str(obj.get('title','Finestra manuale'))[:200],start,end)).lastrowid
   pid=db.execute("INSERT INTO perspectives(call_id,import_id,line_id,start,end,status,evidence) VALUES(?,?,?,?,?,'manual / partial','Analyst-defined time window; no SIP identity')",(cid,iid,line,start,end)).lastrowid
  # A VD event may contain several devices. Assign metrics individually, not the entire block.
  candidates=list(db.execute('''SELECT m.id,e.line_id,m.device,m.output_device FROM metrics m JOIN events e ON e.id=m.event_id
   WHERE e.import_id=? AND m.call_id IS NULL AND m.ts>=? AND m.ts<=?''',(iid,start,end)))
  import re
  for m in candidates:
   device=re.search(r'of Line (\d+)',m['device'] or '')
   if not device and m['device']=='Default Audio Input': device=re.search(r'of Line (\d+)',m['output_device'] or '')
   metric_line=int(device[1]) if device else m['line_id']
   if metric_line==line: db.execute('UPDATE metrics SET call_id=?,perspective_id=? WHERE id=?',(cid,pid,m['id']))
  db.execute('UPDATE events SET call_id=?,perspective_id=? WHERE import_id=? AND call_id IS NULL AND line_id=? AND ts>=? AND ts<=?',(cid,pid,iid,line,start,end))
  db.execute('UPDATE periodic_metadata SET call_id=?,perspective_id=? WHERE import_id=? AND call_id IS NULL AND line_id=? AND ts>=? AND ts<=?',(cid,pid,iid,line,start,end))
 return dict(call_id=cid,perspective_id=pid)
