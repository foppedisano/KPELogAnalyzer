"""Synthetic explicit switch markers, ambiguous context and map evidence."""
import unittest
from app.network_switches import explicit, collect, locate, request, MARKER
from tests import test_enrichment as fixture
from tests.fixtures import sample


def marker(second=10, suffix=''):
    return f'[2026-01-01 12:00:{second:06.3f}] [KPECORE] [INFO] {MARKER}{suffix}\n'


def interface(second, name):
    return f'2026-01-01 12:00:{second:07.4f} [info] [1] : Current network interface: {name}\n'


def files():
    f=sample()
    f['kpelog.txt']+=marker()
    f['App.log']=interface(9,'wifi')+interface(9.9,'cellular')
    f['PhoneEngine.log']='[2026-01-01 12:00:08.000] New location received: Location[gps 45.0,9.0]\n[2026-01-01 12:00:12.000] New location received: Location[gps 45.002,9.002]\n'
    return f


class SwitchTests(unittest.TestCase):
    setUp=fixture.EnrichmentTests.setUp
    tearDown=fixture.EnrichmentTests.tearDown
    load=fixture.EnrichmentTests.load

    def test_explicit_marker_only_and_radio_fields(self):
        self.assertEqual(explicit(marker(),'kpelog.txt')['stage'],'requested')
        s=explicit(marker(suffix=' from EDGE to LTE'),'nested/kpelog-1.txt')
        self.assertEqual((s['previous'],s['next'],s['transition_basis']),('edge','lte','explicit_fields'))
        for text,name in [(marker(),'sip_debug.txt'),('prefix '+marker(),'kpelog.txt'),
            ('header\n'+marker(),'kpelog.txt'),(marker().replace('handle','mention'),'kpelog.txt'),
            ('[2026-01-01 12:00:10.000] [RESIP] [WARNING] Address switchNetwork@example.test','vdklog.txt'),
            ('Network connection changed','PhoneEngine.log'),('INVITE sip:example.test SIP/2.0\nTo: <sip:x@example.test>;tag=1','sip_debug.txt'),
            (marker(suffix=' from <script> to LTE'),'kpelog.txt')]:
            self.assertIsNone(explicit(text,name))

    def test_interface_context_geo_and_read_only(self):
        self.load(files());before=self.db.total_changes
        result=request(self.db,dict(call_id=1))
        self.assertEqual(result['count'],1)
        s=result['events'][0]
        self.assertEqual((s['previous'],s['next']),('wifi','cellular'))
        self.assertEqual(s['transition_basis'],'nearby_interface_observations')
        self.assertEqual(s['location']['basis'],'interpolated')
        self.assertAlmostEqual(s['location']['latitude'],45.001)
        self.assertEqual(len(s['location']['evidence']),2)
        self.assertTrue(s['evidence'][0]['line'])
        self.assertEqual(self.db.total_changes,before)
        self.assertEqual(request(self.db,dict(start='2026-01-01 12:00:11'))['events'],[])

    def test_equal_conflicting_or_multiple_context_is_unknown(self):
        self.load(files())
        self.db.execute("UPDATE network_observations SET access='cellular'")
        self.assertIsNone(collect(self.db)[0]['previous'])
        self.db.execute("UPDATE network_observations SET access='wifi' WHERE id=(SELECT MIN(id) FROM network_observations)")
        self.db.execute("UPDATE network_observations SET ts='2026-01-01 12:00:09.000000'")
        self.assertIsNone(collect(self.db)[0]['next'])

    def test_rotation_duplicates_and_nearby_requests(self):
        f=files();f['kpelog-1.txt']=marker();self.load(f)
        items=collect(self.db)
        self.assertEqual(len(items),1);self.assertEqual(len(items[0]['evidence']),2)
        event=items[0]['event_id']
        self.db.execute("INSERT INTO events(import_id,file_id,line_no,ts,kind,text) SELECT import_id,file_id,line_no+1,'2026-01-01 12:00:11.000000',kind,? FROM events WHERE id=?",(marker(11),event))
        items=collect(self.db)
        self.assertEqual(len(items),2);self.assertTrue(all(x['previous'] is None for x in items))

    def test_overlapping_calls_stay_unassigned_and_unlocated(self):
        self.load(files())
        self.db.execute("UPDATE events SET call_id=NULL,perspective_id=NULL,line_id=NULL WHERE instr(text,?)>0",(MARKER,))
        self.db.execute("INSERT INTO calls(id,call_key,start,end) VALUES(99,'synthetic-overlap','2026-01-01 12:00:00','2026-01-01 12:00:20')")
        self.db.execute("INSERT INTO perspectives(id,call_id,import_id,line_id,start,end) VALUES(99,99,1,0,'2026-01-01 12:00:00','2026-01-01 12:00:20')")
        s=request(self.db,dict(call_id=1))['events'][0]
        self.assertIsNone(s['perspective_id']);self.assertIsNone(s['location'])
        self.assertEqual(s['association'],'unassigned_source_context')

    def test_positions_do_not_snap_or_cross_conflicts(self):
        self.load(files())
        self.db.execute("UPDATE geo_positions SET kind='cached'")
        self.assertIsNone(request(self.db,dict(call_id=1))['events'][0]['location'])
        self.db.execute("UPDATE geo_positions SET kind='sip_config'")
        self.assertIsNone(request(self.db,dict(call_id=1,quality='fresh'))['events'][0]['location'])
        self.db.execute("UPDATE geo_positions SET kind='fresh',ts='2026-01-01 12:00:08.000000'")
        self.assertIsNone(request(self.db,dict(call_id=1))['events'][0]['location'])

    def test_validation(self):
        for params in ({'call_id':True},{'perspective_id':1},{'locate':'yes'},
            {'start':'2026-01-01T12:00:00Z'},{'start':'bad'},{'end':None},{'start':'2026-01-02','end':'2026-01-01'},
            {'quality':'cached'},{'sql':'SELECT 1'}):
            with self.subTest(params=params),self.assertRaises(ValueError):request(self.db,params)


class SwitchAPITests(unittest.TestCase):
    from tests.test_server import APITests as Fixture
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    upload=Fixture.upload
    request=Fixture.request

    def test_event_list_timeline_and_mcp(self):
        self.assertEqual(self.upload(files())[0],201)
        status,data=self.request('POST','/api/analytics/network-switches',dict(call_id=1))
        self.assertEqual(status,200,data);self.assertEqual(data['count'],1)
        status,events=self.request('GET','/api/events?call=1')
        annotated=[e for e in events['events'] if 'network_switch' in e]
        self.assertEqual(len(annotated),1)
        self.assertIn('Wi-Fi',annotated[0]['network_switch']['label'])
        status,global_events=self.request('GET','/api/events?search=switchNetworkEvent')
        switch=global_events['events'][0]['network_switch']
        self.assertEqual(switch['previous'],'wifi')
        self.assertEqual(switch['next'],'cellular')
        self.assertTrue(switch['ts']);self.assertTrue(switch['evidence'])
        status,lanes=self.request('GET','/api/connectivity?calls=1')
        self.assertEqual(lanes[0]['network_switches'][0]['event_id'],data['events'][0]['event_id'])
        from app.mcp_server import Server
        s=Server(f'http://127.0.0.1:{self.server.server_port}');s.ready=True
        reply=s.handle(dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name='analytics_network_switches',arguments=dict(call_id=1))))
        self.assertFalse(reply['result']['isError'])


if __name__=='__main__':unittest.main()
