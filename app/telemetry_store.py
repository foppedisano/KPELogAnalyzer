"""Canonical raw telemetry and conservative, evidence-linked interval derivations."""
import hashlib
import json
import struct
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .telemetry import decode
from .db import rows

VERSION = 'telemetry-2'
LIMIT = 100000
SCHEMA = '''
CREATE TABLE IF NOT EXISTS telemetry_records(
 id INTEGER PRIMARY KEY,source_id TEXT NOT NULL,event_key TEXT NOT NULL,
 event_id INTEGER NOT NULL REFERENCES events(id),body TEXT NOT NULL,
 conflict INTEGER NOT NULL DEFAULT 0,issues TEXT NOT NULL DEFAULT '[]',
 UNIQUE(source_id,event_key));
CREATE TABLE IF NOT EXISTS telemetry_evidence(
 record_id INTEGER NOT NULL REFERENCES telemetry_records(id),event_id INTEGER NOT NULL REFERENCES events(id),
 PRIMARY KEY(record_id,event_id));
CREATE TABLE IF NOT EXISTS telemetry_intervals(
 metric_id INTEGER PRIMARY KEY REFERENCES metrics(id),record_id INTEGER NOT NULL REFERENCES telemetry_records(id),
 previous_record_id INTEGER REFERENCES telemetry_records(id),start TEXT NOT NULL,end TEXT NOT NULL,
 role TEXT NOT NULL,context TEXT NOT NULL,refs TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS telemetry_geo_context(
 observation_id INTEGER PRIMARY KEY REFERENCES geo_mos(id),context TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS telemetry_interval_record ON telemetry_intervals(record_id);
'''


def stamp(event, mono):
    """UTC display coordinate; original UTC + monotonic values stay in raw evidence."""
    return (datetime.fromisoformat(event['observed_utc']).astimezone(timezone.utc).replace(tzinfo=None)
            + timedelta(milliseconds=mono-event['mono_ms'])).isoformat(' ', timespec='microseconds')


def issue(r, reason):
    if reason not in r['issues']:
        r['issues'].append(reason)


def reports(hex_value):
    """Parse compound SR/RR, validating packet framing before returning any blocks."""
    data = bytes.fromhex(hex_value)
    offset = 0
    out = []
    while offset < len(data):
        if len(data)-offset < 4:
            raise ValueError('rtcp_truncated')
        first, kind, length = struct.unpack_from('!BBH', data, offset)
        size = (length+1)*4
        if first >> 6 != 2 or size < 4 or offset+size > len(data):
            raise ValueError('rtcp_framing')
        packet = data[offset:offset+size]
        if first & 32:
            pad = packet[-1]
            if offset+size != len(data) or pad == 0 or pad > size-4:
                raise ValueError('rtcp_padding')
            packet = packet[:-pad]
        count = first & 31
        base = 28 if kind == 200 else 8
        if kind in (200, 201):
            if len(packet) < base+24*count:
                raise ValueError('rtcp_report_truncated')
            reporter = int.from_bytes(packet[4:8], 'big')
            for i in range(count):
                block = packet[base+24*i:base+24*(i+1)]
                out.append(dict(reporter=reporter, ssrc=int.from_bytes(block[:4], 'big'),
                                lost=int.from_bytes(block[5:8], 'big', signed=True),
                                highest=int.from_bytes(block[8:12], 'big')))
        offset += size
    return out


def ingest(db, iid):
    marker = f'{VERSION}:{iid}'
    if db.execute('SELECT 1 FROM meta WHERE key=?', (marker,)).fetchone():
        return
    touched = set()
    for event in db.execute("SELECT e.id,e.text FROM events e JOIN files f ON f.id=e.file_id WHERE e.import_id=? AND f.parser='telemetry'", (iid,)).fetchall():
        obj, errors = decode(event['text'])
        if errors:
            continue
        body = json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        source, key = obj['source_id'], obj['event_id']
        inserted = db.execute('INSERT OR IGNORE INTO telemetry_records(source_id,event_key,event_id,body) VALUES(?,?,?,?)',
                   (source, key, event['id'], body)).rowcount
        rec = db.execute('SELECT id,body,conflict FROM telemetry_records WHERE source_id=? AND event_key=?', (source, key)).fetchone()
        if inserted:touched.add(source)
        if rec['body'] != body and not rec['conflict']:
            touched.add(source)
            db.execute('UPDATE telemetry_records SET conflict=1 WHERE id=?', (rec['id'],))
        db.execute('INSERT OR IGNORE INTO telemetry_evidence VALUES(?,?)', (rec['id'], event['id']))
    for source in touched:
        rebuild(db, source)
    db.execute('INSERT INTO meta VALUES(?,?)', (marker, VERSION))


