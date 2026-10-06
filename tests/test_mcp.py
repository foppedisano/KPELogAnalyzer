import json
import subprocess
import sys
import unittest
from app.mcp_server import Server, endpoint, PROTOCOL, TOOLS
from tests import test_server as fixture


class MCPTests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    upload=fixture.APITests.upload
    request=fixture.APITests.request

    def test_stdio_end_to_end(self):
        self.upload()
        messages=[
            dict(jsonrpc='2.0',id=1,method='initialize',params={'protocolVersion':PROTOCOL,'clientInfo':{'name':'synthetic-test','version':'1'},'capabilities':{}}),
            dict(jsonrpc='2.0',method='notifications/initialized'),
            dict(jsonrpc='2.0',id=2,method='tools/list'),
            dict(jsonrpc='2.0',id=3,method='tools/call',params={'name':'analytics_query','arguments':{'sql':'SELECT COUNT(*) FROM a_calls'}}),
            dict(jsonrpc='2.0',id=4,method='tools/call',params={'name':'analytics_query','arguments':{'sql':'DELETE FROM a_calls'}}),
            dict(jsonrpc='2.0',id=5,method='tools/call',params={'name':'analytics_call_route','arguments':{'call_id':1}}),
            dict(jsonrpc='2.0',id=6,method='tools/call',params={'name':'analytics_perceptual_quality','arguments':{'call_ids':[1]}}),
            dict(jsonrpc='2.0',id=7,method='tools/call',params={'name':'analytics_connectivity','arguments':{'call_ids':[1]}}),
            dict(jsonrpc='2.0',id=8,method='tools/call',params={'name':'analytics_geo_cells','arguments':{'metric':'perceptual'}}),
        ]
        process=subprocess.run([sys.executable,'-m','app.mcp_server','--url',f'http://127.0.0.1:{self.server.server_port}'],
            input=('\n'.join(map(json.dumps,messages))+'\n').encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        self.assertEqual(process.returncode,0,process.stderr)
        replies=list(map(json.loads,process.stdout.splitlines()))
        self.assertEqual(len(replies),8)
        self.assertEqual(replies[0]['result']['protocolVersion'],PROTOCOL)
        self.assertEqual({t['name'] for t in replies[1]['result']['tools']},{t[0] for t in TOOLS})
        self.assertEqual(len(TOOLS),13)
        self.assertEqual(json.loads(replies[2]['result']['content'][0]['text'])['rows'],[[1]])
        self.assertTrue(replies[3]['result']['isError'])
        self.assertTrue(all(not reply['result']['isError'] for reply in replies[4:]))

    def test_lifecycle_and_local_transport(self):
        for url in ['https://127.0.0.1','http://example.test','http://localhost@evil.test','http://localhost/api','http://127.0.0.1/#x']:
            with self.assertRaises(ValueError):endpoint(url)
        s=Server('http://127.0.0.1:8080')
        self.assertIn('error',s.handle({'jsonrpc':'2.0','id':1,'method':'tools/list'}))
        self.assertEqual(s.handle({'jsonrpc':'2.0','id':2,'method':'ping'})['result'],{})
        self.assertIsNone(s.handle({'jsonrpc':'2.0','method':'notifications/cancelled'}))
        self.assertIn('error',s.handle([]))

    def client(self):
        s=Server(f'http://127.0.0.1:{self.server.server_port}')
        s.handle(dict(jsonrpc='2.0',id=1,method='initialize',params=dict(
            protocolVersion=PROTOCOL,clientInfo={},capabilities={})))
        s.handle(dict(jsonrpc='2.0',method='notifications/initialized'))
        return s

    def call(self, s, name, args):
        reply=s.handle(dict(jsonrpc='2.0',id=2,method='tools/call',params=dict(name=name,arguments=args)))
        self.assertNotIn('error',reply)
        result=reply['result']
        self.assertFalse(result['isError'],result)
        return json.loads(result['content'][0]['text'])

    def test_current_tools_match_ui_with_evidence(self):
        from tests.fixtures import sample
        from tests.test_perceptual import IntegrationTests
        from tests.test_connectivity import app_line
        files=sample()
        files.update({'VDlog.txt':IntegrationTests().audio(),'PhoneEngine.log':
            '[2026-01-01 12:00:02.500] New location received: Location[gps 45.0,9.0]\n'
            '[2026-01-01 12:00:19.500] New location received: Location[gps 45.002,9.002]\n',
            'App.log':app_line(3,'Calling number: synthetic-target')+app_line(3,'KPE is not ready yet... the call cannot be established'),
            'vdklog.txt':'[2026-01-01 12:00:01.000] [STUN] [INFO] SPM: Network UP for both pingers\n'})
        self.assertEqual(self.upload(files)[0],201)
        s=self.client()
        catalog=self.call(s,'analytics_catalog',{})
        self.assertIn('a_user_attempts',catalog['tables'])
        self.assertIn('a_connectivity',catalog['tables'])
        self.assertEqual(catalog['current_analysis']['pq_method'],'awt-occupancy-4')
        cov=self.call(s,'analytics_coverage',{})
        self.assertEqual(cov['user_attempts'],[dict(status='blocked',observations=1)])
        geo=self.call(s,'analytics_geo_cells',dict(metric='perceptual',cell=50))
        self.assertEqual(geo,self.request('GET','/api/geography?metric=perceptual&cell=50')[1])
        self.assertGreater(geo['estimated_cells'],0)
        self.assertTrue(any(c['origin']=='direct' for c in geo['cells']))
        route=self.call(s,'analytics_call_route',dict(call_id=1))
        self.assertEqual(route,self.request('GET','/api/call-route?call=1')[1])
        self.assertTrue(route['interpolation']['points'][0]['position_evidence'])
        pq=self.call(s,'analytics_perceptual_quality',dict(call_ids=[1]))
        self.assertTrue(any(x['value']<100 for x in pq['samples']))
        self.assertTrue(all(x['evidence'] for x in pq['samples']))
        lanes=self.call(s,'analytics_connectivity',dict(call_ids=[1]))
        self.assertEqual(lanes,self.request('GET','/api/connectivity?calls=1')[1])
        self.assertEqual(lanes[0]['ttl_seconds'],30)
        source=self.call(s,'analytics_connectivity',dict(import_id=1,start='2026-01-01 12:00:00',end='2026-01-01 12:01:00'))
        self.assertIn('network',source['lanes'])
        attempts=self.call(s,'analytics_query',dict(sql='SELECT * FROM a_user_attempts'))
        self.assertEqual(len(attempts['rows']),1)
        self.assertNotIn('target',attempts['columns'])
        self.assertNotIn('text',attempts['columns'])
        self.assertEqual(self.call(s,'analytics_query',dict(sql='SELECT * FROM a_user_attempts',scope=dict(call_ids=[1])))['rows'],[])
        self.assertEqual(self.call(s,'analytics_query',dict(sql='SELECT * FROM a_user_attempts',scope=dict(start='2026-01-02')))['rows'],[])
        observations=self.call(s,'analytics_query',dict(sql='SELECT event_id,filename,line_no FROM a_connectivity'))
        self.assertTrue(observations['rows'])
        self.assertEqual(self.call(s,'analytics_query',dict(sql='SELECT * FROM a_connectivity',scope=dict(call_ids=[1])))['rows'],[])
        self.assertNotIn('synthetic-target',json.dumps([geo,route,pq,lanes,attempts]))

    def test_current_validation_and_read_only(self):
        self.upload()
        s=self.client()
        cases=[('call-route',{'call_id':True}),('call-route',{'call_id':1,'cell':True}),
            ('call-route',{'call_id':1,'perspective_id':999}),
            ('perceptual-quality',{'call_ids':[]}),('perceptual-quality',{'call_ids':[False]}),
            ('perceptual-quality',{'call_ids':list(range(1,22))}),
            ('connectivity',{}),('connectivity',{'call_ids':[1],'import_id':1}),
            ('connectivity',{'import_id':1,'start':None,'end':'2026-01-02'}),
            ('connectivity',{'import_id':1,'start':'2026-01-01','end':'2026-01-03'}),
            ('geo-cells',{'metric':'perceptual','direction':'upstream'}),
            ('geo-cells',{'metric':'unknown'}),('geo-temporal',{'cell':50,'cell_id':'0:0','metric':'perceptual'})]
        for name,args in cases:
            with self.subTest(name=name,args=args):
                status,_=self.request('POST','/api/analytics/'+name,args)
                self.assertEqual(status,400)
        for sql in ('DELETE FROM a_user_attempts','SELECT * FROM user_attempts','SELECT text FROM a_events'):
            reply=s.handle(dict(jsonrpc='2.0',id=3,method='tools/call',params=dict(name='analytics_query',arguments=dict(sql=sql))))
            self.assertTrue(reply['result']['isError'])
        self.assertEqual(self.call(s,'analytics_query',dict(sql='SELECT COUNT(*) FROM a_calls'))['rows'],[[1]])

    def test_response_limit_rolls_back_without_mutation(self):
        from unittest.mock import patch
        from app.db import connect
        from app.analytics_current import run
        self.upload()
        db=connect()
        try:
            before=db.total_changes
            with patch('app.call_route.route',return_value={'data':'x'*(4*1024*1024)}):
                with self.assertRaisesRegex(ValueError,'4 MiB'):
                    run(db,'call-route',dict(call_id=1))
            self.assertFalse(db.in_transaction)
            self.assertEqual(db.total_changes,before)
            self.assertEqual(run(db,'call-route',dict(call_id=1))['call_id'],1)
        finally:
            db.close()


if __name__=='__main__':unittest.main()
