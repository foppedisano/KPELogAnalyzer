"""Measurement vantage point, distinct from transport and observer names."""
import re
from .db import rows
from .media_semantics import metric_orientation, metric_semantics

GROUPS = {
    'downstream': 'Downstream · peer/GW → app',
    'upstream': 'Upstream · app → peer/GW',
    'bidirectional': 'Bidirezionale e indicatori combinati',
    'local': 'Percorso locale di ricezione · tratta da verificare',
    'peer': 'Report del peer · tratta da verificare',
    'transmit': 'Trasmissione locale · tratta da verificare',
    'processing': 'Elaborazione locale · direzione non determinata',
    'unknown': 'Interpretazione da verificare',
}


def _network_device(value, prefix):
    # Match identities, not an observer mentioning another thread.
    return bool(re.fullmatch(prefix + r'(?:\d+ of Line \d+)?', value or '', re.I))


def _device_path(direction, device, output_device, input_device):
    measured = device or input_device
    rx = _network_device(measured, 'NART')
    tx = _network_device(measured, 'NAWT') or _network_device(output_device, 'NAWT')
    if rx and tx: return 'mixed', 'device_context'
    if rx: return 'receive', 'device_context'
    if tx: return 'transmit', 'device_context'
    # Generic VD, file, microphone or speaker does not establish a network leg.
    if any((device, output_device, input_device)):
        return 'unknown', 'device_context'
    return {'incoming': 'receive', 'outgoing': 'transmit'}.get(direction, 'unknown'), 'reported_direction'


def context(name, direction, role='app', *, device='', output_device='', input_device=''):
    rule = metric_orientation(name)['rule']
    def result(category, label, basis='metric_field'):
        return dict(category=category, label=label, basis=basis, rule=rule)
    def receiver(local, label):
        if role == 'app':
            return result('downstream' if local else 'upstream', ('Downstream' if local else 'Upstream') + ' · ' + label)
        if role == 'gw':
            return result('upstream' if local else 'downstream', ('Upstream' if local else 'Downstream') + ' · ' + label + ' · osservazione GW')
        return result('local' if local else 'peer', label + ' · tratta da verificare')
    if name == 'derived.perceptual_quality':
        return receiver(True, 'Continuità audio locale NART → AWT · indice 0–100')
    if rule == 'unconfirmed':
        return result('unknown', 'Semantica specifica non confermata · ' + (direction or 'direzione non nota'))
    if rule == 'roundtrip': return result('bidirectional', 'Andata e ritorno RTP/RTCP')
    if rule == 'probe': return result('bidirectional', 'Andata e ritorno ICMP · destinazione della sonda')
    if rule == 'combined': return result('bidirectional', 'Indicatore combinato dei device A+B · non end-to-end')
    if rule == 'local_packets': return receiver(True, 'Pacchetti ricevuti localmente')
    if rule == 'peer_sent':
        if role not in ('app', 'gw'):
            return result('peer', 'Pacchetti trasmessi dal peer · Sender Report · tratta da verificare')
        return receiver(True, 'Pacchetti trasmessi dal peer · Sender Report, non ricezione misurata')
    if rule == 'peer_lost': return receiver(False, 'Pacchetti persi dichiarati dal peer · Receiver Report')
    if rule == 'rtp_receive': return receiver(True, 'Ricezione RTP locale')
    if rule in ('receiver_report', 'model', 'verified_loss'):
        if direction not in ('incoming', 'outgoing'):
            return result('unknown', 'Ricevitore non determinato · direzione non nota')
        local = direction == 'incoming'
        label = 'Ricezione locale' if local else 'Ricezione del peer'
        if rule == 'model': label = 'Stima MOS sulla perdita · ' + label.lower()
        elif rule == 'verified_loss': label = 'Perdita su intervallo verificato · ' + label.lower()
        else: label += ' · report RTCP'
        return receiver(local, label)
    path, basis = _device_path(direction, device, output_device, input_device)
    domain = metric_semantics(name)['domain']
    measure = 'Scheduling locale' if domain == 'scheduling' else 'Elaborazione locale'
    if path == 'mixed':
        return result('processing', measure + ' · percorso NART → NAWT (ricezione e trasmissione)', basis)
    if path == 'unknown':
        return result('processing', measure + ' del device · direzione di rete non determinata', basis)
    if path == 'receive':
        c = receiver(True, measure + ' nel percorso di ricezione')
        c['basis'] = basis
        return c
    if role == 'app':
        return result('upstream', measure + ' in trasmissione · app → rete', basis)
    if role == 'gw':
        return result('downstream', measure + ' in trasmissione · GW → app', basis)
    return result('transmit', measure + ' in trasmissione · componente → rete, tratta da verificare', basis)


