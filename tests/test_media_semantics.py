import unittest
from tests import test_server as fixture


class MediaSemanticsTests(unittest.TestCase):
    setUp = fixture.APITests.setUp
    tearDown = fixture.APITests.tearDown
    request = fixture.APITests.request

    def test_shared_ui_api_mcp_contract(self):
        status, media = self.request('GET', '/api/media-semantics')
        self.assertEqual(status, 200)
        parents = {d['name']: d['parent'] for d in media['devices']}
        for device in ('NART', 'ART', 'FileReaderThread'):
            self.assertEqual(parents[device], 'VAID')
        for device in ('NAWT', 'AWT', 'FileWriterThread'):
            self.assertEqual(parents[device], 'VAOD')
        self.assertEqual(parents['VAID'], 'VID')
        self.assertEqual(parents['VAOD'], 'VOD')
        status, analytical = self.request('GET', '/api/analytics/catalog')
        self.assertEqual(status, 200)
        self.assertEqual(analytical['media_plane'], media)
        status, metrics = self.request('GET', '/api/catalog')
        self.assertEqual(status, 200)
        self.assertIsInstance(metrics, list)  # Existing clients retain the list contract.
        by_name = {m['name']: m for m in metrics}
        for name, domain in [('vd.scheduling_delay', 'scheduling'),
                             ('vd.cycles_read', 'scheduling'),
                             ('vd.packets_rtp', 'rtp_transport'),
                             ('vd.underruns', 'buffer_media'),
                             ('vd.bytes_read', 'processing')]:
            self.assertEqual(by_name[name]['semantics']['domain'], domain)
        self.assertEqual(analytical['metrics'], metrics)
        self.assertIn('non il tempo di transito RTP', by_name['vd.scheduling_delay']['meaning'])
