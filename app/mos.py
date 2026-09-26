"""Fixed-reference loss score. No inferred codec, playout loss or peer identity."""
import math
from datetime import datetime, timedelta
from .db import rows

NAME = 'derived.mos_reference'
MODEL = dict(version='loss-reference-1', codec='G.711', packet_ms=10,
             plc='G.711 Appendix I', Ie=0, Bpl=25.1, BurstR=1, baseline_R=93.2,
             description='Profilo fisso; sola perdita RTCP. Jitter, ritardo e scarti al playout esclusi.')
LIMIT = 100000


def score(loss):
    if not math.isfinite(loss) or not 0 <= loss <= 100:
        return None
    r = max(0, min(100, MODEL['baseline_R'] - 95 * loss / (loss + MODEL['Bpl'])))
    return 1 + .035 * r + 7e-6 * r * (r - 60) * (100 - r)


def calculate(db, ids, perspective_id=None):
    marks = ','.join('?' for _ in ids)
    data = rows(db, f'''SELECT m.*,p.start,p.end,p.connected,i.label,i.clock_offset,
        f.name filename,COALESCE(m.source_line,e.line_no) line_no
        FROM metrics m JOIN perspectives p ON p.id=m.perspective_id
        JOIN imports i ON i.id=p.import_id JOIN events e ON e.id=m.event_id
        JOIN files f ON f.id=e.file_id WHERE m.call_id IN ({marks})
        AND m.name='rtcp.loss' AND m.statistic='sample'
        {"AND m.perspective_id=?" if perspective_id is not None else ""}
        ORDER BY m.ts,m.id LIMIT {LIMIT+1}''', [*ids, *([perspective_id] if perspective_id is not None else [])])
    if len(data) > LIMIT:
        raise ValueError('Oltre 100.000 campioni MOS: restringi la selezione')
    groups = {}
    for m in data:
        key = tuple(m[k] for k in ('perspective_id','direction','flow','ssrc'))
        groups.setdefault(key, {}).setdefault(m['ts'], []).append(m)
    out = []
    for group in groups.values():
        stamps = sorted(group)
        previous = None
        for index, ts in enumerate(stamps):
            batch = group[ts]
            m = batch[0]
            t = datetime.fromisoformat(ts)
            valid = all(x['valid'] and x['unit']=='%' and score(x['value']) is not None for x in batch)
            valid = valid and len({x['value'] for x in batch}) == 1
            end = t + timedelta(seconds=30)
            if index+1 < len(stamps):
                end = min(end, datetime.fromisoformat(stamps[index+1]))
            if m['end']:
                end = min(end, datetime.fromisoformat(m['end']))
            begin = max(t, datetime.fromisoformat(m['connected'] or m['start']))
            if valid and end > begin:
                evidence = [dict(event_id=x['event_id'], metric_id=x['id'],
                                 filename=x['filename'], line=x['line_no']) for x in batch]
                out.append(dict(m, name=NAME, value=score(m['value']), unit='MOS',
                    sample_kind='step', valid=1, extractor=MODEL['version'],
                    ts=begin.isoformat(' ',timespec='microseconds'),
                    valid_until=end.isoformat(' ',timespec='microseconds'),
                    report_ts=ts, observation_start=previous,
                    loss_percent=m['value'], evidence=evidence, model=MODEL,
                    interval_seconds=(end-begin).total_seconds()))
            previous = ts
    from .telemetry_store import calculate as telemetry_calculate
    out.extend(telemetry_calculate(db, ids, perspective_id))
    return sorted(out, key=lambda x:(x['ts'],x['id']))


