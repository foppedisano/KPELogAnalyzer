import unittest
from tests import test_periodic as periodic_fixture
from tests.test_periodic import block
from tests.fixtures import sample, archive
from app.parser import ingest
from app.analytics import query, validate
from app.transients import signals, observed_timestamp
from app.incidents import incidents
from tests.test_analytics_incidents import audio


class TransientPatterns(unittest.TestCase):
    def test_whitelist_and_requests(self):
        self.assertEqual(list(signals('Received route change notification: AVAudioSessionRouteChangeReason(rawValue: 3)'))[0][0],'audio_route_change')
        self.assertEqual(list(signals('Setting audio input 0 mute status to  true'))[0][2],'true')
        for text in ('Currently mutedReasons: 0','Checking mute status of input device 0','The current interruption filter is 1','AudioState[startAudioSession','Creating device personal-file.wav','ChatEngine resume','SIP/2.0 200 OK\nTo: <sip:a@example.test>;tag=x'):
            self.assertEqual(list(signals(text)),[])
        request='SIP message:\nINVITE sip:a@example.test SIP/2.0\nTo: <sip:a@example.test>;tag=x\n\n'
        self.assertEqual(list(signals(request))[0][0],'sip_reinvite')
        self.assertEqual(list(signals(request.replace(';tag=x',''))),[])
        self.assertEqual(list(signals('SIP/2.0 200 OK\nTo: <sip:a@example.test>;tag=x\n\n'+request)),[])
        same=': Network changed from SSID: unknown - IP: 192.0.2.1 to SSID: unknown - IP: 192.0.2.1'
        self.assertEqual(list(signals(same)),[])
        self.assertEqual(list(signals(same.replace('to SSID: unknown - IP: 192.0.2.1','to SSID: unknown - IP: 192.0.2.2')))[0][0],'network_configuration_change')

    def test_observed_android_clock_and_validation(self):
        self.assertEqual(observed_timestamp('2026-01-01 12:00:05:123 I/AudioImpl : x',None),('2026-01-01 12:00:05.123000','log_android_milliseconds'))
        for v in (True,-1,31,float('nan')):
            with self.assertRaises(ValueError):validate(dict(sql='SELECT 1',transient_tolerance_seconds=v))


