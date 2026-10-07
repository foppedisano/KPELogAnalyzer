"""Source-local connectivity evidence and explicit user attempts (no causal guessing)."""
import re
from datetime import datetime, timedelta

VERSION = 'connectivity-2'
TTL = 30
LAYERS = ('network', 'device', 'stun', 'cti', 'sip', 'media', 'app')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS connectivity_events(
 event_id INTEGER NOT NULL REFERENCES events(id), layer TEXT NOT NULL,
 import_id INTEGER NOT NULL REFERENCES imports(id), ts TEXT NOT NULL,
 state TEXT NOT NULL, reason TEXT NOT NULL, call_id INTEGER REFERENCES calls(id),
 PRIMARY KEY(event_id,layer));
CREATE INDEX IF NOT EXISTS connectivity_source_time ON connectivity_events(import_id,ts);
CREATE INDEX IF NOT EXISTS connectivity_call ON connectivity_events(call_id);
CREATE TABLE IF NOT EXISTS user_attempts(
 event_id INTEGER PRIMARY KEY REFERENCES events(id), import_id INTEGER NOT NULL REFERENCES imports(id),
 ts TEXT NOT NULL, target TEXT NOT NULL, reason TEXT NOT NULL,
 reason_event_id INTEGER REFERENCES events(id));
