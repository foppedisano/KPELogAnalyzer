"""Producer fingerprints and whole-call skipping; all identifiers synthetic."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import connect, init
from app.parser import ingest
from app.source_dedup import infer, pending, describe
from tests.fixtures import archive, sample, message, kpe, summary, rtcp
from tests import test_server

INSTANCE = '11111111-2222-4333-8444-555555555555'


def identified(cid='call-a', device='synthetic-device-a', instance=INSTANCE, extra=''):
    files = sample(cid)
    register = message(0, cid='registration', method='REGISTER').replace(
        'Content-Length: 0', f'Contact: <sip:alice@example.test>;+sip.instance="<urn:uid:{instance}>"\nContent-Length: 0')
    files['sip_debug.txt'] = register + files['sip_debug.txt']
    files['ios_hwwrapper.log'] = '[2026-01-01 12:00:00.000] synthetic marker\n'
    files['ctilib.log'] = ('[2026-01-01 12:00:00.000] [CTILIB] [INFO] '
                          'Sending auth to CTIServer - username: synthetic - OS: ios 1 - software: demo '
                          f'- device ID: {device} - pre-shared key: synthetic-only\n')
    files['extra.txt'] = extra
    return files


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'test.sqlite3'
        self.db = connect(self.path)
        init(self.db)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def load(self, files):
        return ingest(self.db, archive(files), 'synthetic.zip')

    def test_same_source_call_skipped_new_call_and_other_device_retained(self):
        first = self.load(identified())
        second = self.load(identified(extra='second export'))
        self.assertEqual((second['calls'], second['skipped_calls'], second['metrics']), (0,1,0))
        self.assertGreater(second['skipped_events'], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events WHERE import_id=? AND call_id IS NOT NULL',(second['id'],)).fetchone()[0],0)
        self.assertEqual(self.load(identified(cid='call-b'))['calls'],1)
        self.assertEqual(self.load(identified(device='synthetic-device-b'))['calls'],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM perspectives').fetchone()[0],3)
        identity=describe(self.db,first['id'])
        self.assertEqual(identity['status'],'resolved')
        self.assertTrue(all(e['event_id'] for e in identity['evidence']))
        self.assertNotIn(INSTANCE,json.dumps(identity))

    def test_unknown_gateway_is_kept_and_explicit_role_conflict_vetoes(self):
        self.load(identified())
        self.assertEqual(self.load(sample())['calls'],1)
        with self.db:
            self.db.execute("INSERT INTO observation_roles(perspective_id,session,participant,role,node,note,revision) VALUES(1,'demo','a','xcoder','','',1)")
        self.assertEqual(self.load(identified(extra='conflict'))['calls'],1)

    def test_source_is_not_inferred_from_remote_or_incomplete_evidence(self):
        files=identified()
        def direct(siptext, cti=None, names=None):
            return infer([dict(text=siptext,filename='sip_debug.txt',line_no=1),
                          dict(text=cti or files['ctilib.log'],filename='ctilib.log',line_no=1)],
                         names or files.keys())
        register=files['sip_debug.txt'].split('Content-Length: 0')[0]+'Content-Length: 0\n\n'
        self.assertEqual(direct(register)['status'],'resolved')
        for invalid in (register.replace('OUTGOING','INCOMING'),
                        register.replace('REGISTER sip:bob@example.test SIP/2.0','SIP/2.0 200 OK'),
                        register.replace('Contact:', 'Authorization:'),
                        register.replace('Contact:', '\nContact:'),
                        register.replace(INSTANCE, '00000000-0000-0000-0000-000000000000'),
                        register.replace(INSTANCE, 'broken')):
            with self.subTest(invalid=invalid[:40]):
                self.assertIsNone(direct(invalid)['producer_key'])
        self.assertIsNone(direct(register, names=['sip_debug.txt','ctilib.log'])['producer_key'])
        self.assertIsNone(direct(register,cti=files['ctilib.log']+files['ctilib.log'].replace('synthetic-device-a','other'))['producer_key'])
        self.assertIsNone(direct(register+register.replace(INSTANCE,'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'))['producer_key'])

    def test_reused_line_new_call_kept(self):
        self.load(identified())
        files=identified(extra='extended')
        files['kpelog.txt']+=kpe(30,'Call on lineId [ 0 ] with direction [ 2 ] added to the call list.')+summary(50,'call-b')
        files['rtplog.txt']+=rtcp(40)
        result=self.load(files)
        self.assertEqual((result['calls'],result['skipped_calls']),(1,1))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM metrics m JOIN events e ON e.id=m.event_id WHERE e.import_id=? AND m.name='rtcp.rtt'",(result['id'],)).fetchone()[0],1)

    def test_shared_device_block_keeps_other_line_and_unknown_records(self):
        from tests.test_enrichment import vd
        from tests.test_missing_packets import message as missing
        self.load(identified())
        files=identified(extra='mixed devices')
        files['kpelog.txt']+=kpe(0,'Call on lineId [ 1 ] with direction [ 2 ] added to the call list.')+summary(20,'call-b',1)
        files['VDlog.txt']=vd(5)+'Device name: NART0 of Line 1\nAudio currently in buffer (ms): 77\n'
        files['VDlog.txt']+=missing(line=0)+missing(line=1)+missing(line=9)
        result=self.load(files)
        values=list(self.db.execute('SELECT m.name,m.value,m.call_id FROM metrics m JOIN events e ON e.id=m.event_id WHERE e.import_id=? AND m.name LIKE \'vd.%\'',(result['id'],)))
        self.assertFalse(any(r['call_id']==1 for r in values))
        self.assertTrue(any(r['name']=='vd.buffer' and r['value']==77 and r['call_id']==2 for r in values))
        self.assertTrue(any(r['name']=='vd.missing_packets' and r['call_id'] is None for r in values))
        init(self.db)
        self.assertEqual(len(values),self.db.execute('SELECT COUNT(*) FROM metrics m JOIN events e ON e.id=m.event_id WHERE e.import_id=? AND m.name LIKE \'vd.%\'',(result['id'],)).fetchone()[0])

    def test_migration_preserves_old_copies_and_annotations_idempotently(self):
        self.load(identified())
        # Simulate the previous importer, which retained every export.
        with patch('app.source_dedup.previous',return_value={}):
            self.load(identified(extra='old export'))
        before=[tuple(r) for r in self.db.execute('SELECT * FROM events')]
        with self.db:
            self.db.execute('DELETE FROM import_producers')
            from tests.fixtures import remove_periodic_schema
            remove_periodic_schema(self.db)
            self.db.execute("UPDATE meta SET value='8' WHERE key='schema_version'")
        init(self.db)
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT * FROM events')],before)
        self.assertEqual([tuple(r)[:2] for r in self.db.execute('SELECT * FROM effective_duplicates')],[(2,1)])
        init(self.db)
        self.assertEqual(describe(self.db,2)['historical_duplicates'],1)
        backup=sqlite3.connect(str(self.path)+'.pre-v9.bak')
        try:self.assertEqual(backup.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'8')
        finally:backup.close()
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_import_rollback_and_zip_idempotence(self):
        self.load(identified())
        self.assertTrue(self.load(identified())['duplicate'])
        with patch('app.enrichment.enrich_import',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):self.load(identified(extra='rollback'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM imports').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM import_call_skips').fetchone()[0],0)


class SourceAPITests(unittest.TestCase):
    # Use the shared API harness without duplicating its inherited tests.
    setUp=test_server.APITests.setUp
    tearDown=test_server.APITests.tearDown
    request=test_server.APITests.request
    upload=test_server.APITests.upload
    def test_sources_and_historical_chart_filter(self):
        self.upload(identified())
        with patch('app.source_dedup.previous',return_value={}):
            self.upload(identified(extra='historical'))
        from app.source_dedup import refresh_duplicates
        db=connect()
        with db:
            identity=dict(db.execute('SELECT * FROM import_producers WHERE import_id=2').fetchone())
            refresh_duplicates(db,2,identity)
        db.close()
        for name in ('rtcp.rtt','derived.mos_reference'):
            normal=self.request('GET','/api/metrics?calls=1&name='+name)[1]
            all_copies=self.request('GET','/api/metrics?calls=1&name='+name+'&duplicates=1')[1]
            self.assertTrue(normal)
            self.assertEqual(len(all_copies),2*len(normal))
        sources=self.request('GET','/api/imports')[1]
        self.assertEqual(sources[0]['producer']['historical_duplicates'],1)
        self.upload(identified(extra='new export'))
        self.assertEqual(self.request('GET','/api/imports')[1][0]['producer']['skipped_calls'],1)
