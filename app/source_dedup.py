"""Conservative producer identity and whole-call import decisions.

Never use an account, remote Contact, ZIP name, IP or time overlap as identity.
Legacy evidence is deliberately restricted to the locally observed app patterns.
"""
import hashlib
import json
import re
import uuid
from datetime import datetime

VERSION = 'source-identity-1'
SCHEMA = '''
CREATE TABLE IF NOT EXISTS import_producers(
 import_id INTEGER PRIMARY KEY REFERENCES imports(id), producer_key TEXT,
 role TEXT, platform TEXT, status TEXT NOT NULL, basis TEXT NOT NULL,
 evidence TEXT NOT NULL, method TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS producer_key_idx ON import_producers(producer_key);
CREATE TABLE IF NOT EXISTS duplicate_perspectives(
 perspective_id INTEGER PRIMARY KEY REFERENCES perspectives(id),
 canonical_id INTEGER NOT NULL REFERENCES perspectives(id), method TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS import_call_skips(
 import_id INTEGER NOT NULL REFERENCES imports(id), call_id INTEGER NOT NULL REFERENCES calls(id),
 canonical_id INTEGER NOT NULL REFERENCES perspectives(id), windows TEXT NOT NULL DEFAULT '[]',
 PRIMARY KEY(import_id,call_id));
CREATE VIEW IF NOT EXISTS effective_duplicates AS
 SELECT d.* FROM duplicate_perspectives d
 JOIN perspectives p ON p.id=d.perspective_id JOIN perspectives c ON c.id=d.canonical_id
 JOIN import_producers ip ON ip.import_id=p.import_id
 WHERE NOT EXISTS (SELECT 1 FROM observation_roles r JOIN perspectives rp ON rp.id=r.perspective_id
   WHERE rp.import_id IN (p.import_id,c.import_id) AND r.role!=ip.role);
'''


def infer(records, names):
    names = {n.rsplit('/', 1)[-1].lower() for n in names}
    platforms = set()
    if 'ios_hwwrapper.log' in names: platforms.add('ios')
    if any(n.startswith('kpe-android') for n in names): platforms.add('android')
    instances, devices, telemetry = set(), set(), set()
    evidence = {}
    malformed = False
    for r in records:
        text = r['text']
        filename = r.get('filename', '').rsplit('/', 1)[-1].lower()
        def proof(kind, offset=0):
            evidence.setdefault(kind, dict(event_id=r.get('id'), file_id=r.get('file',r.get('file_id')),
                                           line=r['line_no']+offset, record_line=r['line_no'], field=kind))
        if filename.startswith('telemetry') and filename.endswith('.jsonl'):
            # Validated payloads from parser; historical JSON uses the same validator below.
            event = r.get('telemetry')
            if event is None:
                from .telemetry import records as read_records
                parsed = list(read_records(text))
                if len(parsed) == 1 and not parsed[0][4]: event = parsed[0][3]
            if event and not r.get('errors'):
                telemetry.add((event['source_id'], event['role']))
                proof('telemetry.source_id')
            else: malformed = True
            continue
        if filename.startswith('sip_debug'):
            lines = text.splitlines()
            start = next((i for i,l in enumerate(lines) if re.fullmatch(r'\s*(?:[A-Z]+ sips?:\S+ SIP/2.0|SIP/2.0 \d{3}.*)\s*',l)),None)
            if start is None or not re.fullmatch(r'\s*REGISTER sips?:\S+ SIP/2.0\s*',lines[start]): continue
            prefix = '\n'.join(lines[:start])
            if 'OUTGOING SIP message:' not in prefix or 'INCOMING SIP' in prefix: continue
            if any(re.fullmatch(r'\s*(?:[A-Z]+ sips?:\S+ SIP/2.0|SIP/2.0 \d{3}.*)\s*',l) for l in lines[start+1:]):
                malformed=True
                continue
            for offset in range(start+1,len(lines)):
                line=lines[offset]
                if not line.strip(): break
                if not re.match(r'^Contact\s*:',line,re.I): continue
                if '+sip.instance' not in line: continue
                matches=list(re.finditer(r'\+sip\.instance\s*=\s*"<urn:(?:uid|uuid):([0-9a-f-]{36})>"',line,re.I))
                if len(matches)!=1: malformed=True; continue
                try: value=uuid.UUID(matches[0][1])
                except ValueError: malformed=True; continue
                if not value.int: malformed=True; continue
                instances.add(str(value)); proof('outgoing_register_instance',offset)
        if filename.startswith('ctilib'):
            for offset,line in enumerate(text.splitlines()):
                m=re.match(r'^\[[^\]\n]+\]\s+\[CTILIB\]\s+\[INFO\]\s+Sending auth to CTIServer - username: [^\n]*? - OS: (ios|android)\b[^\n]*? - software: [^\n]*? - device ID: ([^\s]{1,200}) - pre-shared key:',line)
                if m: devices.add((m[1],m[2])); proof('local_cti_device',offset)
    result=dict(producer_key=None,role=None,platform=next(iter(platforms)) if len(platforms)==1 else 'unknown',
                status='unknown',basis='Identità locale insufficiente: importazione conservata',evidence=list(evidence.values()),method=VERSION)
    if malformed:
        result.update(status='ambiguous',basis='Identificativi locali malformati o telemetria non verificabile');return result
    if telemetry:
        if len(telemetry)!=1 or instances or devices:
            result.update(status='ambiguous',basis='Più produttori o formati di identità nello stesso archivio');return result
        source,role=next(iter(telemetry));material=['telemetry',role,source]
        result.update(role=role,basis='source_id e ruolo della telemetria validata')
    elif len(platforms)==1 and len(instances)==1 and len(devices)==1:
        platform=next(iter(platforms));device_platform,device=next(iter(devices))
        if device_platform!=platform:
            result.update(status='ambiguous',basis='Piattaforma locale discordante');return result
        material=['legacy-app',platform,next(iter(instances)),device]
        result.update(role='app',basis='REGISTER uscente + device ID CTI locale + piattaforma')
    else:
        if len(platforms)>1 or len(instances)>1 or len(devices)>1:
            result.update(status='ambiguous',basis='Identificativi locali multipli: nessuno scarto automatico')
        return result
    result.update(status='resolved',producer_key=hashlib.sha256(json.dumps(material).encode()).hexdigest())
    return result


