import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db import connect, init, rows
from app.parser import ingest, records, read_zip
from app.server import readonly_query
from tests.fixtures import archive, sample, message, rtcp, kpe, summary


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.temp.name)/'test.sqlite3')
        init(self.db)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def load(self, files=None):
        return ingest(self.db,archive(files or sample()),'synthetic.zip')

    def test_lifecycle_and_metric_provenance(self):
        result=self.load()
        self.assertEqual(result['calls'],1)
        self.assertEqual(result['metrics'],7)
        p=rows(self.db,'SELECT * FROM perspectives')[0]
        self.assertEqual(p['status'],'completed')
        self.assertEqual(p['direction'],'outgoing')
        self.assertEqual(p['line_id'],0)
        self.assertEqual(result['unassigned_metrics'],0)
        m=rows(self.db,"SELECT m.*,f.name filename,e.line_no FROM metrics m JOIN events e ON e.id=m.event_id JOIN files f ON f.id=e.file_id WHERE m.name='rtcp.rtt'")[0]
        self.assertEqual((m['value'],m['unit'],m['filename'],m['line_no']),(42.25,'ms','rtplog.txt',1))
        raw=rows(self.db,"SELECT value,unit FROM metrics WHERE name='kpe.common.rtt'")[0]
        self.assertEqual(raw,{'value':42250.0,'unit':'raw'})

    def test_negative_values_preserved_but_invalid(self):
        self.load()
        m=rows(self.db,'SELECT value,valid FROM metrics WHERE value<0')
        self.assertEqual(m,[{'value':-42000.0,'valid':0}])

    def test_identical_zip_is_idempotent(self):
        data=archive(sample())
        first=ingest(self.db,data,'one.zip')
        second=ingest(self.db,data,'renamed.zip')
        self.assertEqual(first['id'],second['id'])
        self.assertTrue(second['duplicate'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM imports').fetchone()[0],1)

    def test_same_call_two_devices_keep_metrics_separate(self):
        self.load(sample())
        self.load(sample(direction='INCOMING'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM perspectives').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT COUNT(DISTINCT perspective_id) FROM metrics').fetchone()[0],2)

    def test_different_call_ids_not_merged_by_time(self):
        self.load(sample())
        self.load(sample(cid='call-b'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0],0)

    def test_registration_does_not_become_call(self):
        result=self.load({'sip_debug.txt':message(1,method='REGISTER')+message(2,method='REGISTER',response=200)})
        self.assertEqual(result['calls'],0)

    def test_failed_invite_does_not_connect(self):
        self.load({'sip_debug.txt':message(0)+message(2,response=486)})
        p=rows(self.db,'SELECT * FROM perspectives')[0]
        self.assertEqual(p['status'],'failed')
        self.assertIsNone(p['connected'])

    def test_auth_challenge_then_success_not_failed(self):
        self.load({'sip_debug.txt':message(0)+message(1,response=401)+message(2,response=200)+message(20,method='BYE')})
        self.assertEqual(rows(self.db,'SELECT status FROM perspectives')[0]['status'],'completed')

    def test_reused_line_assigns_correct_call(self):
        files=sample()
        files['kpelog.txt']+=kpe(30,'Call on lineId [ 0 ] with direction [ 2 ] added to the call list.')+summary(50,'call-b')
        files['rtplog.txt']+=rtcp(40)
        self.load(files)
        actual=rows(self.db,"SELECT c.sip_call_id,m.ts FROM metrics m JOIN calls c ON c.id=m.call_id WHERE m.name='rtcp.rtt' ORDER BY m.ts")
        self.assertEqual([a['sip_call_id'] for a in actual],['call-a','call-b'])

    def test_rotations_do_not_duplicate_derived_metrics(self):
        files=sample();files['rtplog-1.txt']=files['rtplog.txt'];files['kpelog-1.txt']=files['kpelog.txt']
        result=self.load(files)
        self.assertEqual(result['calls'],1)
        self.assertEqual(result['metrics'],7)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events e JOIN files f ON f.id=e.file_id WHERE f.name LIKE 'rtplog%' ").fetchone()[0],2)

    def test_unmapped_metrics_not_guessed_from_time(self):
        self.load({'sip_debug.txt':message(0)+message(20,method='BYE'),'rtplog.txt':rtcp()})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM metrics WHERE call_id IS NULL').fetchone()[0],6)

    def test_terminated_line_without_summary_does_not_swallow_future_metrics(self):
        result=self.load({'kpelog.txt':kpe(0,'Call on lineId [ 0 ] with direction [ 2 ] added to the call list.')+kpe(20,'Call on lineId [ 0 ] removed from list.'),'rtplog.txt':rtcp(10)+rtcp(40)})
        self.assertEqual(result['unassigned_metrics'],6)

    def test_malformed_summary_shape_is_reported_not_fatal(self):
        result=self.load({'kpelog.txt':kpe(20,'Info about call finished on line 0 : {"callInfo": []}')})
        self.assertEqual(result['calls'],0)
        self.assertTrue(result['warnings'])

    def test_truncated_and_invalid_utf8_kept(self):
        result=self.load({'CallInfo.log':b'"avg": "1"\n\xff\n2026-01-01 12:00:00.000 [info] : truncated {\n'})
        self.assertEqual(result['calls'],0)
        self.assertTrue(result['warnings'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events WHERE ts IS NULL').fetchone()[0],1)

    def test_crcrlf_and_resip_timestamps(self):
        rs=list(records(message(0).replace('\n','\r\r\n')+message(2).replace('\n','\r\r\n')))
        self.assertEqual(len(rs),2)
        self.assertEqual(rs[1][0],10)
        rs=list(records('INFO | 20260101-120001.123 | RESIP | hello\nINFO | 20260101-120002.456 | RESIP | world'))
        self.assertEqual(len(rs),2)
        self.assertEqual(rs[0][1],'2026-01-01 12:00:01.123000')

    def test_unsafe_and_malformed_zip_rejected_atomically(self):
        for data in [b'not zip'] + [archive({'safe.log': 'synthetic', name: 'x'}) for name in (
            '../evil.log', 'C:/evil.log', 'C:evil.log', '/evil.log',
            '..\\evil.log', '\\\\server\\share\\evil.log', 'safe.log:stream.log',
            '../kpelog-2025-01-27T17:06:17.txt',
            'C:/kpelog-2025-01-27T17:06:17.txt',
            'folder:stream/kpelog-2025-01-27T17:06:17.txt',
            'kpelog-2025-01-27T17:06:17.txt:stream.log',
        )]:
            with self.assertRaises(ValueError):
                ingest(self.db,data,'bad.zip')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM imports').fetchone()[0],0)

    def test_android_timestamped_rotation_names_preserve_provenance(self):
        files = {
            'kpelog-2025-01-27T17:06:17.txt': '2025-01-27 17:06:17 synthetic rotation',
            'logs/ctilib-2025-01-27T16:12:22.log': 'synthetic fragment',
        }
        data = archive(files)
        contents, warnings = read_zip(data)
        self.assertEqual({name: text for name, size, text in contents}, files)
        self.assertEqual(warnings, [])
        result = ingest(self.db, data, 'synthetic.zip')
        evidence = rows(self.db, 'SELECT f.name,e.line_no,e.text FROM events e JOIN files f ON f.id=e.file_id')
        self.assertEqual({r['name']: r['text'] for r in evidence}, files)
        self.assertTrue(all(r['line_no'] == 1 for r in evidence))
        self.assertEqual(ingest(self.db, data, 'synthetic.zip')['id'], result['id'])

    def test_query_read_only_and_limit(self):
        self.load()
        self.assertEqual(readonly_query(self.db,'SELECT count(*) FROM calls')['rows'],[[1]])
        for sql in ['DELETE FROM calls','DROP TABLE calls',"ATTACH DATABASE ':memory:' AS injected",'PRAGMA journal_mode=OFF',"SELECT load_extension('bad')"]:
            with self.assertRaises(sqlite3.Error):
                readonly_query(self.db,sql)
        result=readonly_query(self.db,'WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<1100) SELECT x FROM n')
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['rows']),1000)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],1)


if __name__=='__main__':
    unittest.main()
