"""Measurement vantage point, independent from raw log direction."""
from .db import rows

GROUPS={
    'downstream':'Downstream · peer/GW → app',
    'upstream':'Upstream · app → peer/GW',
    'bidirectional':'Bidirezionale e indicatori combinati',
    'local':'Ricezione locale · tratta da verificare',
    'peer':'Ricezione del peer · tratta da verificare',
    'unknown':'Interpretazione da verificare',
}


def context(name,direction,role='app'):
    if name.startswith('vd.') and direction not in ('incoming',''):
        return dict(category='unknown',label='Elaborazione locale in uscita' if direction=='outgoing' else 'Device locale · direzione non attribuita')
    if name in ('rtcp.rtt','network.ping','kpe.common.rtt') or name in ('derived.buffer_sum','derived.dejitter_sum'):
        return dict(category='bidirectional',label='Andata e ritorno' if 'rtt' in name or name=='network.ping' else 'Indicatore combinato A+B')
    local=(name.startswith('vd.') or name.startswith('incident.') or name in ('derived.silence_delta','derived.silence_played_delta')
           or name=='rtcp.packets_received' or (name in ('rtcp.jitter','rtcp.loss','derived.mos_reference','telemetry.network_loss') and direction=='incoming'))
    peer=name in ('rtcp.jitter','rtcp.loss','derived.mos_reference','telemetry.network_loss') and direction=='outgoing'
    if role=='gw' and (local or peer):
        return dict(category='upstream' if local else 'downstream',label='Upstream · ricezione GW' if local else 'Downstream · report del peer del GW')
    if local:
        return dict(category='downstream' if role=='app' else 'local',label='Downstream · misurato nell’app' if role=='app' else 'Ricezione locale del componente · tratta da verificare')
    if peer:
        return dict(category='upstream' if role=='app' else 'peer',label='Upstream · riportato dal peer/GW' if role=='app' else 'Ricezione del peer del componente · tratta da verificare')
    return dict(category='unknown',label='Semantica KPE da verificare · '+(direction or 'direzione non nota'))


def annotate(db,data):
    roles={r['perspective_id']:r['role'] for r in rows(db,'SELECT perspective_id,role FROM observation_roles')}
    for m in data:
        pid=m.get('perspective_id')
        role=roles.get(pid,m.get('role','app'))
        m['measurement_context']=context(m['name'],m.get('direction',''),role)
        m['measurement_context']['role_basis']='confirmed' if pid in roles else 'telemetry' if 'role' in m else 'app_assumed'
    return data


def options(db,ids,catalog):
    marks=','.join('?' for _ in ids)
    ps=rows(db,f'SELECT p.id,r.role FROM perspectives p LEFT JOIN observation_roles r ON r.perspective_id=p.id WHERE p.call_id IN ({marks})',ids)
    role='app' if all((p['role'] or 'app')=='app' for p in ps) else 'unknown'
    vd_directions={}
    for row in rows(db,f"SELECT DISTINCT name,direction FROM metrics WHERE call_id IN ({marks}) AND name LIKE 'vd.%'",ids):
        vd_directions.setdefault(row['name'],set()).add(row['direction'])
    output=[]
    for metric in catalog:
        name=metric['name']
        if name in ('derived.buffer_sum','derived.dejitter_sum'):continue
        directions=['incoming','outgoing'] if name in ('rtcp.jitter','rtcp.loss','derived.mos_reference','telemetry.network_loss') else ['']
        for direction in directions:
            c=context(name,direction,role)
            if name.startswith('vd.'):
                observed=vd_directions.get(name,set())
                if observed and observed!={'incoming'}:
                    c=context(name,next(iter(observed)) if len(observed)==1 else 'unknown',role)
            output.append(dict(name=name,direction=direction,category=c['category'],group=GROUPS[c['category']],
                title=metric['title']+' · '+c['label'],value=name+('|' +direction if direction else '')))
    return output
