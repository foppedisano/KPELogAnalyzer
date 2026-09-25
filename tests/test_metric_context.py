import unittest
from tests import test_server as fixture
from app.metric_context import context


class ContextTests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    upload=fixture.APITests.upload
    request=fixture.APITests.request

    def test_context_semantics(self):
        self.assertEqual(context('rtcp.jitter','incoming')['category'],'downstream')
        self.assertEqual(context('rtcp.loss','outgoing')['category'],'upstream')
        self.assertEqual(context('rtcp.rtt','outgoing')['category'],'bidirectional')
        self.assertEqual(context('kpe.audio.jitter','incoming')['category'],'unknown')
        self.assertEqual(context('vd.buffer','incoming','xcoder')['category'],'local')
        self.assertEqual(context('rtcp.jitter','outgoing','xcoder')['category'],'peer')

    def test_options_filter_csv_and_roles(self):
        self.upload()
        opts=self.request('GET','/api/metric-options?calls=1')[1]
        jitter=[o for o in opts if o['name']=='rtcp.jitter']
        self.assertEqual({o['category'] for o in jitter},{'upstream','downstream'})
        data=self.request('GET','/api/metrics?calls=1&name=rtcp.loss&direction=outgoing')[1]
        self.assertTrue(data)
        self.assertTrue(all(m['direction']=='outgoing' and m['measurement_context']['category']=='upstream' for m in data))
        csv=self.request('GET','/api/metrics?calls=1&name=rtcp.loss&direction=incoming&format=csv')[1]
        self.assertIn(b'downstream',csv);self.assertNotIn(b'upstream',csv)
        self.assertEqual(self.request('GET','/api/metrics?calls=1&direction=bad')[0],400)
        self.request('POST','/api/topology',dict(perspective_id=1,session='test',participant='Alice',role='xcoder'))
        opts=self.request('GET','/api/metric-options?calls=1')[1]
        self.assertEqual({o['category'] for o in opts if o['name']=='rtcp.jitter'},{'local','peer'})
        d=self.request('GET','/api/diagnostics?a=1')[1]
        self.assertEqual(next(s for s in d['series'] if s['name']=='rtcp.loss' and s['direction']=='outgoing')['measurement_context']['category'],'peer')
