"""Source-family event explorer. Context selection never changes stored attribution."""
import re
from datetime import datetime, timedelta
from pathlib import PurePosixPath


KNOWN = {'vdlog':'VDLog','kpelog':'KPELog','rtplog':'RTPLog','sip_debug':'SIP Debug',
         'vdklog':'VDKLog','callinfo':'CallInfo','phoneengine':'PhoneEngine',
         'telemetry':'Telemetry','app':'App','info':'Info',
         'ios_hwwrapper':'iOS HWWrapper','kpe-android':'KPE Android',
         'store':'Store','ctilib':'CTILib','notificationservice':'NotificationService',
         'mediastatslog':'MediaStatsLog','resip':'Resip','regid':'RegID',
         'intentextension':'IntentExtension','shareextension':'ShareExtension','chatengine':'ChatEngine'}


def family(name):
    base=PurePosixPath(name.replace('\\','/')).name.lower()
    # Strip known extensions and numeric rotation suffixes, never arbitrary words.
    base=re.sub(r'\.(txt|log|jsonl)(?=\.|$)','',base)
    base=re.sub(r'(?:[_.-]\d+)+$','',base)
    return base or 'other'


def label(key):
    return KNOWN.get(key,key)


def bounded(db,p):
    p=dict(p)
    p['stored_end']=p.get('end')
    p['window_evidence']=None
    # Only repair legacy local line windows in this read model. SIP and manual
    # identities retain their explicit semantics and analyst annotations.
    c=db.execute('SELECT call_key FROM calls WHERE id=?',(p['call_id'],)).fetchone()
    if c and c[0].startswith('local:') and p['line_id'] is not None and p['start']:
        e=db.execute('''SELECT e.id,e.ts,e.line_no,f.name filename FROM events e
            JOIN files f ON f.id=e.file_id WHERE e.import_id=? AND e.line_id=? AND e.perspective_id=? AND e.call_id=?
            AND e.ts>=? AND (? IS NULL OR e.ts<=?) AND f.parser='kpe'
            AND (instr(e.text,'removed from list') OR instr(e.text,'Send socket event for call terminated'))
            ORDER BY e.ts,e.id LIMIT 1''',(p['import_id'],p['line_id'],p['id'],p['call_id'],p['start'],p['end'],p['end'])).fetchone()
        if e and (not p['end'] or e['ts']<p['end']):
            p['end']=e['ts'];p['window_evidence']=dict(e)
    if not p['end']:
        p['end']=db.execute('SELECT MAX(ts) FROM events WHERE import_id=? AND call_id=?',
                           (p['import_id'],p['call_id'])).fetchone()[0]
    return p


def windows(db,cid):
    return [bounded(db,p) for p in db.execute('SELECT * FROM perspectives WHERE call_id=? ORDER BY id',(cid,))]


def query(db,cid,modes=None,search='',level='',offset=0,attempt_id=None):
    selected_id=attempt_id if attempt_id is not None else cid
    if type(selected_id) is not int or selected_id<1 or type(offset) is not int or offset<0:raise ValueError('ID/offset non valido')
    evidence_ids=[]
    if attempt_id is not None:
        if cid is not None:raise ValueError('Selezionare chiamata oppure tentativo')
        attempt=db.execute('SELECT * FROM user_attempts WHERE event_id=?',(attempt_id,)).fetchone()
        if not attempt:raise ValueError('Tentativo non trovato')
        evidence_ids=list({i for i in (attempt['event_id'],attempt['reason_event_id']) if i is not None})
        t=datetime.fromisoformat(attempt['ts'])
        reason=db.execute('SELECT ts FROM events WHERE id=? AND import_id=?',
                          (attempt['reason_event_id'],attempt['import_id'])).fetchone()
        end=max(t,datetime.fromisoformat(reason['ts'])) if reason and reason['ts'] else t
        ww=[dict(id=attempt_id,import_id=attempt['import_id'],start=(t-timedelta(seconds=60)).isoformat(' ',timespec='microseconds'),
                 end=end.isoformat(' ',timespec='microseconds'),stored_end=None,window_evidence=None)]
    else:
        if not db.execute('SELECT 1 FROM calls WHERE id=?',(cid,)).fetchone():raise ValueError('Chiamata non trovata')
        ww=windows(db,cid)
    default_mode='evidence' if attempt_id is not None else 'call'
    if modes is not None and (not isinstance(modes,dict) or len(modes)>200 or any(not isinstance(k,str) or v not in (default_mode,'interval','hide') for k,v in modes.items())):
        raise ValueError('Modalità log non valide')
    files={}
    for p in ww:
        for f in db.execute('SELECT id,name FROM files WHERE import_id=?',(p['import_id'],)):
            key=family(f['name']);files.setdefault(key,set()).add(f['id'])
    if modes and set(modes)-set(files):raise ValueError('Famiglia log sconosciuta')
    families=[dict(id=k,label=label(k),mode=(modes or {}).get(k,default_mode)) for k in sorted(files)]
    scope=[];scope_args=[];call_scope=[];call_args=[]
    for p in ww:
        if attempt_id is not None:
            clause='e.import_id=? AND e.id IN ('+','.join('?' for _ in evidence_ids)+')'
            call_args.extend([p['import_id'],*evidence_ids])
        else:
            clause='e.import_id=? AND e.call_id=?';call_args.extend([p['import_id'],cid])
        if p['window_evidence']:
            clause+=' AND (e.ts IS NULL OR e.ts<=?)';call_args.append(p['end'])
        call_scope.append('('+clause+')')
        if p['start'] and p['end']:
            scope.append('(e.import_id=? AND e.ts>=? AND e.ts<=?)')
            scope_args.extend([p['import_id'],p['start'],p['end']])
    selected=[];args=[]
    for mode in (default_mode,'interval'):
        ids=sorted({fid for f in families if f['mode']==mode for fid in files[f['id']]})
        if not ids:continue
        clause='e.file_id IN ('+','.join('?' for _ in ids)+')';args.extend(ids)
        if mode==default_mode:
            clause+=' AND ('+(' OR '.join(call_scope) or '0')+')';args.extend(call_args)
        else:
            clause+=' AND ('+(' OR '.join(scope) or '0')+')';args.extend(scope_args)
        selected.append('('+clause+')')
    data=[]
    if selected:
        where='('+' OR '.join(selected)+')'
        if search:where+=' AND e.text LIKE ?';args.append('%'+search+'%')
        if level:where+=' AND e.level=?';args.append(level)
        data=[dict(r) for r in db.execute('''SELECT e.*,f.name filename,i.label source_label
            FROM events e JOIN files f ON f.id=e.file_id JOIN imports i ON i.id=e.import_id
            WHERE '''+where+' ORDER BY e.ts,e.id LIMIT 101 OFFSET ?',[*args,offset])]
    # Annotate only actual explicit switches; default selection stays strict call-only.
    from .network_switches import collect,explicit
    contexts={}
    for e in data[:100]:
        key=family(e['filename']);e['log_family']=key;e['log_label']=label(key)
        e['is_context']=e['id'] not in evidence_ids if attempt_id is not None else e['call_id']!=cid
        if explicit(e['text'],e['filename']):
            if e['import_id'] not in contexts:
                contexts[e['import_id']]=collect(db,import_id=e['import_id'])
            s=next((s for s in contexts[e['import_id']] if any(v['event_id']==e['id'] for v in s['evidence'])),None)
            if s:e['network_switch']=s
    return dict(events=data[:100],more=len(data)>100,offset=offset,families=families,
                windows=[{k:p[k] for k in ('id','import_id','start','end','stored_end','window_evidence')} for p in ww])
