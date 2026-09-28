"""Dependency-free HTTP service, bound to loopback outside Docker."""
import csv
import io
import json
import math
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .db import connect, init, rows
from .parser import MAX_ZIP, PARSER_VERSION, ingest, sip
from .catalog import catalog, CATALOG
from .metric_context import annotate as annotate_metrics, options as metric_options
from .single_metrics import SINGLE_DERIVED, calculate
from .diagnostics import diagnostics
from .manual import import_text, manual_window
from .identity import candidates as identity_candidates, confirm as confirm_identity
from .topology import listing as topology_listing, save as topology_save, decorate
from .analyses import save as save_analysis

STATIC = Path(__file__).parent / 'static'
IMPORT_LOCK = threading.Lock()


def readonly_query(db, sql):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 20000:
        raise ValueError('Query mancante o troppo lunga')
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
    def authorize(action, arg1, arg2, *_):
        if action not in allowed or (action == sqlite3.SQLITE_FUNCTION and (arg2 or '').lower() in ('load_extension','readfile','writefile')):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    deadline = time.monotonic() + 3
    db.set_authorizer(authorize)
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        cursor = db.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        result = [list(r) for r in cursor.fetchmany(1001)]
        # Bound response size even if a query generates very large strings.
        if len(json.dumps(result)) > 4 * 1024 * 1024:
            raise ValueError('Risultato troppo grande; restringi la query')
        return dict(columns=columns, rows=result[:1000], truncated=len(result)>1000)
    finally:
        db.set_authorizer(None)
        db.set_progress_handler(None, 0)


