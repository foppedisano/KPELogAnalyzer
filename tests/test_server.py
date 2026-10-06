import http.client
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from app.db import connect,init
from app.server import Handler,ThreadingHTTPServer
from tests.fixtures import archive,sample


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'KPE_DATA_DIR':self.temp.name})
        self.env.start()
        db=connect();init(db);db.close()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.env.stop();self.temp.cleanup()

    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        if isinstance(body,dict):
            body=json.dumps(body).encode()
        conn.request(method,path,body=body,headers=headers or {})
        response=conn.getresponse();data=response.read();status=response.status
        mime=response.getheader('Content-Type','');conn.close()
        return status,json.loads(data) if 'json' in mime else data

    def upload(self,files=None):
        return self.request('POST','/api/imports',archive(files or sample()),{'X-Filename':'synthetic.zip'})

    def test_connectivity_attempts_and_bounded_events(self):
        self.assertEqual(self.request('GET','/connectivity.js')[0],200)
        from tests.test_connectivity import app_line
        files=sample()
        files['App.log']=app_line(3,'Calling number: synthetic-target')+app_line(3,'KPE is not ready yet... the call cannot be established')
        self.assertEqual(self.upload(files)[0],201)
        code,calls=self.request('GET','/api/calls?attempts=1')
        self.assertEqual(code,200)
        attempt=next(c for c in calls if c['row_type']=='user_attempt')
        self.assertEqual(attempt['status'],'blocked')
        self.assertLess(attempt['id'],0)
        cid=next(c['id'] for c in calls if c['id']>0)
        code,data=self.request('GET',f'/api/connectivity?calls={cid}')
        self.assertEqual(code,200);self.assertIn('network',data[0]['lanes'])
        self.assertEqual(self.request('GET','/api/connectivity?import=1&start=2026-01-01&end=2026-01-03')[0],400)
        self.assertEqual(self.request('GET','/api/connectivity?calls=-1')[0],400)
        code,data=self.request('GET','/api/events?import=1&start=2026-01-01%2012:00:03&end=2026-01-01%2012:00:04')
        self.assertEqual(code,200);self.assertEqual(len(data['events']),2)
        self.assertTrue(all(e['log_family']=='app' and e['log_label']=='App' for e in data['events']))

    def test_structured_telemetry_api_and_mixed_mos_csv(self):
        from tests.test_telemetry_store import events
        structured=events()
        for e in structured:
            if 'stream' in e['payload']:e['payload']['stream']['sip_call_id']='call-a'
        files=sample()
        files['telemetry.jsonl']='\n'.join(map(json.dumps,structured))
        self.assertEqual(self.upload(files)[0],201)
        code,status=self.request('GET','/api/telemetry')
        self.assertEqual(code,200)
        self.assertEqual(status['intervals'],2)
        cid=self.request('GET','/api/calls')[1][0]['id']
        code,data=self.request('GET',f'/api/metrics?calls={cid}&name=derived.mos_reference&format=csv')
        self.assertEqual(code,200)
        self.assertIn(b'UTC',data)
        self.assertEqual(self.request('GET','/api/geography?access=cellular')[1]['seconds'],2)

    def test_import_browse_csv_and_database_snapshot(self):
        status,result=self.upload();self.assertEqual(status,201)
        cid=self.request('GET','/api/calls')[1][0]['id']
        events=self.request('GET',f'/api/events?call={cid}')[1]
        self.assertTrue(events['events'])
        metrics=self.request('GET',f'/api/metrics?calls={cid}&name=rtcp.rtt&statistic=sample')[1]
        self.assertEqual(metrics[0]['value'],42.25)
        csv=self.request('GET',f'/api/metrics?calls={cid}&name=rtcp.rtt&statistic=sample&format=csv')[1]
        self.assertIn(b'42.25',csv)
        analysis=self.request('GET',f'/api/analysis?call={cid}')[1]
        self.assertEqual(analysis['invalid_metrics'],1)
        self.assertEqual(len(analysis['signaling']),3)
        db=sqlite3.connect(':memory:')
        db.deserialize(self.request('GET','/api/database')[1])
        # serialize() must produce a standalone readable image, not depend on a WAL file.
        self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],1)
        db.close()
        self.assertTrue(self.upload()[1]['duplicate'])

    def test_conversation_host_validation(self):
        self.upload();self.upload(sample(cid='call-b'))
        calls=self.request('GET','/api/calls')[1]
        ids=[c['id'] for c in calls]
        payload={'title':'Synthetic conference','call_ids':ids,'host_perspective_id':999}
        self.assertEqual(self.request('POST','/api/conversations',payload)[0],400)
        payload['host_perspective_id']=self.request('GET','/api/perspectives')[1][0]['id']
        self.assertEqual(self.request('POST','/api/conversations',payload)[0],201)
        self.assertEqual(len(self.request('GET','/api/conversations')[1]),1)

    def test_clock_update_and_readonly_sql(self):
        iid=self.upload()[1]['id']
        self.assertEqual(self.request('PATCH','/api/imports',{'id':iid,'label':'Device B','clock_offset':-2.5})[0],200)
        self.assertEqual(self.request('GET','/api/imports')[1][0]['clock_offset'],-2.5)
        self.assertEqual(self.request('POST','/api/query',{'sql':'DELETE FROM calls'})[0],400)
        self.assertEqual(self.request('POST','/api/query',{'sql':'SELECT count(*) FROM calls'})[1]['rows'],[[1]])

    def test_origin_host_and_bad_zip(self):
        self.assertEqual(self.request('GET','/api/health',headers={'Host':'attacker.test'})[0],403)
        self.assertEqual(self.request('POST','/api/query',{'sql':'SELECT 1'},{'Origin':'http://foreign.test'})[0],403)
        self.assertEqual(self.request('POST','/api/imports',b'bad zip')[0],400)
        self.assertEqual(self.request('GET','/api/overview')[1]['imports'],0)