def pending(db):
    with db:
        for iid, in db.execute('SELECT id FROM imports').fetchall():
            ingest(db, iid)


def clear_derived(db, source):
    # Only this extractor's products, never legacy metrics or analyst annotations.
    args = (source,)
    ids = [r[0] for r in db.execute('''SELECT t.metric_id FROM telemetry_intervals t
        JOIN telemetry_records r ON r.id=t.record_id WHERE r.source_id=?''', args)]
    for mid in ids:
        geo = [r[0] for r in db.execute('SELECT observation_id FROM geo_mos_evidence WHERE metric_id=?', (mid,))]
        for oid in geo:
            db.execute('DELETE FROM telemetry_geo_context WHERE observation_id=?', (oid,))
            db.execute('DELETE FROM geo_mos_evidence WHERE observation_id=?', (oid,))
            db.execute('DELETE FROM geo_mos WHERE id=? AND method=?', (oid, VERSION))
        db.execute('DELETE FROM telemetry_intervals WHERE metric_id=?', (mid,))
        db.execute('DELETE FROM metrics WHERE id=? AND extractor=?', (mid, VERSION))
    db.execute('''DELETE FROM geo_positions WHERE method=? AND event_id IN
        (SELECT event_id FROM telemetry_records WHERE source_id=?)''', (VERSION, source))


def rebuild(db, source):
    data = rows(db, 'SELECT * FROM telemetry_records WHERE source_id=? LIMIT ?', (source, LIMIT+1))
    if len(data) > LIMIT:
        raise ValueError('Oltre 100.000 eventi per sorgente telemetria: importazione annullata')
    clear_derived(db, source)
    groups = defaultdict(list)
    for r in data:
        r['event'] = json.loads(r['body'])
        r['p'] = r['event']['payload']
        r['issues'] = ['event_id_conflict'] if r['conflict'] else []
        if r['event']['validity'] != 'valid':
            issue(r, 'producer_invalid')
        e = r['event']
        groups[(e['session_id'], e['boot_id'])].append(r)
    for group in groups.values():
        group.sort(key=lambda r: (r['event']['seq'], r['id']))
        seqs = defaultdict(list)
        offsets = []
        for r in group:
            e = r['event']
            seqs[e['seq']].append(r)
            try:
                offsets.append(datetime.fromisoformat(e['observed_utc']).timestamp()-e['mono_ms']/1000)
                stamp(e, e['mono_ms'])
                if e['type']=='position':stamp(e,r['p']['fix_mono_ms'])
                if e['type']=='media_interval':stamp(e,r['p']['start_mono_ms'])
            except (OverflowError, ValueError):
                issue(r, 'clock_out_of_range')
        for batch in seqs.values():
            if len(batch) > 1:
                for r in batch:
                    issue(r, 'sequence_conflict')
        # A reset without a new boot ID, or a wall clock jump, has no safe alignment.
        unsafe = any(b['event']['mono_ms'] < a['event']['mono_ms'] for a, b in zip(group, group[1:]))
        unsafe |= bool(offsets and max(offsets)-min(offsets) > 1)
        unsafe |= len({r['event']['role'] for r in group}) > 1
        if unsafe:
            for r in group:
                issue(r, 'clock_or_role_discontinuity')
        for a, b in zip(group, group[1:]):
            if b['event']['seq'] > a['event']['seq']+1:
                issue(b, 'sequence_gap')
        derive_group(db, group)
    for r in data:
        db.execute('UPDATE telemetry_records SET issues=? WHERE id=?', (json.dumps(r['issues']), r['id']))