def call_summary(db, call_id):
    """One declared vantage point; never average duplicate exports or RTP streams."""
    p = db.execute('''SELECT p.*,i.label,r.role FROM perspectives p
        JOIN imports i ON i.id=p.import_id LEFT JOIN observation_roles r ON r.perspective_id=p.id
        WHERE p.call_id=? ORDER BY p.import_id DESC,p.id DESC LIMIT 1''', (call_id,)).fetchone()
    result = dict(downstream=None, upstream=None, reason='Nessuna prospettiva')
    if p is None:
        return result
    result.update(perspective_id=p['id'], source=p['label'], role_basis='confirmed' if p['role'] else 'app_assumed')
    if p['role'] not in (None, 'app'):
        result['reason'] = 'Ruolo/tratta da verificare nel pannello MOS'
        return result
    try:
        values = calculate(db, [call_id], p['id'])
    except ValueError as error:
        result['reason'] = str(error)
        return result
    roles = {v['role'] for v in values if v.get('clock_domain') == 'UTC'}
    if roles == {'gw'}:
        result['role_basis'] = 'telemetry_gw'
        values = [dict(v,direction='outgoing' if v['direction']=='incoming' else 'incoming') for v in values]
    elif roles == {'app'}:
        result['role_basis'] = 'telemetry_app'
    result['reason'] = 'Nessun intervallo MOS valido'
    begin, end = p['connected'] or p['start'], p['end']
    duration = max(0, (datetime.fromisoformat(end)-datetime.fromisoformat(begin)).total_seconds()) if begin and end else None
    for direction, name in [('incoming','downstream'), ('outgoing','upstream')]:
        series = [m for m in values if m['direction']==direction]
        if len({(m['flow'],m['ssrc']) for m in series}) > 1:
            result[name+'_reason'] = 'Più flussi/SSRC: selezionare la serie nel dettaglio'
            continue
        if not series:
            continue
        covered = sum(m['interval_seconds'] for m in series)
        low, high = min(series,key=lambda m:m['value']), max(series,key=lambda m:m['value'])
        result[name] = dict(minimum=low['value'], maximum=high['value'],
            mean=sum(m['value']*m['interval_seconds'] for m in series)/covered,
            covered_seconds=covered, coverage_percent=100*covered/duration if duration else None,
            minimum_event_id=low['event_id'], maximum_event_id=high['event_id'],
            basis='local' if direction=='incoming' else 'remote_rtcp')
    return result


def analysis(db, local, peer=None, local_role='app'):
    """The peer selection explicitly declares the opposite receiver of this leg.

    No automatic cross-call pairing. A supplied peer replaces RTCP fallback;
    gaps stay gaps rather than silently switching measurement sources.
    """
    if local_role not in ('app','gw'):
        raise ValueError('Ruolo locale non valido')
    if peer == local:
        raise ValueError('Seleziona due prospettive distinte')
    ps = []
    for pid in (local, peer):
        if pid is None:
            continue
        p = db.execute('SELECT * FROM perspectives WHERE id=?', (pid,)).fetchone()
        if not p:
            raise ValueError('Prospettiva inesistente')
        ps.append(dict(p))
    if len(ps)==2 and ps[0]['import_id']==ps[1]['import_id']:
        raise ValueError('Il peer deve provenire da una sorgente distinta')
    scores = calculate(db, list(dict.fromkeys(p['call_id'] for p in ps)))
    receive = lambda pid, direction: [m for m in scores if m['perspective_id']==pid and m['direction']==direction]
    downstream = receive(local, 'incoming')
    upstream = receive(peer, 'incoming') if peer else receive(local, 'outgoing')
    local_basis, remote_basis = 'local', 'peer_local_reused' if peer else 'remote_rtcp'
    if local_role == 'gw':
        downstream, upstream = upstream, downstream
        local_basis, remote_basis = remote_basis, local_basis
    from .single_metrics import calculate as single
    context = []
    for p in ps:
        context.extend(m for m in single(db,[p['call_id']],'derived.silence_delta') if m['perspective_id']==p['id'])
    marks=','.join('?' for _ in ps)
    extra=rows(db,f'''SELECT m.*,f.name filename,COALESCE(m.source_line,e.line_no) line_no,
        i.clock_offset FROM metrics m JOIN events e ON e.id=m.event_id
        JOIN files f ON f.id=e.file_id JOIN perspectives p ON p.id=m.perspective_id
        JOIN imports i ON i.id=p.import_id WHERE m.perspective_id IN ({marks})
        AND m.name IN ('vd.missing_packets','rtcp.jitter','rtcp.rtt') AND m.valid=1
        ORDER BY m.ts,m.id LIMIT {LIMIT+1}''', [p['id'] for p in ps])
    if len(extra)+len(context)>LIMIT:
        raise ValueError('Troppi campioni di contesto: restringi la selezione')
    return dict(model=MODEL, local=local, peer=peer, local_role=local_role, downstream=downstream, upstream=upstream,
                downstream_basis=local_basis, upstream_basis=remote_basis,
                context=context+extra,
                limitations=['Stima basata sulla sola perdita; profilo fisso e perdite casuali assunte.',
                    'Silenzio saltato e missing packets sono contesto, non penalità MOS additive.',
                    'Jitter e RTT non sono convertiti in perdita o ritardo unidirezionale.',
                    'Nessuna stima prima del primo report; scadenza dopo 30 s o a fine chiamata.'])
