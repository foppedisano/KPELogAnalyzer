import unittest
from tests import test_server as fixture
from tests.fixtures import sample
from app.analytics_incidents import union_length


def audio(ts,phase,duration=None,observer='AWT - Default Audio Output',device='NART0 of Line 0'):
    message={'start':'Buffer underrun occurred on output device while trying to get data from',
             'end':'Buffer underrun event terminated while getting data from',
             'ongoing':'Still in buffer underrun while getting data from'}[phase]
    suffix='' if duration is None else f" Event {'was' if phase=='end' else 'is currently'} {duration} msecs long."
    return f'[2026-01-01 12:00:{ts}] [{observer}] [WARNING] {message} input device {device} .{suffix}\n'


class AudioAnalyticsTests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    request=fixture.APITests.request
    upload=fixture.APITests.upload

    def query(self,sql,**kwargs):
        status,data=self.request('POST','/api/analytics/query',dict(sql=sql,datasets=['incidents'],scope={'call_ids':[1]},**kwargs))
        self.assertEqual(status,200,data)
        return data

    def test_split_declared_duration_not_log_span_and_evidence(self):
        f=sample();f['VDlog.txt']=audio('02.500','start')+audio('03.400','end',600)
        self.upload(f)
        sql='SELECT window_index,underrun_ms,percent FROM a_incident_windows WHERE window_index<2 ORDER BY window_index'
        self.assertEqual(self.query(sql)['rows'],[[0,200,20],[1,400,40]])
        self.assertEqual(self.query(sql,incident_time_basis='log_span')['rows'],[[0,500,50],[1,400,40]])
        q=self.query('SELECT duration_ms,wall_span_ms,observer,device FROM a_incidents')['rows'][0]
        self.assertEqual(q[0],600);self.assertAlmostEqual(q[1],900,places=3)
        self.assertEqual(q[2:],['AWT - Default Audio Output','NART0 of Line 0'])
        refs=self.query('SELECT DISTINCT e.event_id,e.filename,e.line_no FROM a_incident_window_members w JOIN a_incident_evidence e ON e.incident_id=w.incident_id')['rows']
        self.assertEqual(len(refs),2);self.assertTrue(all(r[1]=='VDlog.txt' for r in refs))

    def test_overlap_union_and_observers_separate(self):
        f=sample();f['VDlog.txt']=audio('03.400','end',600)+audio('03.600','end',400)+audio('03.400','end',600,observer='VD synthetic.wav')
        self.upload(f)
        rows=self.query("SELECT observer,SUM(underrun_ms),MAX(percent) FROM a_incident_windows GROUP BY observer ORDER BY observer")['rows']
        self.assertEqual(rows,[['AWT - Default Audio Output',800,60],['VD synthetic.wav',600,40]])
        self.assertEqual(union_length([(0,600),(200,400),(500,1000)]),1000)

    def test_open_missing_duration_and_wrong_line(self):
        f=sample();f['VDlog.txt']=audio('02.500','start')+audio('03.400','ongoing',600)+audio('04.000','end',500,device='NART0 of Line 1')
        self.upload(f)
        self.assertEqual(self.query('SELECT status FROM a_incidents')['rows'],[['open']])
        q=self.query('SELECT DISTINCT percent,incomplete FROM a_incident_windows')['rows']
        self.assertEqual(q,[[None,1]])

    def test_period_clips_windows_not_episode_evidence(self):
        f=sample();f['VDlog.txt']=audio('02.500','start')+audio('03.400','end',600)
        self.upload(f)
        status,q=self.request('POST','/api/analytics/query',dict(sql='SELECT window_ms,underrun_ms,percent FROM a_incident_windows ORDER BY window_index',datasets=['incidents'],scope={'call_ids':[1],'start':'2026-01-01 12:00:02.900','end':'2026-01-01 12:00:03.200'}))
        self.assertEqual(status,200,q);self.assertEqual(q['rows'],[[100,100,100],[200,200,100]])

    def test_no_evidence_is_not_zero_underrun(self):
        self.upload()
        self.assertEqual(self.query('SELECT * FROM a_incident_windows')['rows'],[])
        self.assertEqual(self.query('SELECT episode_count FROM a_incident_coverage')['rows'],[[0]])


if __name__=='__main__':unittest.main()