def usable(r):
    return not any(x != 'sequence_gap' for x in r['issues'])


class Indexed(list):
    def __init__(self, records):
        super().__init__(records)
        self.kinds = defaultdict(list)
        self.references = defaultdict(list)
        for r in records:
            self.kinds[r['event']['type']].append(r)
            for field in ('config_id', 'fix_id'):
                if field in r['p']:
                    self.references[(r['event']['type'],field,r['p'][field])].append(r)
        self.times = {}
        for kind, values in self.kinds.items():
            values.sort(key=lambda r: r['event']['mono_ms'])
            self.times[kind] = [r['event']['mono_ms'] for r in values]

    def between(self, kind, start, end):
        times = self.times.get(kind, [])
        return self.kinds[kind][bisect_right(times,start):bisect_right(times,end)]


def stream_key(p):
    s = p['stream']
    return (s['call_id'], s['sip_call_id'], s['stream_id'], s['ssrc'], s['direction'])


def latest(group, kind, mono, match=lambda r: True, max_age=None):
    # An invalid last observation is a barrier, not permission to reuse an older one.
    if isinstance(group, Indexed):
        values = group.kinds.get(kind, [])
        times = group.times.get(kind, [])
        stop = bisect_right(times, mono)
        begin = bisect_right(times, mono-max_age) if max_age is not None else 0
        candidates = []
        # Scan newest first, stopping once the latest matching timestamp is complete.
        moment = None
        for i in range(stop-1, begin-1, -1):
            r = values[i]
            if moment is not None and r['event']['mono_ms'] < moment:
                break
            if match(r):
                candidates.append(r)
                moment = r['event']['mono_ms']
    else:
        candidates = [r for r in group if r['event']['type'] == kind and r['event']['mono_ms'] <= mono and match(r)]
    if not candidates:
        return None
    moment = max(r['event']['mono_ms'] for r in candidates)
    batch = [r for r in candidates if r['event']['mono_ms'] == moment]
    if len(batch) != 1 or not usable(batch[0]) or (max_age is not None and mono-moment >= max_age):
        return None
    return batch[0]


def reference(group, kind, field, value, mono, match=lambda r: True):
    values = group.references.get((kind,field,value), []) if isinstance(group, Indexed) else group
    candidates = [r for r in values if r['event']['type'] == kind and r['p'].get(field) == value and match(r)]
    # Same config ID may be repeated identically, but cannot describe different content.
    if len({json.dumps(r['p'], sort_keys=True) for r in candidates}) > 1:
        return None
    return latest(candidates, kind, mono, max_age=None)


