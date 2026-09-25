"""Explicit per-call observation roles; never infer a participant from a server ZIP."""
from .db import rows


def listing(db):
    return rows(db, '''SELECT p.id perspective_id,p.call_id,p.import_id,p.start,p.end,
        i.label,c.sip_call_id,r.session,r.participant,r.role,r.node,r.note,r.revision
        FROM perspectives p JOIN imports i ON i.id=p.import_id
        JOIN calls c ON c.id=p.call_id LEFT JOIN observation_roles r ON r.perspective_id=p.id
        ORDER BY p.start DESC,p.id''')


def annotation(db, pid):
    row = db.execute('SELECT * FROM observation_roles WHERE perspective_id=?', (pid,)).fetchone()
    return dict(row) if row else None


def decorate(db, perspectives):
    roles = {r['perspective_id']: r for r in rows(db, 'SELECT * FROM observation_roles')}
    for p in perspectives:
        r = roles.get(p['id'])
        p['observation'] = r
        if r:
            p['label'] = f"{r['participant']} · {r['role']} · {r['node'] or p['label']}"
    return perspectives


def save(db, obj):
    pid = int(obj['perspective_id'])
    values = {}
    for field, limit in [('session', 160), ('participant', 120), ('role', 20), ('node', 120), ('note', 2000)]:
        value = obj.get(field, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError('Campo topologia non valido: ' + field)
        values[field] = value.strip()
    if not values['session'] or not values['participant'] or values['role'] not in ('app', 'xcoder', 'unknown'):
        raise ValueError('Sessione, partecipante e ruolo validi sono obbligatori')
    with db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM perspectives WHERE id=?', (pid,)).fetchone():
            raise ValueError('Prospettiva inesistente')
        old = annotation(db, pid)
        if int(obj.get('revision', 0)) != (old['revision'] if old else 0):
            raise ValueError('Associazione modificata: ricarica prima di salvare')
        revision = old['revision'] + 1 if old else 1
        db.execute('''INSERT INTO observation_roles(perspective_id,session,participant,role,node,note,revision)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(perspective_id) DO UPDATE SET
            session=excluded.session,participant=excluded.participant,role=excluded.role,
            node=excluded.node,note=excluded.note,revision=excluded.revision,updated_at=CURRENT_TIMESTAMP''',
            (pid, *(values[k] for k in ('session','participant','role','node','note')), revision))
    return annotation(db, pid)
