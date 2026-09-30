import json
import unittest
from collections import defaultdict
from app.db import connect
from app.geography import grid
from app.geo_temporal import profile, summarize, validate
from app.mcp_server import Server, PROTOCOL
from tests import test_server as fixture
from tests.fixtures import sample, rtcp
from tests.test_geography import fix


def observation(start,end,value,source='a',call=1):
    return dict(start=start,end=end,value=value,context={},series='intervals',series_context={},
        sources={source},calls={call},accuracy=12,evidence=[],observation_ids=[])


class TemporalMathTests(unittest.TestCase):
    def result(self,items,**extra):
        c,b=validate(dict(cell=250,cell_id=grid(45,9,250)[0],**extra))
        return summarize(c,b,items,defaultdict(int),lambda:None)

    def test_hour_day_week_year_boundaries_and_no_zero_imputation(self):
        result=self.result([observation('2025-12-31 23:59:50','2026-01-01 00:00:10',2)],grain='year')
        self.assertEqual([(x['key'],x['observed_seconds']) for x in result['profiles']['history']],[('2025',10),('2026',10)])
        self.assertEqual(result['summary']['observed_seconds'],20)
        self.assertEqual(result['summary']['days'],2)
        self.assertEqual(result['profiles']['hour'][23]['mean'],2)
        self.assertIsNone(result['profiles']['hour'][13]['mean'])
        week=self.result([observation('2026-01-04 23:59:50','2026-01-05 00:00:10',2)],grain='week')
        self.assertEqual([x['key'] for x in week['profiles']['history']],['2025-12-29','2026-01-05'])

    def test_day_balancing_and_source_counts_not_sample_counts(self):
        result=self.result([observation('2026-01-01 13:00:00','2026-01-01 13:10:00',1),
                            observation('2026-01-02 13:00:00','2026-01-02 13:00:10',5)])
        r=result['profiles']['hour'][13]
        self.assertAlmostEqual(r['mean'],650/610)
        self.assertEqual(r['day_balanced_mean'],3)
        self.assertEqual((r['sources'],r['calls'],r['days']),(1,1,2))
        self.assertTrue(r['limited'])

    def test_validation_and_exact_grid_bounds(self):
        for size in (50,500,10000):
            key,bounds=grid(45,9,size)
            self.assertEqual(validate(dict(cell=size,cell_id=key))[1],bounds)
        for extra in ({'cell':True},{'cell_id':'-1:2'},{'cell_id':'0:999999999999999999999'},
                      {'time_basis':'local'},{'metric':'m.password'},{'evidence_limit':201},
                      {'start':'2026-01-01T00:00:00Z'},{'operator':[]},{'end':'bad'}):
            with self.assertRaises(ValueError):validate(dict(cell=250,cell_id='1:1')|extra)

    def test_population_comparison_is_explicit_and_preserves_series(self):
        items=[observation('2026-01-01 13:00:00','2026-01-01 13:00:00',10),
               observation('2026-01-02 13:00:00','2026-01-02 13:00:00',30,'b',2)]
        for i,r in enumerate(items):
            r['series']=str(i);r['series_context']=dict(perspective_id=i,ssrc=str(i),unit='ms',direction='incoming')
        initial=self.result(items,metric='rtcp.jitter')
        self.assertTrue(initial['selection_required'])
        self.assertIsNone(initial['summary']['mean'])
        chosen=self.result(items,metric='rtcp.jitter',series_id=initial['populations'][0]['id'])
        self.assertEqual(chosen['summary']['day_balanced_mean'],20)
        self.assertEqual(len(chosen['series_breakdown']),2)
        self.assertEqual(chosen['summary']['sources'],2)
        self.assertFalse(self.result(items,metric='vd.underruns')['populations'])