def save(db,iid,result):
    for proof in result['evidence']:
        if proof['event_id'] is None:
            event=db.execute('SELECT id FROM events WHERE import_id=? AND file_id=? AND line_no=?',
                             (iid,proof['file_id'],proof['record_line'])).fetchone()
            if event: proof['event_id']=event[0]
    db.execute('INSERT OR REPLACE INTO import_producers VALUES(?,?,?,?,?,?,?,?)',
               (iid,result['producer_key'],result['role'],result['platform'],result['status'],result['basis'],json.dumps(result['evidence']),VERSION))


def usable(db,iid,identity):
    return identity['producer_key'] and not db.execute('''SELECT 1 FROM observation_roles r
        JOIN perspectives p ON p.id=r.perspective_id WHERE p.import_id=? AND r.role!=? LIMIT 1''',(iid,identity['role'])).fetchone()


def previous(db,iid,identity):
    # Structured telemetry already deduplicates stable events, checks conflicts,
    # and retains every evidence copy. Do not bypass that stricter contract.
    if identity['basis']=='source_id e ruolo della telemetria validata':return {}
    if not usable(db,iid,identity):return {}
    rows=db.execute('''SELECT p.*,c.sip_call_id FROM perspectives p JOIN calls c ON c.id=p.call_id
        JOIN import_producers i ON i.import_id=p.import_id
        WHERE i.producer_key=? AND p.import_id<? AND c.sip_call_id IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM observation_roles r JOIN perspectives rp ON rp.id=r.perspective_id
            WHERE rp.import_id=p.import_id AND r.role!=i.role)
        ORDER BY p.import_id,p.id''',(identity['producer_key'],iid))
    found={}
    for row in rows:found.setdefault(row['sip_call_id'],dict(row))
    return found


def refresh_duplicates(db,iid,identity):
    prior=previous(db,iid,identity)
    for row in db.execute('SELECT p.id,c.sip_call_id FROM perspectives p JOIN calls c ON c.id=p.call_id WHERE p.import_id=?',(iid,)):
        if row['sip_call_id'] in prior:
            db.execute('INSERT OR IGNORE INTO duplicate_perspectives VALUES(?,?,?)',(row['id'],prior[row['sip_call_id']]['id'],VERSION))


def pending(db):
    for row in db.execute('SELECT id FROM imports WHERE id NOT IN (SELECT import_id FROM import_producers) ORDER BY id').fetchall():
        iid=row['id']
        records=db.execute('''SELECT e.id,e.file_id,e.line_no,e.text,f.name filename FROM events e
            JOIN files f ON f.id=e.file_id WHERE e.import_id=? AND
            (lower(f.name) LIKE '%sip_debug%' OR lower(f.name) LIKE '%ctilib%' OR f.parser='telemetry') ORDER BY e.id''',(iid,))
        identity=infer((dict(r) for r in records),[r[0] for r in db.execute('SELECT name FROM files WHERE import_id=?',(iid,))])
        with db:
            save(db,iid,identity);refresh_duplicates(db,iid,identity)


def skipped_windows(db,iid):
    return [w for r in db.execute('SELECT windows FROM import_call_skips WHERE import_id=?',(iid,)) for w in json.loads(r[0])]


def skip_measurement(windows, kept, line, ts):
    if line is None or not ts:return False
    def matches(p):
        return p['line_id']==line and p['start']<=ts and (not p['end'] or (datetime.fromisoformat(ts)-datetime.fromisoformat(p['end'])).total_seconds()<=.25)
    return any(matches(w) for w in windows) and not any(matches(p) for p in kept)


def filter_duplicates(db,data):
    duplicates={r[0] for r in db.execute('SELECT perspective_id FROM effective_duplicates')}
    return [r for r in data if r.get('perspective_id') not in duplicates]


def describe(db,iid):
    row=db.execute('SELECT * FROM import_producers WHERE import_id=?',(iid,)).fetchone()
    if not row:return None
    result=dict(row);result['evidence']=json.loads(result['evidence'])
    result['producer_key']=result['producer_key'][:12] if result['producer_key'] else None
    result['skipped_calls']=db.execute('SELECT COUNT(*) FROM import_call_skips WHERE import_id=?',(iid,)).fetchone()[0]
    result['historical_duplicates']=db.execute('SELECT COUNT(*) FROM effective_duplicates d JOIN perspectives p ON p.id=d.perspective_id WHERE p.import_id=?',(iid,)).fetchone()[0]
    return result
