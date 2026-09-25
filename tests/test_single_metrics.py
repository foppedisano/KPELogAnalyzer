import unittest
from tests import test_server as fixture
from tests.fixtures import sample
from tests.test_enrichment import vd


class SingleMetricTests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    upload=fixture.APITests.upload
    request=fixture.APITests.request

    def test_delta_menu_api_csv_and_diagnostic_parity(self):
        files=sample()
        files['VDlog.txt']=vd(5,100,10)+vd(10,100,30)+vd(15,100,2)
        self.upload(files)
        names=self.request('GET','/api/metric-names')[1]
        self.assertIn('derived.silence_delta',{x['name'] for x in names})
        status,data=self.request('GET','/api/metrics?calls=1&name=derived.silence_delta&statistic=sample')
        self.assertEqual(status,200)
        self.assertEqual([m['value'] for m in data],[20])
        self.assertEqual(data[0]['interval_seconds'],5)
        self.assertEqual(len(data[0]['evidence']),2)
        diagnostic=self.request('GET','/api/diagnostics?a=1')[1]
        delta=next(s for s in diagnostic['series'] if s['name']=='derived.silence_delta')
        self.assertEqual(delta['points'][0]['value'],data[0]['value'])
        csv=self.request('GET','/api/metrics?calls=1&name=derived.silence_delta&format=csv')[1]
        self.assertIn(b'interval_seconds',csv)
        self.assertIn(b'evidence',csv)

    def test_no_cross_device_or_source_and_rotated_files(self):
        files=sample()
        files['VDlog-old.txt']=vd(5,100,10)
        files['VDlog.txt']=vd(10,100,30)+(vd(5,100,100)+vd(10,100,180)).replace('NART0','NART1')
        self.upload(files)
        other=sample();other['VDlog.txt']=vd(5,100,300)+vd(10,100,350)
        self.upload(other)
        data=self.request('GET','/api/metrics?calls=1&name=derived.silence_delta')[1]
        self.assertEqual(sorted(m['value'] for m in data),[20,50,80])
        self.assertEqual(len({(m['perspective_id'],m['device']) for m in data}),3)

    def test_first_reset_long_gap_no_samples(self):
        from app.single_metrics import silence_delta
        points=[dict(t=t,value=v,evidence={}) for t,v in [(0,10),(5,2),(40,50),(40,60)]]
        self.assertEqual(silence_delta(points),[])
        self.upload()
        self.assertEqual(self.request('GET','/api/metrics?calls=1&name=derived.silence_delta')[1],[])

    def test_episode_durations_unknown_and_evidence(self):
        files=sample()
        files['VDlog.txt']=('[2026-01-01 12:00:05.000] [AWT] Buffer underrun event terminated while getting data from input device NART0 of Line 0 . Event was 40 msecs long.\n')
        files['kpelog.txt']+='[2026-01-01 12:00:06.000] [CORE] Line 0 reported that flow 0 has started receiving RTP media again\n'
        self.upload(files)
        underrun=self.request('GET','/api/metrics?calls=1&name=incident.buffer_underrun')[1]
        self.assertEqual(underrun[0]['value'],40)
        self.assertEqual(underrun[0]['episode']['duration_basis'],'reported')
        missing=self.request('GET','/api/metrics?calls=1&name=incident.media_missing')[1]
        self.assertIsNone(missing[0]['value'])
        self.assertTrue(missing[0]['evidence'])
