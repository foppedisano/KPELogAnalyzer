import json
import subprocess
import sys
import unittest
from app.mcp_server import Server, endpoint, PROTOCOL
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
        ]
        process=subprocess.run([sys.executable,'-m','app.mcp_server','--url',f'http://127.0.0.1:{self.server.server_port}'],
            input=('\n'.join(map(json.dumps,messages))+'\n').encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        self.assertEqual(process.returncode,0,process.stderr)
        replies=list(map(json.loads,process.stdout.splitlines()))
        self.assertEqual(len(replies),4)
        self.assertEqual(replies[0]['result']['protocolVersion'],PROTOCOL)
        self.assertEqual(len(replies[1]['result']['tools']),7)
        self.assertEqual(json.loads(replies[2]['result']['content'][0]['text'])['rows'],[[1]])
        self.assertTrue(replies[3]['result']['isError'])

    def test_lifecycle_and_local_transport(self):
        for url in ['https://127.0.0.1','http://example.test','http://localhost@evil.test','http://localhost/api','http://127.0.0.1/#x']:
            with self.assertRaises(ValueError):endpoint(url)
        s=Server('http://127.0.0.1:8080')
        self.assertIn('error',s.handle({'jsonrpc':'2.0','id':1,'method':'tools/list'}))
        self.assertEqual(s.handle({'jsonrpc':'2.0','id':2,'method':'ping'})['result'],{})
        self.assertIsNone(s.handle({'jsonrpc':'2.0','method':'notifications/cancelled'}))
        self.assertIn('error',s.handle([]))


if __name__=='__main__':unittest.main()
