"""Evidence-driven parsers for the iOS KPE export format. No vendor SDK required."""
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import datetime
from pathlib import PurePosixPath

PARSER_VERSION = '1.10.0'
MAX_ZIP = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_FILE = 40 * 1024 * 1024
STAMP = re.compile(r'^\[?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)')
RESIP_STAMP = re.compile(r'^\w+\s*\|\s*(\d{8}-\d{6}\.\d+)')
LINE = re.compile(r'(?:lineId\s*\[\s*|lineId\s+|line id:\s*|line\s*\(\s*|\bline\s+)(\d+)', re.I)
LEVEL = re.compile(r'\[(DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|FATAL)\]', re.I)


def timestamp(text):
    m = STAMP.match(text)
    if not m:
        other = RESIP_STAMP.match(text)
        if other:
            try:
                return datetime.strptime(other[1], '%Y%m%d-%H%M%S.%f').isoformat(' ', timespec='microseconds')
            except ValueError:
                pass
        return None
    try:
        return datetime.fromisoformat(m[1]).isoformat(' ', timespec='microseconds')
    except ValueError:
        return None


def delta(a, b):
    return (datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()


def records(text):
    # CRCRLF exists in the supplied SIP export; normalize it as one logical newline.
    lines = re.sub(r'\r+\n', '\n', text).replace('\r', '\n').splitlines()
    start, buf, ts = 1, [], None
    for n, line in enumerate(lines, 1):
        current = timestamp(line)
        if current:
            if buf:
                yield start, ts, '\n'.join(buf)
            start, buf, ts = n, [], current
        buf.append(line)
    if buf:
        yield start, ts, '\n'.join(buf)


def json_body(text):
    try:
        return json.JSONDecoder().raw_decode(text[text.index('{'):])[0]
    except (ValueError, json.JSONDecodeError):
        return None


def sip(text):
    if 'SIP message:' not in text:
        return None
    cid = re.search(r'^\s*(?:Call-ID|i):\s*(\S+)', text, re.M | re.I)
    seq = re.search(r'^\s*CSeq:\s*\d+\s+(\w+)', text, re.M | re.I)
    first = re.search(r'^\s*(SIP/2.0 \d{3}[^\n]*|[A-Z]+ sips?:[^\n]+ SIP/2.0)\s*$', text, re.M)
    if not cid or not seq or not first:
        return None
    def header(name):
        m = re.search(r'^\s*' + name + r':\s*([^\n]+)', text, re.M | re.I)
        return m[1].strip() if m else ''
    def identity(value):
        m = re.search(r'sips?:([^>;\s]+)', value)
        return m[1] if m else value
    m = re.match(r'SIP/2.0 (\d{3})', first[1])
    return dict(cid=cid[1], method=seq[1].upper(), response=int(m[1]) if m else None,
                title=first[1], caller=identity(header('From')), callee=identity(header('To')),
                direction='incoming' if 'INCOMING SIP' in text else 'outgoing')


def classify(name):
    base = PurePosixPath(name).name.lower()
    if base.startswith('telemetry') and base.endswith('.jsonl'):
        return 'telemetry'
    for prefix, kind in [('sip_debug', 'sip'), ('kpelog', 'kpe'), ('rtplog', 'rtcp'),
                         ('callinfo', 'callinfo'), ('phoneengine', 'phone'), ('vdlog', 'vd')]:
        if base.startswith(prefix):
            return kind
    return 'raw'


def metrics(record):
    """Yield name, value, unit, direction, flow, ssrc, statistic, valid."""
    text, kind = record['text'], record['parser']
    if kind in ('callinfo', 'kpe') and ('call flow metric line' in text or 'Info about first media flow finished' in text):
        body = json_body(text)
        if not isinstance(body, dict):
            return
        for direction in ('incoming', 'outgoing'):
            groups = body.get(direction, {})
            if not isinstance(groups, dict):
                continue
            for group, values in groups.items():
                if not isinstance(values, dict):
                    continue
                for name, stats in values.items():
                    if not isinstance(stats, dict):
                        continue
                    for stat, raw in stats.items():
                        try:
                            value = float(raw)
                        except (TypeError, ValueError):
                            continue
                        if math.isfinite(value):
                            # Unknown units deliberately remain raw until vendor documentation confirms them.
                            yield f'kpe.{group}.{name}', value, ('packets' if name.startswith('rtp_pkt') else 'raw'), direction, '0', '', stat, int(value >= 0)
    if kind == 'rtcp' and 'RTCP ARRIVED' in text:
        flow = re.search(r'FLOW\s+(\d+)', text)
        ssrc = re.search(r'SSRC of this source:\s*(\w+)', text)
        patterns = [
            ('rtcp.loss', r'Packet loss we perceive from this source \(since last report\):\s*([-\d.]+)%', '%', 'incoming'),
            ('rtcp.jitter', r'Jitter we perceive from this source \(since last report\):\s*([-\d.]+) ms', 'ms', 'incoming'),
            ('rtcp.rtt', r'RTT to this source:\s*([-\d.]+) ms', 'ms', 'roundtrip'),
            ('rtcp.loss', r'Receiver Report - remote peer pkt loss \(since last RR\):\s*([-\d.]+)%', '%', 'outgoing'),
            ('rtcp.jitter', r'Receiver Report - jitter perceived by this remote peer\(since last report\):\s*([-\d.]+) ms', 'ms', 'outgoing'),
            ('rtcp.packets_received', r'Packet we received from this source \(total\):\s*(\d+)', 'packets', 'incoming'),
        ]
        for name, pattern, unit, direction in patterns:
            m = re.search(pattern, text)
            if m:
                value = float(m[1])
                if math.isfinite(value):
                    yield name, value, unit, direction, flow[1] if flow else '?', ssrc[1] if ssrc else '', 'sample', int(value >= 0 and (unit != '%' or value <= 100))
    if kind == 'callinfo':
        m = re.search(r'received \d+ bytes .*?time=([\d.]+) ms', text)
        if m:
            yield 'network.ping', float(m[1]), 'ms', 'roundtrip', 'probe', '', 'sample', 1


def read_zip(data):
    if len(data) > MAX_ZIP:
        raise ValueError('ZIP oltre il limite di 64 MiB')
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError('Il file non è uno ZIP valido') from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > 200 or sum(i.file_size for i in infos) > MAX_EXPANDED:
            raise ValueError('Archivio oltre i limiti: 200 file / 256 MiB decompressi')
        result, warnings, names = [], [], set()
        for info in infos:
            name = info.filename.replace('\\', '/')
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or ':' in name or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Percorso ZIP non sicuro')
            if name in names:
                raise ValueError('Nomi duplicati nello ZIP')
            names.add(name)
            if info.is_dir():
                continue
            if info.flag_bits & 1 or info.file_size > MAX_FILE:
                raise ValueError('File cifrato o oltre 40 MiB')
            if not name.lower().endswith(('.txt', '.log', '.old')) and classify(name) != 'telemetry':
                warnings.append(f'Ignorato file non testuale: {name}')
                continue
            try:
                with archive.open(info) as stream:
                    raw = stream.read(MAX_FILE + 1)
            except (RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
                raise ValueError(f'File ZIP non leggibile: {name}') from exc
            if len(raw) > MAX_FILE:
                raise ValueError('File oltre 40 MiB')
            text = raw.decode('utf-8-sig', errors='replace')
            if '\ufffd' in text:
                warnings.append(f'UTF-8 non valido sostituito in {name}')
            result.append((name, len(raw), text))
    if not result:
        raise ValueError('Nessun file di log supportato nello ZIP')
    return result, warnings


def ingest(db, data, name, label=''):
    digest = hashlib.sha256(data).hexdigest()
    existing = db.execute('SELECT id FROM imports WHERE sha256=?', (digest,)).fetchone()
    if existing:
        return dict(id=existing[0], duplicate=True)
    files, warnings = read_zip(data)
    with db:
        iid = db.execute('INSERT INTO imports(name,sha256,label) VALUES(?,?,?)', (name, digest, label or name)).lastrowid
        all_records = []
        for filename, size, text in files:
            parser = classify(filename)
            fid = db.execute('INSERT INTO files(import_id,name,size,parser) VALUES(?,?,?,?)', (iid, filename, size, parser)).lastrowid
            rs = []
            if parser == 'telemetry':
                from .telemetry import records as telemetry_records
                invalid = 0
                for line_no, ts, body, event, errors in telemetry_records(text):
                    invalid += bool(errors)
                    rs.append(dict(file=fid, line_no=line_no, ts=ts, text=body, parser=parser,
                                   line=None, level='', sip=None, telemetry=event, errors=errors))
                if invalid:
                    warnings.append(f'{filename}: {invalid} record di telemetria non conformi conservati; '
                                    'verificare con python -m app.telemetry')
                dated = [r['ts'] for r in rs if r['ts']]
                db.execute('UPDATE files SET first_ts=?,last_ts=?,records=? WHERE id=?',
                           (min(dated) if dated else None, max(dated) if dated else None, len(rs), fid))
                all_records.extend(rs)
                continue
            for line_no, ts, body in records(text):
                level = LEVEL.search(body.split('\n', 1)[0])
                lm = LINE.search(body.split('\n', 1)[0])
                if not lm and parser == 'phone':
                    lm = re.search(r'"lineId"\s*:\s*(\d+)', body.split('\n', 1)[0])
                s = sip(body) if parser == 'sip' else None
                r = dict(file=fid, line_no=line_no, ts=ts, text=body, parser=parser,
                         line=int(lm[1]) if lm else None, level=level[1].upper() if level else (body.split('|')[0].strip() if RESIP_STAMP.match(body) else ''), sip=s)
                rs.append(r)
            dated = [r['ts'] for r in rs if r['ts']]
            db.execute('UPDATE files SET first_ts=?,last_ts=?,records=? WHERE id=?', (min(dated) if dated else None, max(dated) if dated else None, len(rs), fid))
            if rs and rs[0]['ts'] is None:
                warnings.append(f'{filename}: frammento iniziale senza timestamp, conservato senza attribuzione')
            all_records.extend(rs)
        seen = set()
        for r in all_records:
            signature = (r['parser'], r['ts'], hashlib.sha256(r['text'].encode()).digest())
            r['duplicate'] = signature in seen
            seen.add(signature)
        ordered = sorted((r for r in all_records if r['ts'] and not r['duplicate'] and r['parser'] != 'telemetry'), key=lambda r: r['ts'])
        sip_calls = {}
        for r in ordered:
            s = r['sip']
            if s and s['method'] in ('INVITE', 'ACK', 'BYE', 'CANCEL', 'REFER', 'PRACK', 'UPDATE'):
                sip_calls.setdefault(s['cid'], []).append(r)
        legs, active = [], {}
        for r in ordered:
            if r['parser'] != 'kpe' or r['line'] is None:
                continue
            line, text = r['line'], r['text']
            if 'added to the call list' in text:
                leg = dict(line=line, start=r['ts'], end=None, connected=None, cid=None, summary=None)
                if line in active:
                    # A reused line must never make an older incomplete leg swallow later metrics.
                    active[line]['end'] = r['ts']
                    active[line]['incomplete'] = True
                active[line] = leg
                legs.append(leg)
            elif 'Call status changed to 1' in text and line in active:
                active[line]['connected'] = r['ts']
            elif ('removed from list' in text or 'Send socket event for call terminated' in text) and line in active:
                active[line]['end'] = r['ts']
            elif 'Info about call finished on line' in text:
                body = json_body(text)
                info = body.get('callInfo', {}) if isinstance(body, dict) else {}
                cid = info.get('call-id') if isinstance(info, dict) else None
                if not isinstance(cid, str) or not cid:
                    warnings.append(f"Riepilogo KPE incompleto: file {r['file']} riga {r['line_no']}")
                    continue
                leg = active.pop(line, None)
                if leg is None:
                    matches = sip_calls.get(cid, [])
                    leg = dict(line=line, start=matches[0]['ts'] if matches else r['ts'], connected=None)
                    legs.append(leg)
                leg.update(end=r['ts'], cid=cid, summary=info)
        # A SIP Call-ID is the only automatic cross-archive correlation key.
        mapped = {leg.get('cid') for leg in legs if leg.get('cid')}
        for cid, rs in sip_calls.items():
            if cid not in mapped:
                legs.append(dict(line=None, start=rs[0]['ts'], end=None, connected=None, cid=cid, summary=None))
        # CallInfo can recover line windows when KPE rotations are absent.
        ci_active = {}
        for r in ordered:
            if r['parser'] != 'callinfo' or r['line'] is None:
                continue
            if 'connected line id:' in r['text']:
                if not any(l['line'] == r['line'] and l['start'] <= r['ts'] and (not l.get('end') or l['end'] >= r['ts']) for l in legs):
                    leg = dict(line=r['line'], start=r['ts'], end=None, connected=r['ts'], cid=None, summary=None)
                    legs.append(leg)
                    ci_active[r['line']] = leg
            elif 'terminated line id:' in r['text'] and r['line'] in ci_active:
                ci_active.pop(r['line'])['end'] = r['ts']
        by_cid = {}
        for ix, leg in enumerate(legs):
            cid = leg.get('cid')
            rs = sip_calls.get(cid, [])
            if rs:
                leg['start'] = min(leg['start'], rs[0]['ts'])
            connected = [r['ts'] for r in rs if r['sip']['method'] == 'INVITE' and r['sip']['response'] is not None and 200 <= r['sip']['response'] < 300]
            if connected:
                leg['connected'] = min(connected + ([leg['connected']] if leg.get('connected') else []))
            terminated = [r['ts'] for r in rs if r['sip']['method'] in ('BYE', 'CANCEL')]
            failures = [r for r in rs if r['sip']['method'] == 'INVITE' and (r['sip']['response'] or 0) >= 400 and r['sip']['response'] not in (401,407)]
            if not leg.get('end') and terminated:
                leg['end'] = max(terminated)
            if not leg.get('end') and failures and not leg.get('connected'):
                leg['end'] = failures[-1]['ts']
            info = leg.get('summary') or (rs[0]['sip'] if rs else {})
            key = 'sip:' + cid if cid else f'local:{digest}:{ix}'
            db.execute('INSERT OR IGNORE INTO calls(call_key,sip_call_id,caller,callee,start,end,connected) VALUES(?,?,?,?,?,?,?)',
                       (key, cid, str(info.get('caller','')), str(info.get('callee','')), leg['start'], leg.get('end'), leg.get('connected')))
            call_id = db.execute('SELECT id FROM calls WHERE call_key=?', (key,)).fetchone()[0]
            # Repeated summaries can occur after rotations; keep one perspective per source/call.
            existing_leg = db.execute('SELECT id FROM perspectives WHERE call_id=? AND import_id=?', (call_id, iid)).fetchone()
            direction = next((r['sip']['direction'] for r in rs if r['sip']['method']=='INVITE' and r['sip']['response'] is None), 'unknown')
            status = 'completed' if leg.get('connected') and leg.get('end') and not leg.get('incomplete') else ('connected / partial' if leg.get('connected') else ('failed' if failures else 'partial'))
            evidence = 'KPE summary + line window' if leg.get('summary') else ('SIP Call-ID' if cid else 'Local line window; no SIP identity')
            pid = existing_leg[0] if existing_leg else db.execute('INSERT INTO perspectives(call_id,import_id,line_id,start,end,connected,direction,status,evidence) VALUES(?,?,?,?,?,?,?,?,?)',
                (call_id,iid,leg['line'],leg['start'],leg.get('end'),leg.get('connected'),direction,status,evidence)).lastrowid
            leg.update(call_id=call_id, pid=pid)
            if cid:
                by_cid[cid] = leg
            db.execute('UPDATE calls SET start=(SELECT MIN(start) FROM perspectives WHERE call_id=?),end=(SELECT MAX(end) FROM perspectives WHERE call_id=?),connected=(SELECT MIN(connected) FROM perspectives WHERE call_id=?) WHERE id=?', (call_id,call_id,call_id,call_id))
        counts = dict(metrics=0, unassigned_metrics=0, invalid_metrics=0)
        for r in all_records:
            if r['parser'] == 'telemetry':
                event = r['telemetry']
                kind = 'telemetry.invalid'
                leg = None
                if not r['errors']:
                    kind = 'telemetry.' + event['type'] + '.' + event['validity']
                    cid = event['payload'].get('stream', {}).get('sip_call_id')
                    leg = by_cid.get(cid) if cid else None
                db.execute('INSERT INTO events(import_id,file_id,line_no,ts,level,kind,text,call_id,perspective_id) VALUES(?,?,?,?,?,?,?,?,?)',
                           (iid,r['file'],r['line_no'],r['ts'],'',kind,r['text'],
                            leg['call_id'] if leg else None,leg['pid'] if leg else None))
                continue
            leg = by_cid.get(r['sip']['cid']) if r['sip'] else None
            if not leg:
                explicit = re.search(r'^\s*Call-ID:\s*(\S+)', r['text'], re.M | re.I)
                if explicit:
                    leg = by_cid.get(explicit[1])
            if not leg and r['ts'] and r['line'] is not None:
                candidates = [l for l in legs if l['line'] == r['line'] and l['start'] <= r['ts'] and (not l.get('end') or delta(r['ts'],l['end']) <= 0.25)]
                # Only assign when unambiguous. Overlapping/reused line boundaries stay unassigned.
                if len(candidates) == 1:
                    leg = candidates[0]
            if not leg and r['ts'] and r['parser'] == 'callinfo' and r['line'] is None:
                candidates = [l for l in legs if l['start'] <= r['ts'] and l.get('end') and r['ts'] <= l['end']]
                if len(candidates) == 1:
                    leg = candidates[0]
            kind = 'sip' if r['sip'] else ('metric' if 'call flow metric line' in r['text'] or 'RTCP ARRIVED' in r['text'] else r['parser'])
            eid = db.execute('INSERT INTO events(import_id,file_id,line_no,ts,level,kind,text,call_id,perspective_id,line_id) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (iid,r['file'],r['line_no'],r['ts'],r['level'],kind,r['text'],leg['call_id'] if leg else None,leg['pid'] if leg else None,r['line'])).lastrowid
            if r['ts'] and not r['duplicate']:
                for name_m, value, unit, direction, flow, ssrc, statistic, valid in metrics(r):
                    db.execute('INSERT INTO metrics(event_id,perspective_id,call_id,ts,name,value,unit,direction,flow,ssrc,statistic,valid) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (eid,leg['pid'] if leg else None,leg['call_id'] if leg else None,r['ts'],name_m,value,unit,direction,flow,ssrc,statistic,valid))
                    counts['metrics'] += 1
                    counts['unassigned_metrics'] += not bool(leg)
                    counts['invalid_metrics'] += not valid
        from .enrichment import enrich_import
        enrich_import(db, iid)
        from .geography import enrich as enrich_geo
        enrich_geo(db, iid)
        from .mobility import enrich as enrich_mobility
        enrich_mobility(db, iid)
        from .telemetry_store import ingest as ingest_telemetry
        ingest_telemetry(db, iid)
        totals = db.execute('''SELECT COUNT(*),COALESCE(SUM(m.call_id IS NULL),0),COALESCE(SUM(m.valid=0),0)
            FROM metrics m JOIN events e ON e.id=m.event_id WHERE e.import_id=?''', (iid,)).fetchone()
        counts.update(zip(('metrics', 'unassigned_metrics', 'invalid_metrics'), totals))
        if counts['unassigned_metrics']:
            warnings.append(f"{counts['unassigned_metrics']} metriche senza una chiamata attribuibile con certezza")
        if counts['invalid_metrics']:
            warnings.append(f"{counts['invalid_metrics']} valori anomali conservati, esclusi dai grafici per impostazione predefinita")
        db.execute('UPDATE imports SET file_count=?,event_count=?,warnings=? WHERE id=?', (len(files),len(all_records),json.dumps(warnings),iid))
    call_count = db.execute('SELECT count(*) FROM perspectives WHERE import_id=?', (iid,)).fetchone()[0]
    return dict(id=iid, duplicate=False, calls=call_count, events=len(all_records), warnings=warnings, parser_version=PARSER_VERSION, **counts)
