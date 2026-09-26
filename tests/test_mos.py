import math
import unittest
from app.mos import score
from tests import test_server as fixture
from tests.fixtures import sample, rtcp


class MosTests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    upload=fixture.APITests.upload
    request=fixture.APITests.request

    def test_call_summary_weighting_and_latest_export(self):
        f=sample(); f['rtplog.txt']=rtcp(5)+rtcp(10).replace('2%.','12%.')
        self.upload(f)
        m=self.request('GET','/api/calls')[1][0]['mos']['downstream']
        self.assertAlmostEqual(m['mean'],(score(2)*5+score(12)*10)/15)
        self.assertAlmostEqual(m['coverage_percent'],100*15/18)
        self.assertEqual(m['minimum'],score(12))
        self.assertEqual(m['maximum'],score(2))
        self.assertTrue(m['minimum_event_id'])
        f=sample(); del f['rtplog.txt']; self.upload(f)
        latest=self.request('GET','/api/calls')[1][0]['mos']
        self.assertEqual(latest['perspective_id'],2)
        self.assertIsNone(latest['downstream'])

    def test_call_summary_ambiguous_streams_and_invalid_gap(self):
        f=sample(); f['rtplog.txt']=rtcp(5)+rtcp(10).replace('2%.','-1%.')+rtcp(15)
        self.upload(f)
        m=self.request('GET','/api/calls')[1][0]['mos']['downstream']
        self.assertEqual(m['covered_seconds'],10)
        f=sample(cid='multi'); f['rtplog.txt']=rtcp(5)+rtcp(10).replace('FLOW 0','FLOW 1')
        self.upload(f)
        m=next(c for c in self.request('GET','/api/calls')[1] if c['sip_call_id']=='multi')['mos']
        self.assertIsNone(m['downstream'])
        self.assertIn('SSRC',m['downstream_reason'])

    def test_reference(self):
        self.assertAlmostEqual(score(0),4.409285824)
        self.assertGreater(score(1),score(5))
        self.assertGreaterEqual(score(100),1)
        for v in (-1,101,math.nan,math.inf):
            self.assertIsNone(score(v))

    def test_gateway_origin_reverses_directions(self):
        self.upload()
        app=self.request('GET','/api/mos?local=1')[1]
        gw=self.request('GET','/api/mos?local=1&local_role=gw')[1]
        self.assertEqual(gw['upstream'],app['downstream'])
        self.assertEqual(gw['downstream'],app['upstream'])
        self.assertEqual(gw['upstream_basis'],'local')

    def test_intervals_invalid_and_evidence(self):
        f=sample(); f['rtplog.txt']=rtcp(5)+rtcp(10).replace('2%.','-1%.')+rtcp(15)
        self.upload(f)
        status,data=self.request('GET','/api/mos?local=1')
        self.assertEqual(status,200)
        self.assertEqual([m['interval_seconds'] for m in data['downstream']],[5,5])
        self.assertEqual(len(data['upstream']),3)
        self.assertEqual(data['upstream_basis'],'remote_rtcp')
        self.assertTrue(data['downstream'][0]['evidence'][0]['event_id'])
        self.assertIsNone(data['downstream'][0]['observation_start'])
        self.assertEqual(self.request('GET','/api/mos?local=999')[0],400)

    def test_peer_reuses_local_and_keeps_gaps(self):
        self.upload()
        f=sample(cid='gateway-leg'); f['rtplog.txt']=rtcp(15).replace('2%.','7%.')
        self.upload(f)
        gw=self.request('GET','/api/mos?local=2')[1]
        paired=self.request('GET','/api/mos?local=1&peer=2')[1]
        self.assertEqual(paired['upstream'],gw['downstream'])
        self.assertEqual(paired['upstream'][0]['perspective_id'],2)
        self.assertEqual(paired['upstream_basis'],'peer_local_reused')
        self.assertEqual(self.request('GET','/api/mos?local=1&peer=1')[0],400)

    def test_menu_csv_no_loss_and_context(self):
        from tests.test_enrichment import vd
        f=sample();f['VDlog.txt']=vd(5,100,10)+vd(10,100,30)
        self.upload(f)
        data=self.request('GET','/api/mos?local=1')[1]
        delta=next(m for m in data['context'] if m['name']=='derived.silence_delta')
        self.assertEqual(delta['value'],20)
        self.assertEqual(len(delta['evidence']),2)
        self.assertEqual(data['downstream'][0]['value'],score(2))
        options=self.request('GET','/api/metric-options?calls=1')[1]
        self.assertEqual(len([m for m in options if m['name']=='derived.mos_reference']),2)
        csv=self.request('GET','/api/metrics?calls=1&name=derived.mos_reference&format=csv')[1]
        self.assertIn(b'valid_until',csv)
        f=sample(cid='no-rtcp');del f['rtplog.txt'];self.upload(f)
        self.assertEqual(self.request('GET','/api/mos?local=2')[1]['downstream'],[])

    def test_conflicts_and_flow_isolation(self):
        f=sample();f['rtplog.txt']=rtcp(5)+rtcp(5).replace('2%.','3%.')+rtcp(10).replace('FLOW 0','FLOW 1')
        self.upload(f)
        d=self.request('GET','/api/mos?local=1')[1]['downstream']
        self.assertEqual(len(d),1)
        self.assertEqual(d[0]['flow'],'1')

    def test_expiry_offsets_and_no_cross_source_fill(self):
        from app.db import connect
        self.upload()
        db=connect()
        with db:
            db.execute("UPDATE perspectives SET end='2026-01-01 12:02:00.000000'")
            db.execute('UPDATE imports SET clock_offset=12')
        db.close()
        d=self.request('GET','/api/mos?local=1')[1]['downstream'][0]
        self.assertEqual(d['interval_seconds'],30)
        self.assertEqual(d['valid_until'],'2026-01-01 12:00:40.000000')
        self.assertEqual(d['clock_offset'],12)
        f=sample(cid='silent-gw');del f['rtplog.txt'];self.upload(f)
        paired=self.request('GET','/api/mos?local=1&peer=2')[1]
        self.assertEqual(paired['upstream'],[])
        self.assertTrue(paired['downstream'])


if __name__=='__main__':
    unittest.main()