CREATE INDEX IF NOT EXISTS attempt_time ON user_attempts(ts);
'''


def signals(text, filename):
    """Whitelist formats and file families. Return states, never raw log payloads."""
    name = filename.replace('\\', '/').rsplit('/', 1)[-1].lower()
    h = text.split('\n', 1)[0]
    if name.startswith('vdklog'):
        for marker, state, reason in (
            ('Network UP for both pingers', 'up', 'Entrambi i probe STUN rispondono'),
            ('Network DOWN for ONE pingers', 'transient', 'Un probe STUN non risponde'),
            ('Network DOWN for BOTH pingers', 'down', 'Entrambi i probe STUN non rispondono'),
            ('Stopping STUN pinger...', 'unknown', 'Probe STUN arrestati'),
            ('Starting STUN pinger...', 'transient', 'Avvio dei probe STUN')):
            if marker in h:
                yield 'stun', state, reason
                return
    if name in ('app.log', 'phoneengine.log') or name.startswith('application'):
        if 'Device is not connected to the network.' in h or re.search(r'\bNetwork (?:is )?lost\b', h):
            yield 'device', 'down', 'Il dispositivo segnala rete non disponibile'
        elif 'No network route' in text:
            yield 'device', 'down', 'Il sistema segnala assenza di una route di rete'
        elif 'Code=-1009' in h:
            yield 'device', 'transient', 'Richiesta fallita: sistema segnala offline (non prova universale)'
        elif re.search(r'\bNetwork (?:is )?available\b|connectivityState = UP', h):
            yield 'device', 'available', 'Interfaccia disponibile; accesso Internet non verificato'
        elif 'Current network interface:' in h:
            yield 'device', 'available', 'Interfaccia dichiarata; accesso Internet non verificato'
    if name.startswith('ctilib'):
        if any(x in h for x in ('login succeded!', 'We are still online!', 'Probe received!')):
            yield 'cti', 'up', 'Risposta ricevuta dal servizio CTI'
        elif 'The remote host closed the connection' in h:
            yield 'cti', 'down', 'Connessione CTI chiusa dal peer; causa non determinata'
        elif 'noACKtimeout' in h or 'ConnectionTimeout' in h:
            yield 'cti', 'down', 'Timeout del servizio CTI'
        elif 'Destroying CtiLib' in h:
            yield 'cti', 'unknown', 'CTI arrestato localmente'
    if name == 'phoneengine.log':
        if 'Kpe is unready... try later' in h:
            yield 'app', 'down', 'Avvio bloccato: KPE non pronto'
        match = re.search(r'KPE change state from: .*? to: (.+)$', h)
        if match:
            state = match[1].strip()
            yield 'app', ('up' if state == 'connected' else 'transient' if state in ('connecting', 'disconnecting') else 'down'), 'Stato KPE: ' + state[:100]
    if name.startswith('resip') and ('Broken pipe' in h or 'SSL_read error' in h):
        yield 'sip', 'down', 'Errore di trasporto SIP/TLS; non prova rete generale down'
    if name.startswith('sip_debug'):
        # Only actual incoming responses; headers/auth bodies must never become patterns.
        if 'INCOMING SIP message:' not in h:
            return
        match = re.search(r'^\s*SIP/2\.0 (\d{3}) ([^\n]*)', text, re.M)
        cseq = re.search(r'^\s*CSeq:\s*\d+\s+(\w+)', text, re.M | re.I)
        if match and cseq:
            code = int(match[1]); method = cseq[1].upper()
            # A rejection still demonstrates SIP reachability.
            yield 'sip', 'up', f'SIP {code} ({method}): risposta ricevuta' + ('; richiesta rifiutata' if code >= 400 and code not in (401, 407) else '')


def enrich(db, iid):
    marker = f'connectivity:{iid}'
    if db.execute('SELECT 1 FROM meta WHERE key=? AND value=?', (marker, VERSION)).fetchone():
        return
    # One scan of small signaling/application files, never periodic media blocks.
    files = db.execute('SELECT id,name FROM files WHERE import_id=?', (iid,)).fetchall()
    for file in files:
        name = file['name'].replace('\\', '/').rsplit('/', 1)[-1].lower()
        if not (name.startswith(('vdklog', 'ctilib', 'resip', 'sip_debug', 'application')) or name in ('app.log', 'phoneengine.log')):
            continue
        pending = None
        for e in db.execute('SELECT id,ts,text,call_id FROM events WHERE file_id=? ORDER BY line_no,id', (file['id'],)):
            if not e['ts']:
                continue
            from .transients import observed_timestamp
            ts, _ = observed_timestamp(e['text'], e['ts'])
            for layer, state, reason in signals(e['text'], name):
                cid = e['call_id']
                if name.startswith('sip_debug'):
                    match = re.search(r'^\s*Call-ID:\s*(\S+)', e['text'], re.M | re.I)
                    call = db.execute('SELECT id FROM calls WHERE sip_call_id=?', (match[1],)).fetchone() if match else None
                    cid = call[0] if call else None
                db.execute('INSERT OR IGNORE INTO connectivity_events VALUES(?,?,?,?,?,?,?)', (e['id'], layer, iid, ts, state, reason, cid))
            if name != 'app.log':
                continue
            h = e['text'].split('\n', 1)[0]
            match = re.search(r': Calling number:\s*(\S[^\r\n]*)$', h)
            if match:
                pending = (e['id'], ts)
                db.execute('INSERT OR IGNORE INTO user_attempts VALUES(?,?,?,?,?,NULL)', (e['id'], iid, ts, match[1][:256], 'Richiesta utente; esito SIP non correlato automaticamente'))
            elif 'KPE is not ready yet... the call cannot be established' in h:
                # Pair only the immediately preceding explicit request in this file,
                # within one second. Never merge two calls by number or time overlap.
                if pending and 0 <= (datetime.fromisoformat(ts) - datetime.fromisoformat(pending[1])).total_seconds() <= 1:
                    db.execute('UPDATE user_attempts SET reason=?,reason_event_id=? WHERE event_id=?', ('Avvio bloccato: KPE non pronto (prima del SIP)', e['id'], pending[0]))
                else:
                    db.execute('INSERT OR IGNORE INTO user_attempts VALUES(?,?,?,?,?,?)', (e['id'], iid, ts, '', 'Avvio bloccato: KPE non pronto; richiesta precedente non disponibile', e['id']))
                pending = None
            else:
                pending = None
    # Explicit positive interval reception only: an unchanged cumulative counter
    # or an audio heartbeat is not evidence of packets arriving from the network.
    for m in db.execute('''SELECT m.event_id,m.ts,m.call_id FROM metrics m
        JOIN events e ON e.id=m.event_id WHERE e.import_id=?
        AND m.name='rtcp.packets_received_interval' AND m.valid=1 AND m.value>0''', (iid,)):
        db.execute('INSERT OR IGNORE INTO connectivity_events VALUES(?,?,?,?,?,?,?)',
                   (m['event_id'],'media',iid,m['ts'],'up','Ricezione di pacchetti riportata nell’intervallo; non prova SIP/CTI',m['call_id']))
    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (marker, VERSION))


def pending(db):
    with db:
        for r in db.execute('SELECT id FROM imports').fetchall():
            enrich(db, r[0])


def attempts(db, search=''):
    return [dict(r, id=-r['event_id'], caller='', callee=r['target'], start=r['ts'], end=None,
                 connected=None, sip_call_id=None, perspectives=0, metrics=0, mos={},
                 row_type='user_attempt', status='blocked' if r['reason_event_id'] else 'requested')
            for r in db.execute('''WITH base AS (
              SELECT a.*,f.name filename,e.line_no,i.label,e.text request_text,
                CASE WHEN p.status='resolved' AND p.producer_key IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM observation_roles o JOIN perspectives v ON v.id=o.perspective_id
                    WHERE v.import_id=a.import_id AND o.role!=p.role)
                  THEN p.producer_key ELSE 'import:'||a.import_id END source_key
              FROM user_attempts a JOIN events e ON e.id=a.event_id JOIN files f ON f.id=e.file_id
              JOIN imports i ON i.id=a.import_id LEFT JOIN import_producers p ON p.import_id=a.import_id
            ), numbered AS (
              SELECT *,ROW_NUMBER() OVER(PARTITION BY source_key,import_id,request_text ORDER BY event_id) occurrence
              FROM base
            ), ranked AS (
              SELECT *,ROW_NUMBER() OVER(PARTITION BY source_key,request_text,occurrence ORDER BY import_id DESC,event_id DESC) rank,
                COUNT(*) OVER(PARTITION BY source_key,request_text,occurrence) copies FROM numbered
            ) SELECT event_id,import_id,ts,target,reason,reason_event_id,filename,line_no,label,copies FROM ranked
            WHERE rank=1 AND (target LIKE ? OR reason LIKE ?)
            ORDER BY ts DESC,event_id DESC LIMIT 2000''', ('%'+search+'%',)*2)]


def reasons(db, calls):
    if not calls:
        return
    ids = [c['id'] for c in calls]
    found = {}
    for r in db.execute(f'''SELECT n.call_id,n.reason,n.event_id,f.name filename,e.line_no
        FROM connectivity_events n JOIN events e ON e.id=n.event_id JOIN files f ON f.id=e.file_id
        WHERE n.call_id IN ({','.join('?' for _ in ids)}) AND n.reason LIKE '%richiesta rifiutata%'
        ORDER BY n.ts,n.event_id''', ids):
        found.setdefault(r['call_id'], dict(r))
    for c in calls:
        item = found.get(c['id'])
        c['row_type'] = 'sip_call'
        c['reason'] = item['reason'] if item else ('Esito non determinato dai log' if not c['connected'] else '')
        c['reason_evidence'] = item


def iso(t):
    return t.isoformat(' ', timespec='microseconds')


def timeline(db, iid, start, end, call_id=None, perspective_id=None):
    """Exact-time segments, queryable at any second; observations expire after 30 s."""
    start, end = datetime.fromisoformat(start), datetime.fromisoformat(end)
    if start.tzinfo or end.tzinfo or end <= start or (end-start).total_seconds() > 86400:
        raise ValueError('Periodo rete: da >0 secondi a 24 ore, orari originali senza fuso')
    source = db.execute('SELECT label,clock_offset FROM imports WHERE id=?', (iid,)).fetchone()
    if not source:
        raise ValueError('Sorgente non trovata')
    data = [dict(r) for r in db.execute('''SELECT n.*,f.name filename,e.line_no FROM connectivity_events n
        JOIN events e ON e.id=n.event_id JOIN files f ON f.id=e.file_id
        WHERE n.import_id=? AND n.ts>=? AND n.ts<? ORDER BY n.ts,n.event_id LIMIT 50001''',
        (iid, iso(start-timedelta(seconds=TTL)), iso(end)))]
    if len(data) > 50000:
        raise ValueError('Troppe evidenze: restringere il periodo rete')
    changes = {}
    for r in data:
        t = datetime.fromisoformat(r['ts']); r['until'] = t + timedelta(seconds=TTL)
        changes.setdefault(t, []).append(r)
    boundaries = sorted({start, end, *[max(start, t) for t in changes],
                         *[min(end, r['until']) for r in data if r['until'] > start]})
    current = {}
    for t in sorted(t for t in changes if t < start):
        for r in changes[t]: current[r['layer']] = r
    lanes = {layer: [] for layer in LAYERS}
    evidence = {r['event_id']: {k: r[k] for k in ('event_id','ts','filename','line_no','layer','state','reason')} for r in data}
    for a, b in zip(boundaries, boundaries[1:]):
        for r in changes.get(a, []): current[r['layer']] = r
        states = {layer: r for layer, r in current.items() if r['until'] > a}
        positive = [r for layer,r in states.items() if layer in ('stun','cti','sip','media') and r['state']=='up']
        negative = [r for layer,r in states.items() if layer in ('device','stun') and r['state']=='down']
        uncertain = [r for layer,r in states.items() if layer in ('device','stun') and r['state'] in ('transient','available')]
        if positive and negative:
            net = ('transient', 'Evidenze discordanti: risposte ricevute e indisponibilità segnalata', positive+negative)
        elif negative:
            net = ('down', 'Indisponibilità osservata dal dispositivo/probe; non prova di ogni servizio', negative)
        elif positive:
            net = ('up', 'Raggiungibilità osservata verso almeno un servizio; non garantisce tutti i servizi', positive)
        elif uncertain:
            net = ('transient', 'Disponibilità parziale o accesso Internet non verificato', uncertain)
        else:
            net = ('unknown', 'Nessuna evidenza recente di raggiungibilità', [])
        for layer in LAYERS:
            r = states.get(layer)
            state, reason, inputs = net if layer=='network' else ((r['state'], r['reason'], [r]) if r else ('unknown','Nessuna evidenza negli ultimi 30 secondi',[]))
            ids = sorted(x['event_id'] for x in inputs)
            segment = dict(start=iso(a), end=iso(b), state=state, reason=reason, evidence=ids)
            previous = lanes[layer][-1] if lanes[layer] else None
            if previous and all(previous[k] == segment[k] for k in ('state','reason','evidence')):
                previous['end'] = segment['end']
            else:
                lanes[layer].append(segment)
    from .network_switches import collect
    switches=collect(db,import_id=iid,start=iso(start),end=iso(end),call_id=call_id,perspective_id=perspective_id)
    return dict(import_id=iid, label=source['label'], clock_offset=source['clock_offset'], start=iso(start), end=iso(end),
                ttl_seconds=TTL, lanes=lanes, evidence=evidence,network_switches=switches)


def for_calls(db, ids):
    if not ids or len(ids)>20 or any(i<=0 for i in ids):
        raise ValueError('Selezionare da 1 a 20 chiamate SIP')
    result=[]
    for p in db.execute(f'''SELECT * FROM perspectives WHERE call_id IN ({','.join('?' for _ in ids)})
        AND id NOT IN (SELECT perspective_id FROM effective_duplicates) ORDER BY id''', ids):
        from .call_events import bounded
        p=bounded(db,p)
        end = p['end'] or db.execute('SELECT MAX(ts) FROM events INDEXED BY event_call_ts WHERE import_id=? AND call_id=?',(p['import_id'],p['call_id'])).fetchone()[0]
        if not p['start'] or not end or end <= p['start']:
            continue
        if len(result)>=40:
            raise ValueError('Troppe prospettive: restringere la selezione')
        result.append(dict(timeline(db,p['import_id'],p['start'],end,call_id=p['call_id'],perspective_id=p['id']), perspective_id=p['id'],call_id=p['call_id']))
    return result
