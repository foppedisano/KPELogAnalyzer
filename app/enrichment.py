"""Versioned, idempotent enrichment of stored evidence; never rebuild call IDs."""
import math
import re
from datetime import datetime

VERSION = 'vd-1'
NUM = r'(-?\d+(?:\.\d+)?)'
NART = re.compile(r'NART(\d+) of Line (\d+)', re.I)


def observations(text, filename):
    """Yield normalized observations with exact offsets within the parent event."""
    device = None
    vd = filename.rsplit('/', 1)[-1].lower().startswith('vdlog')
    rtp = filename.rsplit('/', 1)[-1].lower().startswith('rtplog')
    header = text.split('\n', 1)[0]
    if vd:
        device = NART.search(header)
    for offset, line in enumerate(text.splitlines()):
        if 'Device name:' in line:
            device = NART.search(line)  # Other devices explicitly end NART scope.
        matches = []
        if vd and device:
            patterns = [
                ('vd.buffer', r'buffer len in usecs:\s*' + NUM, 'us', .001, 'gauge'),
                ('vd.buffer', r'Audio currently in buffer \(ms\):\s*' + NUM, 'ms', 1, 'gauge'),
                ('vd.dejitter_target', r'ring current max buffer usecs\s*\(for dynamic dejittering\):\s*' + NUM, 'us', .001, 'gauge'),
                ('vd.silence_skipped', r'silence usecs skipped so far:\s*' + NUM, 'us', .001, 'counter'),
                ('vd.silence_skipped', r'silence msecs skipped so far:\s*' + NUM, 'ms', 1, 'counter'),
                ('vd.max_arrival_delay', r'm_maxPktArrivalTimeDelay\s+to ms\s*' + NUM, 'ms', 1, 'event'),
                ('vd.max_arrival_delay', r'm_maxPktArrivalTimeDelay\s*(?:\(ms\)|in ms|ms)\s*[:=]\s*' + NUM, 'ms', 1, 'gauge'),
                ('vd.max_arrival_delay', r'm_maxPktArrivalTimeDelay\s*[:=]\s*' + NUM + r'\s*ms\b', 'ms', 1, 'gauge'),
            ]
            for name, pattern, unit, factor, kind in patterns:
                found = re.search(pattern, line, re.I)
                if found:
                    matches.append((name, found, unit, factor, kind))
        if rtp:
            found = re.search(r'RTT by this source:\s*' + NUM + r'\s*microseconds', line, re.I)
            if found:
                matches.append(('rtcp.rtt', found, 'us', .001, 'sample'))
        for name, found, unit, factor, kind in matches:
            raw = float(found[1])
            if not math.isfinite(raw):
                continue
            lm = re.search(r'LINE\s+(\d+)', header, re.I)
            flow = re.search(r'FLOW\s+(\d+)', header, re.I)
            ssrc = re.search(r'SSRC of this source:\s*(\w+)', text)
            yield dict(name=name, value=raw * factor, raw_value=raw, raw_unit=unit,
                       unit='ms', sample_kind=kind, source_offset=offset, valid=int(raw >= 0),
                       device=device[0] if device else '', line_id=int(device[2]) if device else (int(lm[1]) if lm else None),
                       flow=device[1] if device else (flow[1] if flow else '?'), ssrc=ssrc[1] if ssrc else '',
                       direction='incoming' if vd else 'roundtrip')


def enrich_import(db, iid):
    perspectives = [dict(p) for p in db.execute('SELECT * FROM perspectives WHERE import_id=?', (iid,))]
    seen = set()
    added = 0
    for row in db.execute('''SELECT e.*, f.name filename FROM events e JOIN files f ON f.id=e.file_id
        WHERE e.import_id=? AND e.ts IS NOT NULL AND f.parser!='telemetry' AND (lower(f.name) LIKE '%vdlog%' OR lower(f.name) LIKE '%rtplog%' OR lower(f.name) LIKE '%phoneengine%') ORDER BY e.ts,e.id''', (iid,)):
        e = dict(row)
        version = re.search(r'KPE setAppInfo configured with name=([^,\n]+), version=([^\s,]+)', e['text'])
        if version:
            db.execute('INSERT OR IGNORE INTO app_versions VALUES(?,?,?,?,?)', (e['id'], iid, e['ts'], version[1], version[2]))
        for m in observations(e['text'], e['filename']):
            signature = (e['ts'], m['name'], m['device'], m['line_id'], m['flow'], m['ssrc'], m['value'], m['sample_kind'])
            if signature in seen:
                continue
            seen.add(signature)
            candidates = [p for p in perspectives if m['line_id'] is not None and p['line_id'] == m['line_id'] and p['start'] <= e['ts'] and
                          (not p['end'] or (datetime.fromisoformat(e['ts']) - datetime.fromisoformat(p['end'])).total_seconds() <= .25)]
            p = candidates[0] if len(candidates) == 1 else None
            db.execute('''INSERT INTO metrics(event_id,perspective_id,call_id,ts,name,value,unit,direction,flow,ssrc,statistic,valid,device,source_line,raw_value,raw_unit,sample_kind,extractor)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (e['id'], p['id'] if p else None, p['call_id'] if p else None, e['ts'], m['name'], m['value'], m['unit'], m['direction'], m['flow'], m['ssrc'], 'sample', m['valid'], m['device'], e['line_no'] + m['source_offset'], m['raw_value'], m['raw_unit'], m['sample_kind'], VERSION))
            added += 1
    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (f'enrichment:{iid}', VERSION))
    from .missing_packets import enrich
    enrich(db,iid)
    from .conversation_discovery import enrich as discover
    discover(db,iid)
    return added


def enrich_pending(db):
    ids = [r[0] for r in db.execute('SELECT id FROM imports')]
    with db:
        for iid in ids:
            from .missing_packets import enrich
            enrich(db,iid)
            from .conversation_discovery import enrich as discover
            discover(db,iid)
            marker = db.execute('SELECT value FROM meta WHERE key=?', (f'enrichment:{iid}',)).fetchone()
            if not marker or marker[0] != VERSION:
                enrich_import(db, iid)
