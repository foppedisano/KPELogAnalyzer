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

    def test_interpolation_uses_audio_between_good_endpoints(self):
        self.prepare()
        self.db.execute("UPDATE geo_positions SET valid=0 WHERE ts LIKE '%06.%'")
        data=route(self.db,1)
        self.assertEqual([p['value'] for p in data['points']],[100,100])
        samples=data['interpolation']['points']
        bad=next(s for s in samples if '12:00:06.' in s['window_ts'])
        self.assertEqual(bad['value'],60)
        self.assertEqual(len(bad['position_evidence']),2)
        self.assertTrue(bad['audio_evidence'])
        self.assertGreater(bad['latitude'],45)
        self.assertLess(bad['latitude'],45.0002)
        self.assertLess(data['interpolation']['mean'],100)
        self.assertEqual(data['samples'],2)

    def test_minute_has_sixty_samples_and_large_gap_is_empty(self):
        self.prepare()
        self.db.execute("UPDATE geo_positions SET valid=0 WHERE ts LIKE '%06.%'")
        self.db.execute("UPDATE geo_positions SET ts='2026-01-01 12:00:00.000000' WHERE ts LIKE '%02.500%'")
        self.db.execute("UPDATE geo_positions SET ts='2026-01-01 12:01:00.000000' WHERE ts LIKE '%19.500%'")
        self.db.execute("UPDATE perspectives SET connected=start,end='2026-01-01 12:03:00.000000'")
        samples=route(self.db,1)['interpolation']['points']
        self.assertEqual(len(samples),60)
        self.assertEqual(len({s['window_ts'] for s in samples}),60)
        self.db.execute("UPDATE geo_positions SET ts='2026-01-01 12:02:01.000000' WHERE ts LIKE '%01:00.%'")
        self.assertEqual(route(self.db,1)['interpolation']['points'],[])

    def test_conflicting_anchors_and_cache_do_not_interpolate(self):
        self.prepare()
        self.db.execute("UPDATE geo_positions SET ts='2026-01-01 12:00:06.200000',latitude=46 WHERE ts LIKE '%06.500%'")
        self.assertEqual(route(self.db,1)['interpolation']['points'],[])

    def test_global_map_has_interpolated_audio_and_period_filter(self):
        self.prepare()
        data=aggregate(self.db,dict(metric='perceptual',cell='50'))
        estimates=[c.get('estimate',c) for c in data['cells'] if c['origin']=='estimated' or 'estimate' in c]
        points=[e for c in estimates for e in c['evidence']]
        self.assertTrue(points)
        self.assertTrue(any(s['value']<100 for s in points))
        self.assertTrue(all(len(s['position'])==2 for s in points))
        self.assertEqual(data['route_samples'],sum(c['observations'] for c in estimates))
        self.assertEqual(data['samples'],3)
        self.assertEqual(aggregate(self.db,dict(metric='perceptual',start='2026-01-01 12:00:10'))['route_samples'],0)

    def test_global_map_does_not_bridge_filtered_or_other_call_fixes(self):
        self.prepare()
        self.db.execute("UPDATE geo_positions SET kind='sip_local' WHERE ts LIKE '%06.%'")
        self.assertEqual(aggregate(self.db,dict(metric='perceptual',quality='fresh'))['route_samples'],0)
        self.assertTrue(aggregate(self.db,dict(metric='perceptual',quality='declared'))['route_samples'])
        self.db.execute("INSERT INTO calls(id,call_key) VALUES(99,'other')")
        self.db.execute("UPDATE geo_positions SET call_id=99 WHERE ts LIKE '%06.%'")
        self.assertEqual(aggregate(self.db,dict(metric='perceptual',quality='declared'))['route_samples'],0)
        self.db.execute("UPDATE geo_positions SET kind='cached'")
        self.assertEqual(route(self.db,1)['interpolation']['points'],[])

    def test_global_cells_fill_only_traversed_gaps_and_direct_wins(self):
        self.prepare()
        self.db.execute("UPDATE geo_positions SET valid=0 WHERE ts LIKE '%06.%'")
        self.db.execute("UPDATE geo_positions SET latitude=45.01,longitude=9.01 WHERE ts LIKE '%19.500%'")
        data=aggregate(self.db,dict(metric='perceptual',cell='50'))
        self.assertEqual(data['direct_cells'],2)
        self.assertGreater(data['estimated_cells'],0)
        self.assertEqual(len({c['id'] for c in data['cells']}),len(data['cells']))
        self.assertTrue(any(c['minimum']<100 for c in data['cells'] if c['origin']=='estimated'))
        for c in data['cells']:
            self.assertGreater(c['passes'],0)
            self.assertEqual(c['days'],1)
            if c['origin']=='estimated':
                self.assertEqual(c['gap_min_seconds'],17)
                self.assertEqual(c['gap_max_seconds'],17)
                self.assertTrue(c['evidence'][0]['audio'])
            else: self.assertEqual(c['mean'],100)
        # A larger cell contains direct observations and the disturbed interval.
        # Its displayed quality must remain the direct value, not a blend.
        data=aggregate(self.db,dict(metric='perceptual',cell='10000'))
        c=next(c for c in data['cells'] if 'estimate' in c and c['estimate']['minimum']<100)
        self.assertEqual(c['origin'],'direct')
        self.assertEqual(c['mean'],100)
        self.assertLess(c['estimate']['mean'],100)
        self.assertGreater(c['estimate']['affected_seconds'],0)
        self.assertEqual(data['mean'],100)

    def test_estimates_without_evaluable_audio_do_not_color_empty_zones(self):
        from unittest.mock import patch
        self.prepare()
        from app.call_route import interpolated_samples
        def ambiguous(*args):
            result=interpolated_samples(*args)
            for s in result['points']: s['value']=None
            return result
        with patch('app.perceptual_geo.interpolated_samples',side_effect=ambiguous):
            data=aggregate(self.db,dict(metric='perceptual'))
        self.assertEqual(data['estimated_cells'],0)
        self.assertTrue(all(c['origin']=='direct' and 'estimate' not in c for c in data['cells']))

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
