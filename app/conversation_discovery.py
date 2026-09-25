"""Evidence-backed conversation groups. Never rewrites SIP identity or raw outcomes."""
import json
import re
import uuid
from datetime import datetime
from .db import rows

VERSION='conversation-discovery-1'


def sip_headers(text):
    """Only headers of an actual SIP message, never body or authentication fields."""
    lines=text.splitlines()
    start=next((i for i,l in enumerate(lines) if re.match(r'^\s*(?:[A-Z]+ sips?:\S+ SIP/2.0|SIP/2.0 \d{3})',l)),None)
    if start is None:return []
    result=[]
    for i in range(start+1,len(lines)):
        if not lines[i].strip():break
        m=re.match(r'^([\w-]+):\s*(.*)$',lines[i])
        if m and m[1].lower() in ('x-call-uuid','reason'):
            result.append((m[1].lower(),m[2].strip(),i))
    return result


def enrich(db,iid):
    marker=f'{VERSION}:{iid}'
    if db.execute('SELECT 1 FROM meta WHERE key=?',(marker,)).fetchone():return
    from .parser import sip
    files=rows(db,'SELECT id,name FROM files WHERE import_id=?',(iid,))
    names={f['name'].rsplit('/',1)[-1].lower() for f in files}
    platform='android' if any(n.startswith('kpe-android') for n in names) else 'ios' if 'ios_hwwrapper.log' in names else 'unknown'
    profile=dict(platform=platform,app_version=None,os_version=None,model=None,evidence=[],
        has_periodic_callinfo=any(n.startswith('callinfo') for n in names),version_scope='export_metadata')
    for f in files:
        if f['name'].rsplit('/',1)[-1].lower()!='info.log':continue
        for e in rows(db,'SELECT id,text,line_no FROM events WHERE file_id=? ORDER BY id LIMIT 10',(f['id'],)):
            for offset,line in enumerate(e['text'].splitlines()):
                m=re.match(r'^\s*(DEVICE MODEL|OS VERSION|APP VERSION)\s*:\s*(.{1,120})\s*$',line,re.I)
                if not m:continue
                key={'DEVICE MODEL':'model','OS VERSION':'os_version','APP VERSION':'app_version'}[m[1].upper()]
                profile[key]=m[2].strip()
                profile['evidence'].append(dict(event_id=e['id'],filename=f['name'],line=e['line_no']+offset,field=key))
    db.execute('INSERT OR REPLACE INTO source_profiles VALUES(?,?)',(iid,json.dumps(profile)))
    for e in db.execute("SELECT * FROM events WHERE import_id=? AND kind='sip' AND (text LIKE '%X-Call-UUID:%' OR text LIKE '%Call completed elsewhere%') ORDER BY id",(iid,)):
        message=sip(e['text'])
        if not message:continue
        for key,value,offset in sip_headers(e['text']):
            if key=='x-call-uuid' and message['method']=='INVITE' and message['response'] is None and e['call_id']:
                try: parsed=uuid.UUID(value.strip('{}'))
                except (ValueError,AttributeError):continue
                if not parsed.int:continue
                db.execute('INSERT OR IGNORE INTO call_correlations VALUES(?,?,?,?)',(e['id'],e['call_id'],str(parsed),e['line_no']+offset))
            if key=='reason' and message['method']=='CANCEL' and message['response'] is None and e['perspective_id']:
                if re.search(r'\bcause\s*=\s*200\b',value,re.I) and re.search(r'\bCall completed elsewhere\b',value,re.I):
                    db.execute('INSERT OR IGNORE INTO leg_outcomes VALUES(?,?,?)',(e['id'],e['perspective_id'],'answered_elsewhere'))
    db.execute('INSERT INTO meta VALUES(?,?)',(marker,'done'))


def profiles(db):
    return {r['import_id']:json.loads(r['profile']) for r in rows(db,'SELECT * FROM source_profiles')}