KIND_LABELS = {
    'sample': 'campione', 'gauge': 'valore istantaneo', 'counter': 'contatore cumulativo',
    'interval': 'incremento / valore su intervallo', 'event': 'evento', 'episode': 'episodio',
    'step': 'valore mantenuto a scadenza', 'derived step': 'stima mantenuta a scadenza',
    'derived gauge': 'indicatore combinato', 'reported statistic': 'statistica riportata',
}


def annotate(db, data):
    from .catalog import CATALOG
    kinds = {m['name']: m['kind'] for m in CATALOG}
    roles = {r['perspective_id']: r['role'] for r in rows(db, 'SELECT perspective_id,role FROM observation_roles')}
    for m in data:
        pid = m.get('perspective_id')
        role = roles.get(pid, m.get('role', 'app'))
        c = context(m['name'], m.get('direction', ''), role,
            **{key: m.get(key, '') for key in ('device', 'output_device', 'input_device')})
        c['role_basis'] = 'confirmed' if pid in roles else 'telemetry' if 'role' in m else 'app_assumed'
        if c['role_basis'] == 'app_assumed' and c['category'] in ('upstream', 'downstream'):
            c['label'] += ' · app presunta'
        m['measurement_context'] = c
        kind = m.get('sample_kind') or m.get('kind') or kinds.get(m['name'], 'sample')
        if kind == 'sample': kind = kinds.get(m['name'], kind)
        statistic = m.get('statistic', 'sample')
        m['observation_label'] = ('Statistica riportata · ' + statistic if statistic not in ('sample', '')
            else KIND_LABELS.get(kind, kind))
    return data


def options(db, ids, catalog):
    marks = ','.join('?' for _ in ids)
    ps = rows(db, f'SELECT p.id,r.role FROM perspectives p LEFT JOIN observation_roles r ON r.perspective_id=p.id WHERE p.call_id IN ({marks})', ids)
    roles = {(p['role'] or 'app') for p in ps}
    role = next(iter(roles)) if len(roles) == 1 else 'unknown'
    observed = {}
    for row in rows(db, f'''SELECT DISTINCT m.name,m.direction,m.device,m.output_device,m.input_device,r.role
        FROM metrics m LEFT JOIN observation_roles r ON r.perspective_id=m.perspective_id
        WHERE m.call_id IN ({marks})''', ids):
        observed.setdefault(row['name'], []).append(row)
    sources = {'derived.silence_delta': 'vd.silence_skipped', 'derived.silence_played_delta': 'vd.silence_played'}
    output = []
    for metric in catalog:
        name = metric['name']
        if name in ('derived.buffer_sum', 'derived.dejitter_sum'): continue
        directions = ['incoming', 'outgoing'] if name in ('rtcp.jitter', 'rtcp.loss', 'derived.mos_reference', 'telemetry.network_loss') else ['']
        for direction in directions:
            c = context(name, direction, role)
            candidates = [context(name, row['direction'], row['role'] or 'app',
                **{key: row[key] for key in ('device', 'output_device', 'input_device')})
                for row in observed.get(sources.get(name, name), []) if not direction or row['direction'] == direction]
            variants = {(v['category'], v['label']) for v in candidates}
            if len(variants) == 1: c = candidates[0]
            elif len(variants) > 1:
                c = dict(category='unknown', label='Contesti multipli · vedere le singole serie')
            output.append(dict(name=name, direction=direction, category=c['category'], group=GROUPS[c['category']],
                title=metric['title'] + ' · ' + c['label'], value=name + ('|' + direction if direction else ''),
                units=metric['units'], unit_label=metric['unit_label'], unit_labels=metric['unit_labels'], unit_note=metric['unit_note']))
    return output