if __name__=='__main__':
    unittest.main()

class ManualAndDiagnosticAPITests(unittest.TestCase):
    setUp = APITests.setUp
    tearDown = APITests.tearDown
    request = APITests.request
    def test_text_import_manual_window_and_diagnostics(self):
        from tests.test_enrichment import vd
        body={'label':'Synthetic side','files':[{'name':'VDlog_A.txt','text':vd(5)+vd(10,150,200)}]}
        status,result=self.request('POST','/api/text-import',body)
        self.assertEqual(status,201)
        iid=result['id']
        self.assertEqual(self.request('POST','/api/text-import',body)[1]['duplicate'],True)
        self.assertEqual(self.request('GET','/api/calls')[1],[])
        window={'import_id':iid,'line_id':0,'start':'2026-01-01 12:00:00','end':'2026-01-01 12:00:20','title':'Synthetic window'}
        status,result=self.request('POST','/api/windows',window)
        self.assertEqual(status,201)
        pid=result['perspective_id']
        self.assertEqual(self.request('POST','/api/windows',window)[0],400)
        status,result=self.request('GET',f'/api/diagnostics?a={pid}')
        self.assertEqual(status,200)
        self.assertIn('rtcp.rtt',result['coverage'][0]['missing'])
        self.assertEqual(len(result['series']),4)
        self.assertEqual(self.request('GET',f'/api/diagnostics?a={pid}&b={pid}')[0],400)
        self.assertEqual(self.request('GET',f'/api/diagnostics?a={pid}&rtt_threshold=NaN')[0],400)
        self.assertTrue(self.request('GET','/api/catalog')[1])
        self.assertEqual(self.request('GET','/api/devices')[1][0]['device'],'NART0 of Line 0')
    def test_text_import_path_validation_and_window_timezone(self):
        self.assertEqual(self.request('POST','/api/text-import',{'files':[{'name':'../VDlog.txt','text':'x'}]})[0],400)
        self.assertEqual(self.request('POST','/api/windows',{'import_id':1,'start':'2026-01-01T12:00:00-02:00','end':'2026-01-01T12:00:20-02:00'})[0],400)