class GeoTemporalAPITests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    upload=fixture.APITests.upload
    request=fixture.APITests.request

    def load(self):
        f=sample();f['application.log']=fix(5);f['rtplog.txt']=rtcp(6)+rtcp(12)
        self.assertEqual(self.upload(f)[0],201)

    def query(self,**extra):
        body=dict(cell=250,cell_id=grid(45,9,250)[0])|extra
        status,result=self.request('POST','/api/analytics/geo-temporal',body)
        self.assertEqual(status,200,result)
        return result

    def test_api_map_parity_and_evidence_pagination(self):
        self.load();m=self.request('GET','/api/geography')[1];r=self.query(evidence_limit=1)
        self.assertAlmostEqual(r['summary']['observed_seconds'],m['seconds'])
        self.assertAlmostEqual(r['summary']['mean'],m['mean'])
        self.assertEqual(r['summary']['calls'],1)
        self.assertTrue(r['evidence'][0]['references'][0]['position_event_id'])
        self.assertTrue(r['evidence_more'])
        next_page=self.query(evidence_offset=1,evidence_limit=1)
        self.assertEqual(next_page['snapshot'],r['snapshot'])
        self.assertNotEqual(next_page['evidence'],r['evidence'])
        for size in (50,500):
            self.assertEqual(self.query(cell=size,cell_id=grid(45,9,size)[0])['summary']['observed_seconds'],r['summary']['observed_seconds'])
        empty=self.query(cell_id=grid(0,0,250)[0])
        self.assertIsNone(empty['summary']['mean'])
        self.assertEqual(empty['summary']['observed_seconds'],0)
        self.assertEqual(self.query(access='wifi')['summary']['observations'],0)

    def test_clock_domains_remain_separate(self):
        self.load()
        from tests.test_telemetry_store import events
        self.upload({'telemetry.jsonl':'\n'.join(map(json.dumps,events()))})
        db=connect()
        row=db.execute("SELECT g.latitude,g.longitude FROM geo_mos g JOIN telemetry_geo_context t ON t.observation_id=g.id LIMIT 1").fetchone()
        db.close();self.assertIsNotNone(row)
        utc=self.query(time_basis='utc',cell_id=grid(row[0],row[1],250)[0])
        self.assertGreater(utc['summary']['observed_seconds'],0)
        self.assertEqual(utc['time_basis'],'utc')
        self.assertEqual(self.query(time_basis='utc',metric='vd.scheduling_delay')['summary']['observations'],0)

    def test_point_metric_provenance_no_invented_duration(self):
        self.load();r=self.query(metric='rtcp.jitter')
        self.assertGreater(r['summary']['observations'],0)
        self.assertEqual(r['summary']['observed_seconds'],0)
        self.assertTrue(r['evidence'][0]['references'][0]['metric_id'])
        self.assertEqual(r['summary']['calls'],1)
        self.assertEqual(self.query(metric='rtcp.jitter',start='2026-01-01T12:00:11')['summary']['observations'],1)

    def test_counter_reset_conflicts_and_hour_crossing(self):
        self.load();db=connect()
        template=dict(db.execute('SELECT * FROM metrics LIMIT 1').fetchone());template.pop('id')
        with db:
            for ts,value,valid in [('12:00:06',10,1),('12:00:10',30,1),('12:00:12',2,1),
                                   ('12:00:14',10,0),('12:00:16',30,1),('12:00:18',40,1),('12:00:18',50,1)]:
                m=template|dict(ts='2026-01-01 '+ts,name='vd.scheduling_delay',value=value,valid=valid,unit='ms',sample_kind='counter')
                db.execute(f"INSERT INTO metrics({','.join(m)}) VALUES({','.join('?' for _ in m)})",list(m.values()))
        db.close()
        r=self.query(metric='vd.scheduling_delay')
        self.assertEqual(r['summary']['total_delta'],20)
        self.assertEqual(r['summary']['rate_per_second'],5)
        self.assertIsNone(r['summary']['mean'])
        self.assertEqual(len(r['evidence'][0]['references']),2)
        self.assertGreater(r['exclusions']['counter_reset_or_gap'],0)
        self.assertGreater(r['exclusions']['invalid_or_conflicting_samples'],0)

    def test_counter_never_allocates_across_hour_or_position(self):
        self.load();db=connect()
        template=dict(db.execute('SELECT * FROM metrics LIMIT 1').fetchone());template.pop('id')
        with db:
            db.execute("UPDATE geo_positions SET ts='2026-01-01 12:59:50.000000'")
            for ts,value in [('12:59:55',10),('13:00:05',30),('13:00:10',40)]:
                m=template|dict(ts='2026-01-01 '+ts+'.000000',name='vd.scheduling_delay',value=value,valid=1,unit='ms',sample_kind='counter')
                db.execute(f"INSERT INTO metrics({','.join(m)}) VALUES({','.join('?' for _ in m)})",list(m.values()))
        db.close()
        r=self.query(metric='vd.scheduling_delay')
        self.assertEqual(r['summary']['total_delta'],10)
        self.assertEqual(r['exclusions']['counter_crosses_time_position_or_network'],1)
        self.assertIsNone(r['profiles']['hour'][12]['total_delta'])
        self.assertEqual(r['profiles']['hour'][13]['total_delta'],10)
        db=connect()
        with db:
            # A delivered fix in another cell invalidates both endpoint localization and any bridge back.
            p=dict(db.execute('SELECT * FROM geo_positions LIMIT 1').fetchone());p.pop('id')
            p.update(ts='2026-01-01 13:00:07.000000',longitude=10,source_line=999)
            db.execute(f"INSERT INTO geo_positions({','.join(p)}) VALUES({','.join('?' for _ in p)})",list(p.values()))
        db.close()
        self.assertEqual(self.query(metric='vd.scheduling_delay')['summary']['observations'],0)

    def test_mcp_real_http_contract_and_bad_request(self):
        self.load();server=Server(f'http://127.0.0.1:{self.server.server_port}')
        server.handle(dict(jsonrpc='2.0',id=1,method='initialize',params=dict(protocolVersion=PROTOCOL,capabilities={},clientInfo={})))
        server.handle(dict(jsonrpc='2.0',method='notifications/initialized'))
        reply=server.handle(dict(jsonrpc='2.0',id=2,method='tools/call',params=dict(name='analytics_geo_temporal',arguments=dict(cell=250,cell_id=grid(45,9,250)[0]))))
        self.assertFalse(reply['result']['isError'])
        self.assertEqual(json.loads(reply['result']['content'][0]['text'])['version'],'geo-temporal-1')
        self.assertIn('geo_temporal',self.request('GET','/api/analytics/catalog')[1])
        status, discovery=self.request('POST','/api/analytics/geo-cells',{'cell':500})
        self.assertEqual(status,200)
        self.assertEqual(discovery['cells'][0]['id'],grid(45,9,500)[0])
        reply=server.handle(dict(jsonrpc='2.0',id=3,method='tools/call',params=dict(name='analytics_geo_cells',arguments={'cell':500})))
        self.assertFalse(reply['result']['isError'])
        self.assertEqual(json.loads(reply['result']['content'][0]['text'])['cells'],discovery['cells'])
        self.assertEqual(self.request('POST','/api/analytics/geo-temporal',{'cell':250,'cell_id':'x'})[0],400)

    def test_duplicates_and_non_app_roles(self):
        self.load();before=self.query()
        f=sample();f['application.log']=fix(5);f['rtplog.txt']=rtcp(6)+rtcp(12);f['extra.txt']='synthetic duplicate'
        self.upload(f)
        self.assertEqual(self.query()['summary']['observed_seconds'],before['summary']['observed_seconds'])
        db=connect()
        with db:
            for pid, in db.execute('SELECT id FROM perspectives').fetchall():
                db.execute("INSERT INTO observation_roles(perspective_id,session,participant,role) VALUES(?,'test','synthetic','xcoder')",(pid,))
        db.close()
        self.assertEqual(self.query()['summary']['observations'],0)