class TransientAnalytics(unittest.TestCase):
    setUp=periodic_fixture.PeriodicTests.setUp
    tearDown=periodic_fixture.PeriodicTests.tearDown

    def load(self):
        files=sample()
        files['VDlog.txt']=block(3,value=10)+block(5,value=30)+block(7,value=30)
        files['PhoneEngine.log']='2026-01-01 12:00:04.0000 [debug] : Received route change notification: AVAudioSessionRouteChangeReason(rawValue: 3)\n'
        ingest(self.db,archive(files),'synthetic.zip')

    def q(self,sql,**kw):
        return query(self.db,dict(sql=sql,datasets=['transients'],**kw))['rows']

    def test_denominators_initial_evidence_and_no_raw_text(self):
        self.load()
        rows=self.q("SELECT total_intervals,intervals_with_transient,positive_intervals_with_transient,positive_intervals_without_any_transient FROM a_counter_transient_summary WHERE name='vd.silence_played' AND type='audio_route_change'")
        self.assertEqual(rows,[[2,1,1,0]])
        self.assertEqual(self.q("SELECT value,localizable FROM a_counter_initial_observations WHERE name='vd.silence_played'"),[[10,0]])
        self.assertEqual(self.q("SELECT basis,attribution_basis,filename,line_no FROM a_transients WHERE type='audio_route_change'"),[['observed','unique_source_window','PhoneEngine.log',1]])
        with self.assertRaises(Exception):self.q('SELECT text FROM a_transients')

    def test_scope_is_not_initial_and_tolerance(self):
        self.load()
        self.assertEqual(self.q("SELECT COUNT(*) FROM a_counter_initial_observations WHERE name='vd.silence_played'",scope={'start':'2026-01-01 12:00:04'}),[[0]])
        self.assertEqual(self.q("SELECT intervals_with_transient FROM a_counter_transient_summary WHERE name='vd.silence_played' AND type='audio_route_change'",transient_tolerance_seconds=1),[[2]])

    def test_overlapping_perspectives_stay_unassigned_even_scoped(self):
        self.load()
        with self.db:
            cid=self.db.execute("INSERT INTO calls(call_key,start,end) VALUES('overlap','2026-01-01 12:00:00','2026-01-01 12:00:20')").lastrowid
            self.db.execute("INSERT INTO perspectives(call_id,import_id,line_id,start,end) VALUES(?,1,1,'2026-01-01 12:00:00','2026-01-01 12:00:20')",(cid,))
        self.assertEqual(self.q("SELECT perspective_id FROM a_transients WHERE type='audio_route_change'",scope={'call_ids':[1]}),[[None]])

    def test_nawt_episodes_separate_wrong_line(self):
        files=sample()
        files['VDlog.txt']=audio('03.000','start',observer='NAWT0 of Line 0',device='Default Audio Input')+audio('03.040','end',40,observer='NAWT0 of Line 0',device='Default Audio Input')+audio('03.040','end',90,observer='NAWT0 of Line 1',device='Default Audio Input')
        ingest(self.db,archive(files),'synthetic.zip')
        result=incidents(self.db,1)['episodes']
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['duration_ms'],40)

    def test_summary_over_100_and_metrics_unchanged(self):
        self.load()
        with self.db:
            for i in range(101):
                cid=self.db.execute('INSERT INTO calls(call_key) VALUES(?)',(f'synthetic-{i}',)).lastrowid
                self.db.execute("INSERT INTO perspectives(call_id,import_id,line_id,start,end) VALUES(?,1,NULL,'2026-01-01 12:00:00','2026-01-01 12:00:20')",(cid,))
        r=query(self.db,dict(sql='SELECT COUNT(*) FROM a_incident_call_summary',datasets=['incident_summary']))
        self.assertEqual(r['rows'],[[102]])
        sql="SELECT name,COUNT(*) FROM a_metrics WHERE name IN ('vd.buffer','vd.dejitter_target') GROUP BY name"
        self.assertEqual(query(self.db,dict(sql=sql))['rows'],query(self.db,dict(sql=sql,datasets=['incident_summary']))['rows'])

    def test_recreation_does_not_close_previous_episode(self):
        files=sample()
        files['VDlog.txt']=audio('03.000','start',observer='NAWT0 of Line 0',device='Default Audio Input')+'[2026-01-01 12:00:03.020] [VDFACTORY] [INFO] Creating device NAWT0 of Line 0\n'+audio('03.040','end',10,observer='NAWT0 of Line 0',device='Default Audio Input')
        ingest(self.db,archive(files),'synthetic.zip')
        result=incidents(self.db,1)['episodes']
        self.assertEqual(len(result),2)
        self.assertEqual({r['status'] for r in result},{'open','closed'})

    def test_simultaneous_observers_and_rotation_evidence(self):
        files=sample()
        message='We reset the VOD timing to avoid continuous false warnings.'
        nawt=f'[2026-01-01 12:00:04.000] [NAWT0 of Line 0] [WARNING] {message}\n'
        nart=f'[2026-01-01 12:00:04.000] [NART0 of Line 0] [WARNING] {message}\n'
        files['VDlog.txt']=block(3)+nawt+nart+block(5,value=30)
        files['VDlog-1.txt']=nawt
        ingest(self.db,archive(files),'synthetic.zip')
        self.assertEqual(self.q("SELECT COUNT(*) FROM a_transients WHERE type='scheduling_reset'"),[[2]])
        self.assertEqual(self.q("SELECT COUNT(*) FROM a_transient_evidence e JOIN a_transients t ON t.id=e.transient_id WHERE t.type='scheduling_reset'"),[[3]])


if __name__=='__main__':unittest.main()
