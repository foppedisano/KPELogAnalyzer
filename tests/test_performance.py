"""Synthetic performance invariants and non-destructive schema upgrade."""
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from app.db import connect, init
from app.perceptual import overlap, overlap_query, perspective, prepare
from app.parser import ingest
from tests.fixtures import sample, archive


class PerformanceTests(unittest.TestCase):
    def test_interval_integral_matches_reference(self):
        rng=random.Random(42)
        spans=[(rng.randrange(-100,100),rng.randrange(-100,100)) for _ in range(150)]
        spans += [(1000,2000),(1500,2500),(3000,3000)]
        fast=overlap_query(spans)
        for a in range(-120,3200,13):
            for length in (0,1,17,100,2000):
                self.assertEqual(fast(a,a+length),overlap(spans,a,a+length))
        self.assertEqual(overlap_query([])(0,100),0)

    def test_upgrade_backup_preservation_and_index_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.sqlite3'
            db=connect(path);init(db)
            ingest(db,archive(sample()),'synthetic.zip')
            db.execute('DROP INDEX event_import_time')
            db.execute("UPDATE meta SET value='12' WHERE key='schema_version'")
            db.execute("INSERT INTO conversations(title,note) VALUES('synthetic','preserve')")
            db.commit()
            before=[tuple(r) for r in db.execute('SELECT * FROM events')]
            init(db)
            self.assertEqual(before,[tuple(r) for r in db.execute('SELECT * FROM events')])
            self.assertEqual(db.execute('SELECT note FROM conversations').fetchone()[0],'preserve')
            self.assertEqual(db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'13')
            plan=' '.join(str(tuple(r)) for r in db.execute("EXPLAIN QUERY PLAN SELECT id FROM events WHERE import_id=1 AND ts>='2026-01-01' AND ts<'2026-01-02'"))
            self.assertIn('event_import_time',plan)
            backup=sqlite3.connect(str(path)+'.pre-v13.bak')
            self.assertEqual(backup.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'12')
            backup.close()
            init(db)  # Reopening never repeats the migration or overwrites the backup.
            p=db.execute('SELECT p.*,i.label,i.clock_offset FROM perspectives p JOIN imports i ON i.id=p.import_id LIMIT 1').fetchone()
            self.assertEqual(perspective(db,p),perspective(db,p,prepared=prepare(db,p)))
            # Unrelated events before/after the call must not make endpoint lookups
            # scan the source-time index instead of the exact-call index.
            db.executemany("INSERT INTO events(import_id,file_id,line_no,ts,kind,text) VALUES(1,1,1,?,'generic','synthetic unrelated')",
                           ((('2025' if i%2 else '2027')+'-01-01 00:00:00',) for i in range(15000)))
            db.execute("INSERT INTO metrics(event_id,ts,name,value,unit,direction,flow) VALUES(1,'2026-01-01 12:00:10','synthetic.unassigned',1,'raw','','')")
            db.commit()
            unclosed=dict(p);unclosed['end']=None
            steps=[0]
            def progress():
                steps[0]+=100
                return 0
            db.set_progress_handler(progress,100)
            perspective(db,unclosed)
            from app.catalog import catalog, CATALOG
            from app.call_events import query
            names={r['name'] for r in catalog(db,[p['call_id']])}
            self.assertNotIn('synthetic.unassigned',names)
            self.assertTrue({r['name'] for r in CATALOG}.issubset(names))
            query(db,p['call_id'])
            db.set_progress_handler(None,0)
            self.assertLess(steps[0],20000)
            db.close()