class Handler(BaseHTTPRequestHandler):
    server_version = 'KPELogAnalyzer/1.0'

    def log_message(self, fmt, *args):
        # Avoid printing query text / SIP identifiers to server logs.
        pass

    def send(self, obj, status=200, mime='application/json; charset=utf-8', filename=None):
        if not isinstance(obj, bytes):
            obj = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(obj)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(obj)

    def do_GET(self):
        self.route('GET')

    def do_POST(self):
        self.route('POST')

    def do_PATCH(self):
        self.route('PATCH')

    def route(self, method):
        db = None
        try:
            # Local service: reject foreign browser origins and DNS-rebinding hosts.
            host = self.headers.get('Host','').split(':')[0].lower()
            if host not in ('localhost', '127.0.0.1'):
                return self.send({'error':'Host non consentito; usa localhost o 127.0.0.1'},403)
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host',''):
                return self.send({'error':'Origine non consentita'},403)
            parsed = urlparse(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            def q(key, default=''):
                return query.get(key,[default])[0]
            if method == 'GET' and not path.startswith('/api/'):
                mapping = {'/analytics-ui.js':'analytics-ui.js','/':'index.html','/app.js':'app.js','/call-chart.js':'call-chart.js','/geography.js':'geography.js','/basemap.json':'basemap.json','/mos.js':'mos.js','/diagnostics.js':'diagnostics.js','/analysis-ui.js':'analysis-ui.js','/topology.js':'topology.js','/conversations.js':'conversations.js','/style.css':'style.css'}
                if path not in mapping:
                    return self.send({'error':'Non trovato'},404)
                filename = mapping[path]
                mime = {'html':'text/html','js':'text/javascript','css':'text/css','json':'application/json'}[filename.rsplit('.',1)[1]]
                return self.send((STATIC/filename).read_bytes(),mime=mime+'; charset=utf-8')
            db = connect()
            if method == 'GET':
                if path.startswith('/api/analytics/'):
                    from . import analytics
                    handlers={'catalog':analytics.catalog,'coverage':analytics.coverage,'recipes':analytics.recipes}
                    name=path.removeprefix('/api/analytics/')
                    if name in handlers:return self.send(handlers[name](db))
                if path == '/api/map-tile':
                    from .map_tiles import tile
                    return self.send(tile(q('z'),q('x'),q('y'),self.headers.get('Referer','http://127.0.0.1:8080/')),mime='image/png')
                if path == '/api/geography':
                    from .geography import aggregate
                    return self.send(aggregate(db,{k:q(k) for k in ('cell','direction','quality','start','end','platform','access','upstream','operator') if q(k)}))
                if path == '/api/telemetry':
                    from .telemetry_store import status
                    return self.send(status(db))
                if path == '/api/mos':
                    from .mos import analysis
                    return self.send(analysis(db,int(q('local')),int(q('peer')) if q('peer') else None,q('local_role','app')))
                if path == '/api/topology':
                    return self.send(topology_listing(db))
                if path == '/api/saved-analyses':
                    return self.send(rows(db,'SELECT * FROM saved_analyses ORDER BY updated_at DESC,id DESC'))
                if path == '/api/identities':
                    return self.send(identity_candidates(db,int(q('import'))))
                if path == '/api/windows':
                    return self.send(rows(db,"SELECT p.*,c.caller title FROM perspectives p JOIN calls c ON c.id=p.call_id WHERE c.call_key LIKE 'manual:%' ORDER BY p.start"))
                if path == '/api/window-history':
                    return self.send(rows(db,'SELECT * FROM window_revisions WHERE perspective_id=? ORDER BY id DESC',(int(q('perspective')),)))
                if path == '/api/catalog':
                    return self.send(catalog(db))
                if path == '/api/diagnostics':
                    thresholds = [float(q('rtt_threshold','200')),float(q('buffer_threshold','500'))]
                    if any(not math.isfinite(x) or x < 0 for x in thresholds):
                        raise ValueError('Soglie finite e non negative richieste')
                    return self.send(diagnostics(db,int(q('a')),int(q('b')) if q('b') else None,q('device_a','NART0 of Line 0'),q('device_b','NART0 of Line 0'),*thresholds,start=q('start') or None,end=q('end') or None,offset_a=float(q('offset_a')) if q('offset_a') else None,offset_b=float(q('offset_b')) if q('offset_b') else None))
                if path == '/api/devices':
                    return self.send(rows(db,"SELECT DISTINCT perspective_id,device FROM metrics WHERE device<>'' AND perspective_id IS NOT NULL ORDER BY perspective_id,device"))
                if path == '/api/health':
                    return self.send({'ok':True,'parser_version':PARSER_VERSION})
                if path == '/api/overview':
                    counts = {t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('imports','calls','events','metrics')}
                    counts['unassigned_metrics'] = db.execute('SELECT COUNT(*) FROM metrics WHERE call_id IS NULL').fetchone()[0]
                    counts['invalid_metrics'] = db.execute('SELECT COUNT(*) FROM metrics WHERE valid=0').fetchone()[0]
                    return self.send(counts)
                if path == '/api/conversation-groups':
                    from .conversation_discovery import groups
                    return self.send(groups(db))
                if path == '/api/imports':
                    from .source_dedup import describe
                    from .conversation_discovery import profiles
                    source = profiles(db)
                    data = rows(db, '''WITH first_seen AS (
                        SELECT call_id,MIN(import_id) first_import FROM perspectives GROUP BY call_id
                    ), counts AS (
                        SELECT p.import_id,COUNT(DISTINCT p.call_id) call_count,
                            COUNT(DISTINCT CASE WHEN p.import_id=f.first_import THEN p.call_id END) new_call_count
                        FROM perspectives p JOIN first_seen f ON f.call_id=p.call_id GROUP BY p.import_id
                    ) SELECT i.*,COALESCE(c.call_count,0) call_count,
                        COALESCE(c.new_call_count,0) new_call_count,
                        COALESCE(c.call_count-c.new_call_count,0) existing_call_count
                    FROM imports i LEFT JOIN counts c ON c.import_id=i.id ORDER BY i.id DESC''')
                    return self.send([dict(r,source_profile=source.get(r['id'],{}),producer=describe(db,r['id'])) for r in data])
                if path == '/api/files':
                    return self.send(rows(db,'SELECT f.*,i.label FROM files f JOIN imports i ON i.id=f.import_id ORDER BY f.import_id,f.name'))
                if path == '/api/calls':
                    from .mos import call_summary
                    calls = rows(db,"""SELECT c.*, (SELECT COUNT(*) FROM perspectives p WHERE p.call_id=c.id) perspectives,
                        (SELECT COUNT(*) FROM metrics m WHERE m.call_id=c.id) metrics,
                        (SELECT group_concat(DISTINCT status) FROM perspectives p WHERE p.call_id=c.id) status
                        FROM calls c WHERE c.caller LIKE ? OR c.callee LIKE ? OR COALESCE(c.sip_call_id,'') LIKE ?
                        ORDER BY c.start DESC LIMIT 2000""", ('%'+q('search')+'%',)*3)
                    return self.send([dict(c,mos=call_summary(db,c['id'])) for c in calls])
                if path == '/api/perspectives':
                    return self.send(decorate(db,rows(db,'''SELECT p.*,i.label,i.clock_offset,
                        (SELECT version FROM app_versions v WHERE v.import_id=p.import_id AND v.ts<=p.start ORDER BY v.ts DESC,v.event_id DESC LIMIT 1) app_version,
                        (SELECT event_id FROM app_versions v WHERE v.import_id=p.import_id AND v.ts<=p.start ORDER BY v.ts DESC,v.event_id DESC LIMIT 1) version_event_id
                        FROM perspectives p JOIN imports i ON i.id=p.import_id ORDER BY p.start DESC''')))
                if path == '/api/analysis':
                    cid = int(q('call'))
                    summary = rows(db,"""SELECT m.perspective_id,i.label,m.name,m.direction,m.unit,
                        COUNT(*) samples,MIN(m.value) minimum,AVG(m.value) mean,MAX(m.value) maximum
                        FROM metrics m JOIN perspectives p ON p.id=m.perspective_id JOIN imports i ON i.id=p.import_id
                        WHERE m.call_id=? AND m.valid=1 AND m.name IN ('rtcp.rtt','rtcp.jitter','rtcp.loss')
                        GROUP BY m.perspective_id,m.name,m.direction,m.unit ORDER BY m.perspective_id,m.name,m.direction""",(cid,))
                    invalid = db.execute('SELECT COUNT(*) FROM metrics WHERE call_id=? AND valid=0',(cid,)).fetchone()[0]
                    errors = db.execute("SELECT COUNT(*) FROM events WHERE call_id=? AND level IN ('ERROR','FATAL')",(cid,)).fetchone()[0]
                    signaling=[]
                    for event in rows(db,"""SELECT e.id,e.ts,e.text,e.perspective_id,f.name filename,e.line_no,i.label
                        FROM events e JOIN files f ON f.id=e.file_id JOIN imports i ON i.id=e.import_id
                        WHERE e.call_id=? AND e.kind='sip' ORDER BY e.ts,e.id LIMIT 501""",(cid,)):
                        decoded=sip(event.pop('text'))
                        if decoded:
                            event.update(decoded);signaling.append(event)
                    return self.send(dict(summary=summary,invalid_metrics=invalid,error_events=errors,signaling=signaling[:500],truncated=len(signaling)>500))
                if path == '/api/events':
                    clauses,args = [],[]
                    for key,column in [('call','e.call_id'),('file','e.file_id'),('import','e.import_id'),('perspective','e.perspective_id')]:
                        if q(key):
                            clauses.append(column+'=?'); args.append(int(q(key)))
                    if q('search'):
                        clauses.append('e.text LIKE ?'); args.append('%'+q('search')+'%')
                    if q('level'):
                        clauses.append('e.level=?');args.append(q('level'))
                    if q('unassigned') == '1':
                        clauses.append('e.call_id IS NULL')
                    where = ' WHERE '+' AND '.join(clauses) if clauses else ''
                    offset = max(0,int(q('offset','0')))
                    events = rows(db,'SELECT e.*,f.name filename FROM events e JOIN files f ON f.id=e.file_id'+where+' ORDER BY e.ts,e.id LIMIT 101 OFFSET ?', (*args,offset))
                    return self.send(dict(events=events[:100], more=len(events)>100, offset=offset))
                if path == '/api/metric-names':
                    data=rows(db,'SELECT name,unit,statistic,COUNT(*) samples FROM metrics GROUP BY name,unit,statistic ORDER BY name,statistic')
                    known={m['name'] for m in data}
                    for metric in CATALOG:
                        if metric['name'] not in known and metric['name'] not in ('derived.buffer_sum','derived.dejitter_sum'):
                            data.append(dict(name=metric['name'],unit=metric['unit'],statistic='sample',samples=0,calculated=metric['name'] in SINGLE_DERIVED))
                    return self.send(data)
                if path == '/api/metric-options':
                    ids=[int(x) for x in q('calls').split(',') if x]
                    if not ids or len(ids)>20: raise ValueError('Seleziona da 1 a 20 chiamate')
                    return self.send(metric_options(db,ids,catalog(db)))
                if path == '/api/metrics':
                    from .source_dedup import filter_duplicates
                    ids = [int(x) for x in q('calls').split(',') if x]
                    if not ids or len(ids)>20:
                        raise ValueError('Seleziona da 1 a 20 chiamate')
                    where = f"m.call_id IN ({','.join('?' for _ in ids)}) AND m.name=? AND m.statistic=?"
                    args = [*ids,q('name','rtcp.rtt'),q('statistic','sample')]
                    if q('duplicates') != '1':
                        where += ' AND m.perspective_id NOT IN (SELECT perspective_id FROM effective_duplicates)'
                    if q('direction'):
                        if q('direction') not in ('incoming','outgoing','roundtrip','combined'): raise ValueError('Direzione non valida')
                        where+=' AND m.direction=?'
                        args.append(q('direction'))
                    if q('invalid') != '1':
                        where += ' AND m.valid=1'
                    data = rows(db,f'''SELECT m.*,i.label,i.clock_offset,p.start,p.line_id,f.name filename,COALESCE(m.source_line,e.line_no) line_no
                        FROM metrics m JOIN perspectives p ON p.id=m.perspective_id JOIN imports i ON i.id=p.import_id
                        JOIN events e ON e.id=m.event_id JOIN files f ON f.id=e.file_id
                        WHERE {where} ORDER BY m.ts,m.id LIMIT 100001''',args)
                    if q('name') in SINGLE_DERIVED:
                        data=calculate(db,ids,q('name')) if q('statistic','sample')=='sample' else []
                        if q('direction'): data=[m for m in data if m['direction']==q('direction')]
                        if q('duplicates') != '1': data=filter_duplicates(db,data)
                    annotate_metrics(db,data)
                    if len(data)>100000:
                        raise ValueError('Oltre 100.000 campioni: restringi la selezione')
                    if q('format')=='csv':
                        out = io.StringIO()
                        if data:
                            writer = csv.DictWriter(out,fieldnames=list(dict.fromkeys(k for row in data for k in row)));writer.writeheader()
                            for row in data:
                                # Protect spreadsheet formula evaluation in user-controlled text.
                                writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items()})
                        return self.send(out.getvalue().encode('utf-8-sig'),mime='text/csv; charset=utf-8',filename='metrics.csv')
                    return self.send(data)
                if path == '/api/conversations':
                    return self.send(rows(db,'''SELECT c.*, (SELECT group_concat(call_id) FROM conversation_calls WHERE conversation_id=c.id) call_ids
                        FROM conversations c ORDER BY c.id DESC'''))
                if path == '/api/database':
                    snapshot = sqlite3.connect(':memory:')
                    try:
                        db.backup(snapshot)
                        # A WAL-mode header cannot be reopened as an independent in-memory image.
                        blob = bytearray(snapshot.serialize())
                        blob[18:20] = b'\x01\x01'
                        return self.send(bytes(blob),mime='application/vnd.sqlite3',filename='kpe.sqlite3')
                    finally:
                        snapshot.close()
                return self.send({'error':'API non trovata'},404)
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('Transfer-Encoding non supportato')
            length = int(self.headers.get('Content-Length','0'))
            limit = MAX_ZIP if path in ('/api/imports','/api/text-import') else 64000
            if length<=0 or length>limit:
                return self.send({'error':f'Corpo richiesta mancante o oltre {limit} byte'},413)
            self.connection.settimeout(60)
            body = self.rfile.read(length)
            if len(body)!=length:
                raise ValueError('Upload incompleto')
            if method=='POST' and path=='/api/imports':
                name = unquote(self.headers.get('X-Filename','upload.zip'))[:240]
                label = unquote(self.headers.get('X-Label',''))[:120]
                with IMPORT_LOCK:
                    return self.send(ingest(db,body,name,label),201)
            obj = json.loads(body)
            if path.startswith('/api/analytics/'):
                from . import analytics
                name=path.removeprefix('/api/analytics/')
                if method=='POST' and name in ('query','evidence','run-recipe'):
                    handler={'query':analytics.query,'evidence':analytics.evidence,'run-recipe':analytics.run_recipe}[name]
                    return self.send(handler(db,obj))
                if method in ('POST','PATCH') and name=='recipes':
                    return self.send(analytics.save_recipe(db,obj,update=method=='PATCH'),201 if method=='POST' else 200)
            if method=='POST' and path=='/api/topology':
                with IMPORT_LOCK:
                    return self.send(topology_save(db,obj))
            if method in ('POST','PATCH') and path=='/api/saved-analyses':
                return self.send(save_analysis(db,obj,update=method=='PATCH'),201 if method=='POST' else 200)
            if method=='POST' and path=='/api/identities':
                with IMPORT_LOCK:
                    return self.send(confirm_identity(db,obj))
            if method=='PATCH' and path=='/api/windows':
                with IMPORT_LOCK:
                    return self.send(manual_window(db,obj,edit=True))
            if method=='POST' and path=='/api/text-import':
                with IMPORT_LOCK:
                    return self.send(import_text(db,obj),201)
            if method=='POST' and path=='/api/windows':
                with IMPORT_LOCK:
                    return self.send(manual_window(db,obj),201)
            if method=='POST' and path=='/api/query':
                db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 4*1024*1024)
                return self.send(readonly_query(db,obj.get('sql','')))
            if method=='PATCH' and path=='/api/imports':
                offset = float(obj.get('clock_offset',0))
                if not math.isfinite(offset) or abs(offset)>86400:
                    raise ValueError('Correzione orologio: massimo ±86400 secondi')
                with db:
                    result = db.execute('UPDATE imports SET label=?,clock_offset=? WHERE id=?',(str(obj['label'])[:120],offset,int(obj['id'])))
                    if not result.rowcount:
                        raise ValueError('Importazione non trovata')
                return self.send({'ok':True})
            if method=='POST' and path=='/api/conversations':
                ids = sorted(set(int(x) for x in obj.get('call_ids',[])))
                title = str(obj.get('title','')).strip()[:200]
                host = int(obj['host_perspective_id']) if obj.get('host_perspective_id') else None
                if not title or not 2<=len(ids)<=20:
                    raise ValueError('Servono un titolo e da 2 a 20 chiamate')
                marks = ','.join('?' for _ in ids)
                if db.execute(f'SELECT COUNT(*) FROM calls WHERE id IN ({marks})',ids).fetchone()[0]!=len(ids):
                    raise ValueError('Chiamata non trovata')
                if host and not db.execute(f'SELECT 1 FROM perspectives WHERE id=? AND call_id IN ({marks})',[host,*ids]).fetchone():
                    raise ValueError('L’host deve appartenere alle chiamate selezionate')
                with db:
                    cid = db.execute('INSERT INTO conversations(title,host_perspective_id,note) VALUES(?,?,?)',(title,host,str(obj.get('note',''))[:2000])).lastrowid
                    db.executemany('INSERT INTO conversation_calls VALUES(?,?)',[(cid,c) for c in ids])
                return self.send({'id':cid},201)
            return self.send({'error':'API non trovata'},404)
        except (ValueError,KeyError,TypeError,sqlite3.Error) as exc:
            self.send({'error':str(exc)},400)
        except (BrokenPipeError,ConnectionResetError,TimeoutError):
            pass
        except Exception:
            import traceback
            traceback.print_exc()
            self.send({'error':'Errore interno; consulta il log del servizio'},500)
        finally:
            if db:
                db.close()


def main():
    db = connect();init(db);db.close()
    host, port = os.environ.get('KPE_HOST','127.0.0.1'),int(os.environ.get('KPE_PORT','8080'))
    server = ThreadingHTTPServer((host,port),Handler)
    print(f'KPELogAnalyzer: http://{host}:{port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
