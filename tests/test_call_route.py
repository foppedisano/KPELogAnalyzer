import unittest
from app.call_route import route
from app.geography import aggregate
from tests import test_enrichment as fixture
from tests import test_perceptual


class RouteTests(unittest.TestCase):
    setUp=fixture.EnrichmentTests.setUp
    tearDown=fixture.EnrichmentTests.tearDown
    load=fixture.EnrichmentTests.load

    def prepare(self):
        self.load({'VDlog.txt':test_perceptual.IntegrationTests().audio(),'PhoneEngine.log':
            '[2026-01-01 12:00:02.500] New location received: Location[gps 45.0,9.0]\n'
            '[2026-01-01 12:00:06.200] New location received: Location[gps 45.0001,9.0001]\n'
            '[2026-01-01 12:00:06.500] New location received: Location[gps 45.0001,9.0001]\n'
            '[2026-01-01 12:00:19.500] New location received: Location[gps 45.0002,9.0002]\n'})

    def test_points_quality_and_dedup(self):
        self.prepare();data=route(self.db,1)
        self.assertEqual(len(data['points']),4)
        self.assertEqual(data['samples'],3)
        self.assertEqual([p['value'] for p in data['points']],[100,60,60,100])
        self.assertTrue(all(p['evidence']['event_id'] and p['audio_evidence'] for p in data['points']))
        self.assertEqual(data['cell'],50)
        with self.assertRaises(ValueError):route(self.db,1,999)
        with self.assertRaises(ValueError):route(self.db,1,cell=0)
        self.assertEqual(route(self.db,999)['points'],[])

    def test_boundaries_global_and_route(self):
        self.prepare()
        self.db.execute("UPDATE perspectives SET connected='2026-01-01 12:00:02.455000',end='2026-01-01 12:00:19.800000'")
        data=route(self.db,1)
        self.assertEqual(data['points'][0]['value'],100)
        self.assertEqual(data['points'][0]['observed_ms'],545)
        self.assertEqual(data['points'][-1]['observed_ms'],800)
        self.assertEqual(aggregate(self.db,dict(metric='perceptual',cell='50'))['samples'],3)
        self.db.execute('UPDATE perspectives SET end=NULL')
        self.assertEqual(route(self.db,1)['end_basis'],'last_call_evidence')
        self.assertEqual(aggregate(self.db,dict(metric='perceptual',cell='50'))['samples'],3)

    def test_other_calls_and_ambiguous_unassigned_positions(self):
        self.prepare()
        self.db.execute("INSERT INTO calls(id,call_key,start,end) VALUES(99,'other','2026-01-01 12:00:00','2026-01-01 12:00:20')")
        self.db.execute("INSERT INTO perspectives(id,call_id,import_id,line_id,start,end) VALUES(99,99,1,0,'2026-01-01 12:00:00','2026-01-01 12:00:20')")
        self.db.execute('UPDATE geo_positions SET call_id=NULL')
        self.assertEqual(route(self.db,1)['points'],[])
        self.db.execute('UPDATE geo_positions SET call_id=99')
        self.assertEqual(route(self.db,1)['points'],[])
        self.db.execute('UPDATE geo_positions SET call_id=1')
        self.assertEqual(len(route(self.db,1)['points']),4)

    def test_cache_and_long_gap_do_not_form_path(self):
        self.prepare()
        self.db.execute('UPDATE geo_positions SET call_id=1')
        self.db.execute("UPDATE geo_positions SET kind='cached' WHERE ts LIKE '%06.200%'")
        self.db.execute("UPDATE geo_positions SET ts='2026-01-01 12:01:00.000000' WHERE ts LIKE '%19.500%'")
        self.db.execute("UPDATE perspectives SET end='2026-01-01 12:01:01.000000'")
        points=route(self.db,1)['points']
        self.assertIsNone(points[1]['segment']);self.assertIsNone(points[1]['value'])
        self.assertEqual([p['segment'] for p in points],[1,None,1,2])


class RouteAPITests(unittest.TestCase):
    from tests.test_server import APITests as Fixture
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    request=Fixture.request
    upload=Fixture.upload

    def test_endpoint_and_source_scope(self):
        from tests.fixtures import sample
        files=sample();files['PhoneEngine.log']='[2026-01-01 12:00:06.200] New location received: Location[gps 45.0,9.0]\n'
        self.assertEqual(self.upload(files)[0],201)
        status,data=self.request('GET','/api/call-route?call=1&cell=50')
        self.assertEqual(status,200);self.assertEqual(data['points'][0]['value'],100)
        self.assertEqual(self.request('GET','/api/call-route?call=1&perspective=999')[0],400)
