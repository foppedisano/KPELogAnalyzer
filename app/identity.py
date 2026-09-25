"""Conservative local SIP identity hints and explicit analyst confirmation."""
import json
import re
from .db import rows


def candidates(db, iid):
 if not db.execute('SELECT 1 FROM imports WHERE id=?',(iid,)).fetchone(): raise ValueError('Sorgente non trovata')
 found={}; count=0
 for row in db.execute("SELECT e.id,e.ts,e.text,e.line_no,f.name filename FROM events e JOIN files f ON f.id=e.file_id WHERE e.import_id=? AND e.kind='sip' ORDER BY e.ts,e.id LIMIT 50001",(iid,)):
  count+=1
  if count>50000: break
  text=row['text']
  # Responses echo both parties: never interpret them as local account evidence.
  request=re.search(r'^\s*(REGISTER|INVITE) sips?:\S+ SIP/2.0\s*$',text,re.M)
  if not request: continue
  outgoing='OUTGOING SIP' in text;incoming='INCOMING SIP' in text
  if request[1]=='REGISTER' and not outgoing: continue
  if not outgoing and not incoming: continue
  header='From' if outgoing else 'To'
  h=re.search(r'^\s*'+header+r':\s*(?:"([^"\n]*)"\s*)?(?:([^<\n]*?)\s*)?<sips?:([^>;\s]+)[^>]*>|^\s*'+header+r':\s*sips?:([^>;\s]+)',text,re.M|re.I)
  if not h: continue
  account=h[3] or h[4]; display=(h[1] or h[2] or '').strip()[:120]
  key=(account,display,request[1])
  group=found.setdefault(key,dict(account=account,display_name=display,basis='REGISTER uscente: identità dichiarata per registrazione' if request[1]=='REGISTER' else 'INVITE: parte locale dedotta dal verso del messaggio',confidence='account locale dichiarato' if request[1]=='REGISTER' else 'indizio da verificare',occurrences=0,evidence=[]))
  group['occurrences']+=1
  if len(group['evidence'])<5: group['evidence'].append(dict(event_id=row['id'],ts=row['ts'],filename=row['filename'],line=row['line_no']))
 confirmed=db.execute('SELECT * FROM source_identities WHERE import_id=?',(iid,)).fetchone()
 return dict(candidates=list(found.values())[:100],truncated=count>50000 or len(found)>100,confirmed=dict(confirmed) if confirmed else None,warning='Account e display name non provano l’identità della persona o del proprietario. Più account possono appartenere alla stessa sorgente; confermare manualmente.')


def confirm(db,obj):
 iid=int(obj['import_id']);name=str(obj.get('name','')).strip()[:120]
 if not name: raise ValueError('Inserisci il nome da associare alla sorgente')
 if not db.execute('SELECT 1 FROM imports WHERE id=?',(iid,)).fetchone(): raise ValueError('Sorgente non trovata')
 ids=list(dict.fromkeys(int(x) for x in obj.get('event_ids',[])))
 if len(ids)>10: raise ValueError('Massimo 10 evidenze')
 for eid in ids:
  if not db.execute('SELECT 1 FROM events WHERE id=? AND import_id=?',(eid,iid)).fetchone(): raise ValueError('Evidenza estranea alla sorgente')
 with db:
  db.execute('''INSERT INTO source_identities(import_id,name,account,note,evidence) VALUES(?,?,?,?,?)
   ON CONFLICT(import_id) DO UPDATE SET name=excluded.name,account=excluded.account,note=excluded.note,evidence=excluded.evidence,updated_at=CURRENT_TIMESTAMP''', (iid,name,str(obj.get('account',''))[:240],str(obj.get('note',''))[:2000],json.dumps(ids)))
  db.execute('UPDATE imports SET label=? WHERE id=?',(name,iid))
 return dict(ok=True)
