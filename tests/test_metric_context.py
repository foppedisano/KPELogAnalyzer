import unittest
from tests import test_server as fixture
from app.metric_context import context
from app.catalog import CATALOG
from tests.fixtures import sample
from tests.test_periodic import block


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

    def test_every_device_metric_and_delta_use_the_measured_path(self):
        names = [m['name'] for m in CATALOG if m['orientation']['rule'] == 'device']
        for name in names:
            for role in ('app', 'xcoder', 'unknown'):
                with self.subTest(name=name, role=role):
                    tx = context(name, 'outgoing', role, device='Default Audio Input', output_device='NAWT0 of Line 0')
                    self.assertEqual(tx['category'], 'upstream' if role == 'app' else 'transmit')
                    self.assertIn('trasmissione', tx['label'])
                    rx = context(name, 'incoming', role, device='NART0 of Line 0', output_device='Default Audio Output')
                    self.assertEqual(rx['category'], 'downstream' if role == 'app' else 'local')
                    self.assertEqual(context(name, '', role)['category'], 'processing')
                    for device in ('Default Audio Input', 'Default Audio Output', 'VD', 'FileReaderThread', 'NAWT-not-an-identity'):
                        self.assertEqual(context(name, 'incoming', role, device=device)['category'], 'processing')
                    # A loopback/mix from receiver to network writer is not a one-way app leg.
                    self.assertEqual(context(name, 'outgoing', role, device='NART0 of Line 0', output_device='NAWT0 of Line 0')['category'], 'processing')

    def test_all_transport_rules_do_not_confuse_report_sender_and_receiver(self):
        for m in CATALOG:
            name = m['name']
            with self.subTest(name=name):
                self.assertIn('description', m['orientation'])
                if name.startswith('kpe.'):
                    for direction in ('incoming', 'outgoing', ''):
                        self.assertEqual(context(name, direction)['category'], 'unknown')
        for suffix in ('total', 'interval'):
            sent = context('rtcp.packets_sent_' + suffix, 'incoming')
            lost = context('rtcp.packets_lost_' + suffix, 'outgoing')
            self.assertEqual(sent['category'], 'downstream')
            self.assertIn('Sender Report', sent['label'])
            self.assertIn('non ricezione misurata', sent['label'])
            self.assertEqual(lost['category'], 'upstream')
            self.assertIn('Receiver Report', lost['label'])
        for name in ('rtcp.packets_received', 'rtcp.packets_received_interval', 'vd.missing_packets', 'vd.max_arrival_delay', 'incident.media_missing'):
            self.assertEqual(context(name, 'incoming')['category'], 'downstream')
            self.assertEqual(context(name, 'incoming', 'gw')['category'], 'upstream')
        for name in ('rtcp.jitter', 'rtcp.loss', 'derived.mos_reference', 'telemetry.network_loss'):
            self.assertEqual(context(name, 'outgoing', 'gw')['category'], 'downstream')
            self.assertEqual(context(name, '')['category'], 'unknown')
        self.assertIn('Stima', context('derived.mos_reference', 'incoming')['label'])
        self.assertIn('ICMP', context('network.ping', 'roundtrip')['label'])

    def test_microphone_delta_inherits_context_across_api_menu_csv_and_diagnostics(self):
        files = sample()
        def tx(second, value):
            return block(second, value=value, observer='NAWT0 of Line 0', device='Default Audio Input').replace('Default Audio Output', 'NAWT0 of Line 0')
        files['VDlog.txt'] = tx(5, 100) + tx(10, 125)
        self.assertEqual(self.upload(files)[0], 201)
        path = '/api/metrics?calls=1&name=derived.silence_played_delta'
        delta = self.request('GET', path)[1][0]
        self.assertEqual(delta['value'], 25)
        self.assertEqual(delta['unit'], 'ms')
        self.assertEqual(delta['measurement_context']['category'], 'upstream')
        self.assertIn('app presunta', delta['measurement_context']['label'])
        self.assertIn('intervallo', delta['observation_label'])
        self.assertIsNone(delta['raw_value'])
        self.assertEqual(len(delta['evidence']), 2)
        source = self.request('GET', '/api/metrics?calls=1&name=vd.silence_played')[1][0]
        self.assertIn('contatore', source['observation_label'])
        opts = self.request('GET', '/api/metric-options?calls=1')[1]
        self.assertEqual(next(o for o in opts if o['name'] == delta['name'])['category'], 'upstream')
        csv = self.request('GET', path + '&format=csv')[1]
        self.assertIn(b'upstream', csv)
        self.assertNotIn(b'downstream', csv)
        diag = self.request('GET', '/api/diagnostics?a=1&device_a=Default%20Audio%20Input')[1]
        for items in (diag['series'], diag['findings']):
            item = next(s for s in items if s['name'] == delta['name'])
            self.assertEqual(item['measurement_context']['category'], 'upstream')
            self.assertEqual(item['device'], 'Default Audio Input')
        self.request('POST', '/api/topology', dict(perspective_id=1, session='synthetic', participant='Node', role='xcoder'))
        self.assertEqual(self.request('GET', path)[1][0]['measurement_context']['category'], 'transmit')

    def test_mixed_context_menu_and_observer_do_not_override_measured_device(self):
        files = sample()
        files['VDlog.txt'] = block(5, value=100) + block(10, value=125)
        files['VDlog.txt'] += (block(5, value=200, observer='NAWT0 of Line 0', device='Default Audio Input') +
                              block(10, value=240, observer='NAWT0 of Line 0', device='Default Audio Input')).replace('Default Audio Output', 'NAWT0 of Line 0')
        self.upload(files)
        data = self.request('GET', '/api/metrics?calls=1&name=derived.silence_played_delta')[1]
        self.assertEqual({m['value'] for m in data}, {25, 40})
        self.assertEqual({m['measurement_context']['category'] for m in data}, {'upstream', 'downstream'})
        opts = self.request('GET', '/api/metric-options?calls=1')[1]
        for name in ('vd.silence_played', 'derived.silence_played_delta'):
            option = next(o for o in opts if o['name'] == name)
            self.assertEqual(option['category'], 'unknown')
            self.assertIn('Contesti multipli', option['title'])
        from app.metric_context import annotate
        from app.db import connect
        db = connect()
        try:
            generic = dict(name='vd.buffer', perspective_id=1, direction='incoming', device='unrelated', observer='NART0 of Line 0')
            self.assertEqual(annotate(db, [generic])[0]['measurement_context']['category'], 'processing')
        finally:
            db.close()
