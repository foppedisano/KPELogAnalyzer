"""Synthetic regressions for log families, source windows and call-only defaults."""
import unittest
from app.call_events import family,query,windows
from app.db import connect
from tests import test_server
from tests.fixtures import sample,kpe


class CallEventsTests(unittest.TestCase):
    setUp=test_server.APITests.setUp
    def tearDown(self):
        if getattr(self,"db",None):self.db.close()
        test_server.APITests.tearDown(self)
    upload=test_server.APITests.upload
    request=test_server.APITests.request

    def test_family_rotations(self):
        for name in ('VDLog_1.txt','nested/VDlog-12.txt','VDLog.txt.2','VDLog.log','VDLog'):
            self.assertEqual(family(name),'vdlog')
        self.assertNotEqual(family('custom_alpha.log'),family('custom_beta.log'))

    def test_mixed_modes_context_pagination_and_filters(self):
        self.upload(sample())
        db=self.db=connect()
        fid=db.execute("SELECT id FROM files WHERE name='kpelog.txt'").fetchone()[0]
        # Assigned other-call and unknown events in the same source are context;
        # outside-window rows and a different source must never leak into it.
        db.execute("INSERT INTO calls(id,call_key) VALUES(99,'synthetic-other')")
        for cid,ts,text in [(None,'12:00:08','context'),(99,'12:00:09','other-call'),(None,'12:00:59','outside')]:
            db.execute("INSERT INTO events(import_id,file_id,line_no,ts,kind,text,call_id) VALUES(1,?,90,?,'raw',?,?)",(fid,'2026-01-01 '+ts,text,cid))
        db.execute("INSERT INTO imports(id,name,sha256,label) VALUES(99,'synthetic','synthetic','synthetic')")
        db.execute("INSERT INTO files(id,import_id,name,size,parser) VALUES(99,99,'kpelog.txt',0,'kpe')")
        db.execute("INSERT INTO events(import_id,file_id,line_no,ts,kind,text) VALUES(99,99,1,'2026-01-01 12:00:08','raw','foreign-source')")
        db.execute("INSERT INTO perspectives(call_id,import_id,start,end) VALUES(1,99,'2026-01-01 12:01:00','2026-01-01 12:01:20')")
        db.execute("INSERT INTO events(import_id,file_id,line_no,ts,kind,text) VALUES(99,99,2,'2026-01-01 12:01:08','raw','second-window')")
        db.execute("INSERT INTO events(import_id,file_id,line_no,kind,text,call_id) VALUES(1,?,89,'raw','undated',1)",(fid,))
        for n in range(105):
            db.execute("INSERT INTO events(import_id,file_id,line_no,ts,kind,text,level) VALUES(1,?,?,'2026-01-01 12:00:10','raw','page-row','DEBUG')",(fid,100+n))
        db.commit()
        before=db.total_changes
        default=query(db,1)
        self.assertTrue(all(e['call_id']==1 for e in default['events']))
        self.assertTrue(any(e['text']=='undated' for e in default['events']))
        modes={f['id']:'hide' for f in default['families']};modes['kpelog']='interval'
        data=query(db,1,modes)
        self.assertTrue(data['more']);self.assertEqual(len(data['events']),100)
        self.assertTrue(any(e['is_context'] for e in data['events']))
        rest=query(db,1,modes,offset=100)
        self.assertFalse(set(e['id'] for e in data['events']) & set(e['id'] for e in rest['events']))
        self.assertFalse(any(e['text'] in ('outside','foreign-source') for e in data['events']+rest['events']))
        self.assertTrue(any(e['text']=='second-window' for e in rest['events']))
        self.assertFalse(any(e['text']=='undated' for e in data['events']+rest['events']))
        self.assertEqual(len(query(db,1,modes,search='other-call')['events']),1)
        self.assertTrue(all(e['level']=='DEBUG' for e in query(db,1,modes,level='DEBUG')['events']))
        self.assertEqual(query(db,1,{f['id']:'hide' for f in default['families']})['events'],[])
        self.assertEqual(db.total_changes,before);db.close()
        status,response=self.request('GET','/api/call-events?call=1')
        self.assertEqual(status,200);self.assertTrue(response['families'])
        for path in ('/api/call-events?call=-1','/api/call-events?call=1&families=[]','/api/call-events?call=1&offset=-1'):
            self.assertEqual(self.request('GET',path)[0],400)

    def test_terminated_local_window_not_extended_by_reuse(self):
        text=kpe(0,'Call on line 0 added to the call list')+kpe(1,'Call status changed to 1 on line 0')+kpe(10,'Call on line 0 removed from list')+kpe(40,'Call on line 0 added to the call list')
        self.upload({'kpelog.txt':text})
        db=self.db=connect()
        p=dict(db.execute('SELECT * FROM perspectives ORDER BY id LIMIT 1').fetchone())
        self.assertIn('12:00:10',p['end'])
        # Simulate the legacy bug without changing source evidence.
        db.execute("UPDATE perspectives SET end='2026-01-01 12:00:40.000000' WHERE id=?",(p['id'],))
        db.execute("UPDATE calls SET end='2026-01-01 12:00:40.000000' WHERE id=?",(p['call_id'],));db.commit()
        w=windows(db,p['call_id'])[0]
        self.assertIn('12:00:10',w['end']);self.assertIsNotNone(w['window_evidence'])
        self.assertIn('12:00:40',db.execute('SELECT end FROM perspectives WHERE id=?',(p['id'],)).fetchone()[0])
        db.close()

    def test_attempt_evidence_context_and_pagination(self):
        from tests.test_connectivity import app_line
        from urllib.parse import urlencode
        import json
        f=sample()
        f['App.log']=app_line(8,'Unrelated context')+app_line(10,'Calling number: synthetic-target')+app_line(10,'KPE is not ready yet... the call cannot be established')+app_line(12,'Calling number: another-target')+app_line(30,'Outside context')
        self.upload(f)
        db=self.db=connect()
        a=db.execute('SELECT * FROM user_attempts ORDER BY ts LIMIT 1').fetchone()
        aid=a['event_id'];proof={aid,a['reason_event_id']}
        data=query(db,None,attempt_id=aid)
        self.assertEqual({e['id'] for e in data['events']},proof)
        self.assertTrue(all(not e['is_context'] for e in data['events']))
        self.assertTrue(all(f['mode']=='evidence' for f in data['families']))
        families=data['families']
        modes={'app':'interval'}
        data=query(db,None,modes,attempt_id=aid)
        self.assertEqual(len(data['events']),3)
        self.assertEqual(sum(e['is_context'] for e in data['events']),1)
        self.assertEqual(data['windows'][0]['start'],'2026-01-01 11:59:10.000000')
        self.assertEqual(data['windows'][0]['end'],'2026-01-01 12:00:10.000000')
        self.assertFalse(any('another-target' in e['text'] or 'Outside' in e['text'] for e in data['events']))
        self.assertEqual(query(db,None,{f['id']:'hide' for f in families},attempt_id=aid)['events'],[])
        other=db.execute('SELECT event_id FROM user_attempts WHERE event_id!=?',(aid,)).fetchone()[0]
        self.assertEqual(len(query(db,None,attempt_id=other)['events']),1)
        self.assertEqual(query(db,None,modes,attempt_id=other)['windows'][0]['end'],'2026-01-01 12:00:12.000000')
        db.execute("UPDATE events SET ts='2026-01-01 12:00:11.000000' WHERE id=?",(a['reason_event_id'],))
        delayed=query(db,None,modes,attempt_id=aid)
        self.assertEqual(delayed['windows'][0]['end'],'2026-01-01 12:00:11.000000')
        self.assertTrue(proof.issubset({e['id'] for e in delayed['events']}))
        fid=db.execute("SELECT id FROM files WHERE name='App.log'").fetchone()[0]
        for n in range(105):
            db.execute("INSERT INTO events(import_id,file_id,line_no,ts,kind,text) VALUES(1,?,?,'2026-01-01 12:00:09','raw','page')",(fid,100+n))
        db.commit();before=db.total_changes
        first=query(db,None,modes,attempt_id=aid);second=query(db,None,modes,offset=100,attempt_id=aid)
        self.assertTrue(first['more']);self.assertEqual(len(first['events']),100)
        self.assertFalse(set(e['id'] for e in first['events']) & set(e['id'] for e in second['events']))
        self.assertEqual(db.total_changes,before)
        code,response=self.request('GET','/api/attempt-events?'+urlencode(dict(attempt=aid,families=json.dumps(modes),search='Unrelated')))
        self.assertEqual(code,200);self.assertEqual(len(response['events']),1)
        for params in ({'attempt':-1},{'attempt':999999},{'attempt':aid,'families':'[]'},{'attempt':aid,'families':'{"app":"call"}'},{'attempt':aid,'offset':-1}):
            self.assertEqual(self.request('GET','/api/attempt-events?'+urlencode(params))[0],400)


if __name__=='__main__':unittest.main()
