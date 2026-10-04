import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO meta VALUES('schema_version','1');
CREATE TABLE IF NOT EXISTS imports(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT UNIQUE NOT NULL,
 label TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 file_count INTEGER DEFAULT 0, event_count INTEGER DEFAULT 0, warnings TEXT DEFAULT '[]',
 clock_offset REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS files(
 id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES imports(id),
 name TEXT NOT NULL, size INTEGER NOT NULL, parser TEXT NOT NULL,
 first_ts TEXT, last_ts TEXT, records INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS calls(
 id INTEGER PRIMARY KEY, call_key TEXT UNIQUE NOT NULL, sip_call_id TEXT,
 caller TEXT DEFAULT '', callee TEXT DEFAULT '', start TEXT, end TEXT, connected TEXT);
CREATE TABLE IF NOT EXISTS perspectives(
 id INTEGER PRIMARY KEY, call_id INTEGER NOT NULL REFERENCES calls(id),
 import_id INTEGER NOT NULL REFERENCES imports(id), line_id INTEGER,
 start TEXT, end TEXT, connected TEXT, direction TEXT DEFAULT 'unknown',
 status TEXT DEFAULT 'partial', evidence TEXT, UNIQUE(call_id, import_id));
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES imports(id),
 file_id INTEGER NOT NULL REFERENCES files(id), line_no INTEGER NOT NULL,
 ts TEXT, level TEXT, kind TEXT NOT NULL, text TEXT NOT NULL,
 call_id INTEGER REFERENCES calls(id), perspective_id INTEGER REFERENCES perspectives(id),
 line_id INTEGER);
CREATE TABLE IF NOT EXISTS metrics(
 id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES events(id),
 perspective_id INTEGER REFERENCES perspectives(id), call_id INTEGER REFERENCES calls(id),
 ts TEXT NOT NULL, name TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL,
 direction TEXT NOT NULL, flow TEXT NOT NULL, ssrc TEXT DEFAULT '',
 statistic TEXT DEFAULT 'sample', valid INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS conversations(
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, host_perspective_id INTEGER REFERENCES perspectives(id),
 note TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS conversation_calls(
 conversation_id INTEGER REFERENCES conversations(id), call_id INTEGER REFERENCES calls(id),
 PRIMARY KEY(conversation_id, call_id));
CREATE INDEX IF NOT EXISTS event_call_ts ON events(call_id, ts);
CREATE INDEX IF NOT EXISTS event_file ON events(file_id,line_no);
CREATE INDEX IF NOT EXISTS metric_call ON metrics(call_id,name,ts);
CREATE INDEX IF NOT EXISTS perspective_import ON perspectives(import_id);
"""


def path():
    return Path(os.environ.get('KPE_DATA_DIR', 'data')) / 'kpe.sqlite3'


def connect(db_path=None):
    p = Path(db_path) if db_path else path()
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return db


def init(db):
    db.executescript(SCHEMA)
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version not in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'):
        raise RuntimeError('Unsupported database schema; back up the database before upgrading')
    if version == '1':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v2.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename it before retrying migration')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        with db:
            db.execute('BEGIN IMMEDIATE')
            for definition in ("device TEXT DEFAULT ''", "source_line INTEGER", "raw_value REAL", "raw_unit TEXT", "sample_kind TEXT DEFAULT 'sample'", "extractor TEXT DEFAULT 'legacy'"):
                db.execute('ALTER TABLE metrics ADD COLUMN ' + definition)
            db.execute('CREATE TABLE app_versions(event_id INTEGER PRIMARY KEY REFERENCES events(id), import_id INTEGER REFERENCES imports(id), ts TEXT NOT NULL, app_name TEXT, version TEXT)')
            db.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '2':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v3.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("CREATE TABLE saved_analyses(id INTEGER PRIMARY KEY,title TEXT NOT NULL,config TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE source_identities(import_id INTEGER PRIMARY KEY REFERENCES imports(id),name TEXT NOT NULL,account TEXT NOT NULL DEFAULT '',note TEXT NOT NULL DEFAULT '',evidence TEXT NOT NULL DEFAULT '[]',updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE window_revisions(id INTEGER PRIMARY KEY,perspective_id INTEGER NOT NULL REFERENCES perspectives(id),snapshot TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("UPDATE meta SET value='3' WHERE key='schema_version'")
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '3':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v4.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("""CREATE TABLE observation_roles(
                perspective_id INTEGER PRIMARY KEY REFERENCES perspectives(id),
                session TEXT NOT NULL, participant TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('app','xcoder','unknown')),
                node TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
                revision INTEGER NOT NULL DEFAULT 1, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("UPDATE meta SET value='4' WHERE key='schema_version'")
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '4':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v5.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE source_profiles(import_id INTEGER PRIMARY KEY REFERENCES imports(id),profile TEXT NOT NULL)')
            db.execute('''CREATE TABLE call_correlations(event_id INTEGER NOT NULL REFERENCES events(id),
                call_id INTEGER NOT NULL REFERENCES calls(id),uuid TEXT NOT NULL,source_line INTEGER NOT NULL,
                PRIMARY KEY(event_id,uuid))''')
            db.execute('CREATE INDEX correlation_uuid ON call_correlations(uuid,call_id)')
            db.execute('''CREATE TABLE leg_outcomes(event_id INTEGER PRIMARY KEY REFERENCES events(id),
                perspective_id INTEGER NOT NULL REFERENCES perspectives(id),outcome TEXT NOT NULL)''')
            db.execute("UPDATE meta SET value='5' WHERE key='schema_version'")
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '5':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v6.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename it before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        from .geography import SCHEMA as GEO_SCHEMA
        try:
            db.executescript("BEGIN IMMEDIATE;" + GEO_SCHEMA + "UPDATE meta SET value='6' WHERE key='schema_version'; COMMIT;")
        except Exception:
            db.rollback()
            raise
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '6':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v7.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename it before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        from .mobility import SCHEMA as MOBILITY_SCHEMA
        try:
            db.executescript("BEGIN IMMEDIATE;" + MOBILITY_SCHEMA + "UPDATE meta SET value='7' WHERE key='schema_version'; COMMIT;")
        except Exception:
            db.rollback()
            raise
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '7':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v8.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        from .telemetry_store import SCHEMA as TELEMETRY_SCHEMA
        try:
            db.executescript("BEGIN IMMEDIATE;" + TELEMETRY_SCHEMA + "UPDATE meta SET value='8' WHERE key='schema_version'; COMMIT;")
        except Exception:
            db.rollback()
            raise
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '8':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v9.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        from .source_dedup import SCHEMA as SOURCE_SCHEMA
        try:
            db.executescript("BEGIN IMMEDIATE;" + SOURCE_SCHEMA + "UPDATE meta SET value='9' WHERE key='schema_version'; COMMIT;")
        except Exception:
            db.rollback()
            raise
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '9':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v10.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        from .analytics import SCHEMA as ANALYTICS_SCHEMA
        try:
            db.executescript("BEGIN IMMEDIATE;" + ANALYTICS_SCHEMA + "UPDATE meta SET value='10' WHERE key='schema_version'; COMMIT;")
        except Exception:
            db.rollback()
            raise
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '10':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v11.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        from .periodic import SCHEMA as PERIODIC_SCHEMA
        try:
            db.executescript("BEGIN IMMEDIATE;" + PERIODIC_SCHEMA + "UPDATE meta SET value='11' WHERE key='schema_version'; COMMIT;")
        except Exception:
            db.rollback()
            raise
    version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    if version == '11':
        filename = db.execute('PRAGMA database_list').fetchone()[2]
        if filename and db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]:
            backup = Path(filename).with_name(Path(filename).name + '.pre-v12.bak')
            if backup.exists():
                raise RuntimeError(f'Backup already exists: {backup}; preserve or rename before upgrading')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
            finally:
                target.close()
        from .connectivity import SCHEMA as CONNECTIVITY_SCHEMA
        try:
            db.executescript("BEGIN IMMEDIATE;" + CONNECTIVITY_SCHEMA + "UPDATE meta SET value='12' WHERE key='schema_version'; COMMIT;")
        except Exception:
            db.rollback()
            raise
    from .enrichment import enrich_pending
    enrich_pending(db)
    from .geography import pending
    pending(db)
    from .mobility import pending as mobility_pending
    mobility_pending(db)
    from .telemetry_store import pending as telemetry_pending
    telemetry_pending(db)
    from .source_dedup import pending as source_pending
    source_pending(db)
    from .connectivity import pending as connectivity_pending
    connectivity_pending(db)


def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]