def groups(db):
    """Derived groups with stable keys; UUID conflicts remain visible for review."""
    ps=rows(db,'''SELECT p.*,i.label,i.name import_name,c.sip_call_id,c.caller,c.callee,
        r.session,r.participant,r.role,r.node FROM perspectives p JOIN imports i ON i.id=p.import_id
        JOIN calls c ON c.id=p.call_id LEFT JOIN observation_roles r ON r.perspective_id=p.id ORDER BY p.start,p.id''')
    counts={r['perspective_id']:r['n'] for r in rows(db,'SELECT perspective_id,count(*) n FROM metrics WHERE perspective_id IS NOT NULL GROUP BY perspective_id')}
    source=profiles(db)
    outcomes={}
    for r in rows(db,'''SELECT o.*,e.ts,f.name filename,e.line_no FROM leg_outcomes o
        JOIN events e ON e.id=o.event_id JOIN files f ON f.id=e.file_id'''):
        outcomes.setdefault(r['perspective_id'],[]).append(r)
    bycall={}
    for p in ps:
        p['profile']=source.get(p['import_id'],{})
        p['metrics']=counts.get(p['id'],0)
        p['outcomes']=outcomes.get(p['id'],[])
        p['display_status']='answered_elsewhere' if p['outcomes'] else p['status']
        bycall.setdefault(p['call_id'],[]).append(p)
    correlations=rows(db,'''SELECT r.*,e.import_id,e.ts,f.name filename FROM call_correlations r
        JOIN events e ON e.id=r.event_id JOIN files f ON f.id=e.file_id ORDER BY e.ts,e.id''')
    byuuid={};calluuids={}
    for r in correlations:
        byuuid.setdefault(r['uuid'],[]).append(r)
        calluuids.setdefault(r['call_id'],set()).add(r['uuid'])
    result=[]
    def add(key,title,kind,members,evidence=None,note='',review=False):
        if not members:return
        starts=[p['start'] for p in members if p['start']]
        ends=[p['end'] for p in members if p['end']]
        result.append(dict(key=key,title=title,kind=kind,review=review,note=note,
            start=min(starts) if starts else None,end=max(ends) if ends else None,
            call_ids=sorted({p['call_id'] for p in members}),source_count=len({p['import_id'] for p in members}),
            perspectives=members,evidence=evidence or []))
    covered=set()
    for uid,proof in byuuid.items():
        ids={r['call_id'] for r in proof}
        members=[p for cid in ids for p in bycall.get(cid,[])]
        if len(members)<2:continue
        starts=[datetime.fromisoformat(p['start']) for p in members if p['start']]
        review=any(len(calluuids[cid])>1 for cid in ids) or (starts and (max(starts)-min(starts)).total_seconds()>86400)
        add('uuid:'+uid,'Conversazione · '+uid[:8],'uuid',members,proof,
            'X-Call-UUID condiviso negli INVITE. Include tentativi e rami annullati; non prova audio su ogni dispositivo.',bool(review))
        covered.update(ids)
    for cid,members in bycall.items():
        if cid not in covered and len(members)>1:
            add('call:'+str(cid),'Chiamata condivisa #'+str(cid),'sip',members,note='Stesso SIP Call-ID in più log set; possono essere esportazioni ripetute dello stesso dispositivo.')
    for manual in rows(db,'SELECT * FROM conversations'):
        ids=[r[0] for r in db.execute('SELECT call_id FROM conversation_calls WHERE conversation_id=?',(manual['id'],))]
        add('manual:'+str(manual['id']),manual['title'],'manual',[p for cid in ids for p in bycall.get(cid,[])],note=manual['note'])
    for session in sorted({p['session'] for p in ps if p['session']}):
        add('session:'+session,session,'session',[p for p in ps if p['session']==session],note='Associazione esplicita da App e xcoder.')
    result.sort(key=lambda g:g['start'] or '',reverse=True)
    return result