def derive_group(db, group):
    group = Indexed(group)
    by_event = {r['event']['event_id']: r for r in group}
    # Validate references used for auditing offline decisions, without issuing commands.
    plans = defaultdict(list)
    for r in group:
        if r['event']['type'] == 'plan_received':
            p = r['p']['plan']
            plans[(p['plan_id'], p['revision'])].append(r)
    for batch in plans.values():
        if len({r['p']['content_sha256'] for r in batch}) > 1:
            for r in batch:issue(r, 'plan_revision_conflict')
    for r in group:
        kind, p, e = r['event']['type'], r['p'], r['event']
        if kind == 'plan_received':
            requests = [x for x in group.kinds['api_request'] if x['p']['request_id']==p['request_id']
                        and x['p']['phase']=='started' and x['event']['mono_ms']<=e['mono_ms'] and usable(x)]
            if not requests:issue(r, 'request_reference_unresolved')
        if kind in ('plan_state', 'action') and p.get('plan'):
            ref = p['plan']
            known = plans.get((ref['plan_id'], ref['revision']), [])
            available = [x for x in known if usable(x) and x['event']['mono_ms'] <= e['mono_ms']]
            if not available:
                issue(r, 'plan_reference_unresolved')
            elif kind=='plan_state' and p['state'] in ('activated','resumed') and all(x['p']['valid_until_mono_ms']<=e['mono_ms'] for x in available):
                issue(r, 'expired_plan_activation')
        if kind == 'plan_state' and p['position_basis'] == 'measured':
            pos = by_event.get(p['position_event_id'])
            if not pos or pos['event']['type'] != 'position' or not usable(pos) or pos['event']['mono_ms'] > e['mono_ms']:
                issue(r, 'position_reference_unresolved')
        if kind == 'action':
            for field in ('old_config_id', 'new_config_id'):
                if not reference(group, 'media_config', 'config_id', p[field], e['mono_ms'],
                                 lambda x: stream_key(x['p']) == stream_key(p)):
                    issue(r, 'config_reference_unresolved')
    positions = []
    for r in group:
        if r['event']['type'] != 'position' or r['event']['role'] != 'app':
            continue
        p, e = r['p'], r['event']
        # Repeated fix IDs do not create new motion evidence; conflicts invalidate all copies.
        same = group.references[('position','fix_id',p['fix_id'])]
        if len({(x['p']['fix_mono_ms'], x['p']['latitude'], x['p']['longitude']) for x in same}) > 1:
            issue(r, 'fix_id_conflict')
        if not usable(r):
            continue
        event = db.execute('SELECT * FROM events WHERE id=?', (r['event_id'],)).fetchone()
        ts = stamp(e, p['fix_mono_ms'])
        pid = db.execute('''INSERT INTO geo_positions(event_id,import_id,source_line,ts,latitude,longitude,
            accuracy,kind,valid,method) VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (r['event_id'], event['import_id'], event['line_no'], ts, p['latitude'], p['longitude'],
             p['accuracy_m'], 'cached' if p['cached'] else 'fresh', 1, VERSION)).lastrowid
        r['position_id'] = pid
        positions.append(r)
    intervals = []
    previous = {}
    for r in sorted(group, key=lambda x: (x['event']['mono_ms'], x['id'])):
        e, p, kind = r['event'], r['p'], r['event']['type']
        if kind == 'media_interval':
            if not usable(r):
                continue
            config = reference(group, 'media_config', 'config_id', p['config_id'], p['start_mono_ms'],
                               lambda x: stream_key(x['p']) == stream_key(p))
            if not config:
                issue(r, 'config_reference_unresolved')
                continue
            if not p['complete'] or p['end_mono_ms']-p['start_mono_ms'] > 30000:
                issue(r, 'incomplete_or_long_interval')
                continue
            changes = group.between('media_config', p['start_mono_ms'], p['end_mono_ms']-0.000001)
            barriers = group.between('collection', p['start_mono_ms'], p['end_mono_ms']-0.000001)
            if any(stream_key(x['p'])==stream_key(p) and x['p']['config_id']!=p['config_id'] for x in changes) or any(
                    x['p']['subsystem'] in ('media','logger','clock') and x['p']['status'] not in ('started','resumed') for x in barriers):
                issue(r, 'interval_crosses_configuration_or_collection_gap')
                continue
            if p['semantics_id'] != 'rtp-sequence-window/1':
                issue(r, 'loss_semantics_unverified')
                continue
            if p['stream']['direction'] != 'local_receive':
                issue(r, 'receive_counters_required')
                continue
            if p['expected_packets'] == 0:
                issue(r, 'no_expected_packets')
                continue
            loss = 100*(p['expected_packets']-p['received_in_window_packets'])/p['expected_packets']
            intervals.append(dict(r=r, start=p['start_mono_ms'], end=p['end_mono_ms'], loss=loss,
                                  direction='incoming', previous=None, refs=[config['id']]))
        elif kind == 'rtcp':
            key = (stream_key(p), p['transport_direction'])
            old = previous.get(key)
            previous[key] = None
            if not usable(r):
                continue
            try:
                rr = [b for b in reports(p['packet_hex']) if b['ssrc'] == p['stream']['ssrc']]
            except ValueError as ex:
                issue(r, str(ex))
                continue
            if len(rr) != 1:
                issue(r, 'rtcp_matching_report_ambiguous_or_missing')
                continue
            b = rr[0]
            previous[key] = (r, b)
            if old is None:
                issue(r, 'rtcp_baseline_only')
                continue
            a, before = old
            elapsed = e['mono_ms']-a['event']['mono_ms']
            expected = b['highest']-before['highest']
            lost = b['lost']-before['lost']
            if not 0 < elapsed <= 30000 or b['reporter'] != before['reporter'] or not 0 <= lost <= expected or expected <= 0:
                issue(r, 'rtcp_reset_gap_or_loss_ambiguous')
                continue
            # Sent RR describes local reception; received RR describes peer reception.
            direction = 'incoming' if p['transport_direction'] == 'sent' else 'outgoing'
            wanted = 'local_receive' if direction == 'incoming' else 'local_send'
            if p['stream']['direction'] != wanted:
                issue(r, 'rtcp_stream_direction_conflict')
                continue
            intervals.append(dict(r=r, start=a['event']['mono_ms'], end=e['mono_ms'], loss=100*lost/expected,
                                  direction=direction, previous=a['id'], refs=[]))
    # Overlapping observations of one RTP stream must not count twice, even with different event IDs.
    stream_intervals = defaultdict(list)
    for interval in intervals:
        s = interval['r']['p']['stream']
        stream_intervals[(s['call_id'],s['stream_id'],s['ssrc'],interval['direction'])].append(interval)
    for values in stream_intervals.values():
        sequence_windows = {}
        for a in sorted(values, key=lambda x:x['start']):
            p = a['r']['p']
            if a['r']['event']['type'] != 'media_interval':continue
            epoch = p['counter_epoch']
            before = sequence_windows.get(epoch)
            if before and p['sequence_first'] <= before['r']['p']['sequence_last']:
                before['suppressed'] = a['suppressed'] = True
                issue(before['r'], 'sequence_window_reused')
                issue(a['r'], 'sequence_window_reused')
            sequence_windows[epoch] = a
        active = []
        for b in sorted(values, key=lambda x:x['start']):
            active = [a for a in active if a['end'] > b['start']]
            if len(active) > 1000:
                raise ValueError('Oltre 1.000 intervalli telemetria sovrapposti')
            for a in active:
                # Local explicit sequence windows supersede overlapping local RTCP intervals.
                if a['r']['event']['type'] != b['r']['event']['type']:
                    (a if a['r']['event']['type'] == 'rtcp' else b)['suppressed'] = True
                else:
                    a['suppressed'] = b['suppressed'] = True
                    issue(a['r'], 'overlapping_media_intervals')
                    issue(b['r'], 'overlapping_media_intervals')
            active.append(b)
    for interval in intervals:
        if not interval.get('suppressed'):
            store_interval(db, group, positions, interval)


def context_at(group, record, mono):
    p = record['p']
    network = latest(group, 'network', mono, lambda x: x['p']['scope'] == 'media_path'
                     and x['p']['stream_id'] == p['stream']['stream_id'], max_age=30000)
    if network and p.get('network_id') is not None and network['p']['network_id'] != p['network_id']:
        network = None
    session = latest(group, 'session', mono)
    platform = session['p']['platform'] if session else 'unknown'
    if platform in ('windows', 'macos', 'linux'):
        platform = 'desktop'
    n = network['p'] if network else {}
    return dict(platform=platform, access=n.get('access', 'unknown'), upstream=n.get('upstream', 'unknown'),
                operator=n.get('serving_operator') or 'unknown'), network, session


def store_interval(db, group, positions, interval):
    r = interval['r']; e = r['event']; p = r['p']; s = p['stream']
    begin, end = stamp(e, interval['start']), stamp(e, interval['end'])
    raw = db.execute('SELECT * FROM events WHERE id=?', (r['event_id'],)).fetchone()
    cid = s['sip_call_id']
    call_id = pid = None
    if cid:
        # Structured identities are exact; never create identity from local call IDs alone.
        db.execute('INSERT OR IGNORE INTO calls(call_key,sip_call_id,start,end) VALUES(?,?,?,?)', ('sip:'+cid, cid, begin, end))
        call_id = db.execute('SELECT id FROM calls WHERE call_key=?', ('sip:'+cid,)).fetchone()[0]
        source_count = db.execute('''SELECT count(DISTINCT r.source_id) FROM telemetry_evidence x
            JOIN telemetry_records r ON r.id=x.record_id JOIN events e ON e.id=x.event_id WHERE e.import_id=?''', (raw['import_id'],)).fetchone()[0]
        if source_count == 1:
            db.execute('''INSERT OR IGNORE INTO perspectives(call_id,import_id,start,end,status,evidence)
                VALUES(?,?,?,?,?,?)''', (call_id, raw['import_id'], begin, end, 'partial', 'Structured telemetry; UTC'))
            pid = db.execute('SELECT id FROM perspectives WHERE call_id=? AND import_id=?', (call_id, raw['import_id'])).fetchone()[0]
            db.execute("UPDATE perspectives SET start=min(start,?),end=max(end,?) WHERE id=? AND evidence='Structured telemetry; UTC'", (begin, end, pid))
            db.execute('''UPDATE calls SET start=(SELECT min(start) FROM perspectives WHERE call_id=?),
                end=(SELECT max(end) FROM perspectives WHERE call_id=?) WHERE id=?''', (call_id,call_id,call_id))
            db.execute('UPDATE events SET call_id=?,perspective_id=? WHERE id=? AND call_id IS NULL', (call_id,pid,r['event_id']))
        else:
            issue(r, 'multiple_sources_in_zip')
    flow = 'telemetry:'+e['session_id']+':'+s['stream_id']
    mid = db.execute('''INSERT INTO metrics(event_id,perspective_id,call_id,ts,name,value,unit,direction,flow,ssrc,
        statistic,valid,source_line,sample_kind,extractor) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (r['event_id'], pid, call_id, begin, 'telemetry.network_loss', interval['loss'], '%', interval['direction'],
         flow, str(s['ssrc']), 'sample', 1, raw['line_no'], 'interval', VERSION)).lastrowid
    context, network, session = context_at(group, r, interval['start'])
    if p.get('network_id') is not None and network is None:
        issue(r, 'network_reference_unresolved')
    refs = interval['refs'] + [x['id'] for x in (network, session) if x]
    db.execute('INSERT INTO telemetry_intervals VALUES(?,?,?,?,?,?,?,?)',
               (mid, r['id'], interval['previous'], begin, end, e['role'], json.dumps(context), json.dumps(refs)))
    if e['role'] != 'app':
        return
    from .mos import score, MODEL
    boundaries = {interval['start'], interval['end']}
    local_records = []
    for kind in ('position','network','collection'):
        local_records.extend(group.between(kind, interval['start']-30000, interval['end']))
    for pos in local_records:
        if pos['event']['type'] == 'position':
            for t in (pos['event']['mono_ms'], pos['p']['fix_mono_ms']+30000):
                if interval['start'] < t < interval['end']:
                    boundaries.add(t)
        elif pos['event']['type'] == 'network':
            for t in (pos['event']['mono_ms'], pos['event']['mono_ms']+30000):
                if interval['start'] < t < interval['end']:
                    boundaries.add(t)
        elif pos['event']['type'] == 'collection' and interval['start'] < pos['event']['mono_ms'] < interval['end']:
            boundaries.add(pos['event']['mono_ms'])
    times = sorted(boundaries)
    for a, b in zip(times, times[1:]):
        pos = latest(group, 'position', a)
        if not pos or 'position_id' not in pos or pos['p']['cached'] or a-pos['p']['fix_mono_ms'] >= 30000:
            continue
        state = latest(group, 'collection', a, lambda x: x['p']['subsystem'] == 'position')
        if state and state['event']['mono_ms'] >= pos['event']['mono_ms'] and state['p']['status'] not in ('started', 'resumed'):
            continue
        ctx, _, _ = context_at(group, r, a)
        fix = pos['p']
        signature = hashlib.sha256(f"{e['source_id']}:{e['event_id']}:{interval['direction']}".encode()).hexdigest()
        for quality in ('fresh', 'declared'):
            oid = db.execute('''INSERT INTO geo_mos(signature,start,end,latitude,longitude,accuracy,position_ts,
                direction,mos,loss,quality,model,method) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (signature, stamp(e,a), stamp(e,b), fix['latitude'], fix['longitude'], fix['accuracy_m'],
                 stamp(e,fix['fix_mono_ms']), 'downstream' if interval['direction']=='incoming' else 'upstream',
                 score(interval['loss']), interval['loss'], quality, MODEL['version'], VERSION)).lastrowid
            db.execute('INSERT INTO geo_mos_evidence VALUES(?,?,?)', (oid, mid, pos['position_id']))
            db.execute('INSERT INTO telemetry_geo_context VALUES(?,?)', (oid, json.dumps(ctx)))


def calculate(db, ids, perspective_id=None):
    from .mos import score, MODEL, NAME
    # Legacy-only archives must not scan all metrics to discover an empty join,
    # especially when the call register requests hundreds of summaries.
    if not db.execute('SELECT 1 FROM telemetry_intervals LIMIT 1').fetchone():
        return []
    marks = ','.join('?' for _ in ids)
    data = rows(db, f'''SELECT m.*,t.start window_start,t.end window_end,t.role,t.record_id,t.previous_record_id,t.refs,
        p.start,p.end,p.connected,i.label,i.clock_offset,f.name filename,e.line_no
        FROM telemetry_intervals t JOIN metrics m ON m.id=t.metric_id
        LEFT JOIN perspectives p ON p.id=m.perspective_id JOIN events e ON e.id=m.event_id
        JOIN imports i ON i.id=e.import_id JOIN files f ON f.id=e.file_id
        WHERE m.call_id IN ({marks}) {"AND m.perspective_id=?" if perspective_id is not None else ""}
        ORDER BY t.start LIMIT ?''', [*ids, *([perspective_id] if perspective_id is not None else []), LIMIT+1])
    if len(data) > LIMIT:
        raise ValueError('Oltre 100.000 intervalli telemetria: restringere la selezione')
    out = []
    for m in data:
        refs = list(dict.fromkeys([m['record_id'], *json.loads(m['refs']), *([m['previous_record_id']] if m['previous_record_id'] else [])]))
        evidence = rows(db, f'''SELECT x.event_id,f.name filename,e.line_no line FROM telemetry_evidence x
            JOIN events e ON e.id=x.event_id JOIN files f ON f.id=e.file_id
            WHERE x.record_id IN ({','.join('?' for _ in refs)}) ORDER BY x.event_id LIMIT 1001''', refs)
        if len(evidence) > 1000:
            raise ValueError('Oltre 1.000 evidenze per intervallo telemetria')
        for ev in evidence:
            ev['metric_id'] = m['id']
        out.append(dict(m, name=NAME, value=score(m['value']), unit='MOS', valid_until=m['window_end'],
                        start=m['start'] or m['window_start'],
                        report_ts=db.execute('SELECT ts FROM events WHERE id=?',(m['event_id'],)).fetchone()[0], observation_start=m['window_start'], loss_percent=m['value'], evidence=evidence,
                        model=MODEL, clock_domain='UTC', sample_kind='interval',
                        interval_seconds=(datetime.fromisoformat(m['window_end'])-datetime.fromisoformat(m['window_start'])).total_seconds()))
    return out


def status(db):
    issue_count = db.execute("SELECT count(*) FROM telemetry_records WHERE issues!='[]'").fetchone()[0]
    return dict(version=VERSION, records=db.execute('SELECT count(*) FROM telemetry_records').fetchone()[0],
                evidence=db.execute('SELECT count(*) FROM telemetry_evidence').fetchone()[0],
                conflicts=db.execute('SELECT count(*) FROM telemetry_records WHERE conflict=1').fetchone()[0],
                intervals=db.execute('SELECT count(*) FROM telemetry_intervals').fetchone()[0],
                issues=rows(db, '''SELECT r.id,r.event_id,r.issues,f.name filename,e.line_no FROM telemetry_records r
                    JOIN events e ON e.id=r.event_id JOIN files f ON f.id=e.file_id
                    WHERE r.issues!='[]' ORDER BY r.id LIMIT 200'''),
                issues_limit=200, issue_count=issue_count, issues_truncated=issue_count>200)
