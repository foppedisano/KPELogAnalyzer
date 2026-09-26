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
    if name in ('rtcp.rtt','network.ping','kpe.common.rtt') or name in ('derived.buffer_sum','derived.dejitter_sum'):
        return dict(category='bidirectional',label='Andata e ritorno' if 'rtt' in name or name=='network.ping' else 'Indicatore combinato A+B')
    local=(name.startswith('vd.') or name.startswith('incident.') or name=='derived.silence_delta'
           or name=='rtcp.packets_received' or (name in ('rtcp.jitter','rtcp.loss','derived.mos_reference') and direction=='incoming'))
    peer=name in ('rtcp.jitter','rtcp.loss','derived.mos_reference') and direction=='outgoing'
    if local:
        return dict(category='downstream' if role=='app' else 'local',label='Downstream · misurato nell’app' if role=='app' else 'Ricezione locale del componente · tratta da verificare')
    if peer:
        return dict(category='upstream' if role=='app' else 'peer',label='Upstream · riportato dal peer/GW' if role=='app' else 'Ricezione del peer del componente · tratta da verificare')
    return dict(category='unknown',label='Semantica KPE da verificare · '+(direction or 'direzione non nota'))


def annotate(db,data):
    roles={r['perspective_id']:r['role'] for r in rows(db,'SELECT perspective_id,role FROM observation_roles')}
    for m in data:
        pid=m.get('perspective_id')
        role=roles.get(pid,'app')
        m['measurement_context']=context(m['name'],m.get('direction',''),role)
        m['measurement_context']['role_basis']='confirmed' if pid in roles else 'app_assumed'
    return data


def options(db,ids,catalog):
    marks=','.join('?' for _ in ids)
    ps=rows(db,f'SELECT p.id,r.role FROM perspectives p LEFT JOIN observation_roles r ON r.perspective_id=p.id WHERE p.call_id IN ({marks})',ids)
    role='app' if all((p['role'] or 'app')=='app' for p in ps) else 'unknown'
    output=[]
    for metric in catalog:
        name=metric['name']
        if name in ('derived.buffer_sum','derived.dejitter_sum'):continue
        directions=['incoming','outgoing'] if name in ('rtcp.jitter','rtcp.loss','derived.mos_reference') else ['']
        for direction in directions:
            c=context(name,direction,role)
            output.append(dict(name=name,direction=direction,category=c['category'],group=GROUPS[c['category']],
                title=metric['title']+' · '+c['label'],value=name+('|' +direction if direction else '')))
    return output
