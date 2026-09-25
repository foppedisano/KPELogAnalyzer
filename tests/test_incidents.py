import unittest
from app.incidents import signal,reconstruct,incidents
from tests import test_enrichment as fixture
from app.diagnostics import diagnostics

def e(second,text,id=1):
 return dict(id=id,ts=f'2026-01-01 12:00:{second:02}.000000',text=f'[2026-01-01 12:00:{second:02}.000] '+text,filename='VDlog.txt',line_no=id)
class IncidentTests(unittest.TestCase):
 def signals(self,events):return [s for ev in events if (s:=signal(ev,'NART0 of Line 0',0))]
 def test_distinct_observers_and_declared_duration(self):
  events=[]
  for i,observer in enumerate(['AWT - Default Audio Output','VD recording.wav']):
   events.extend([e(5,f'[{observer}] [WARNING] Buffer underrun occurred on output device while trying to get data from input device NART0 of Line 0 .',i+1),e(6,f'[{observer}] [WARNING] Buffer underrun event terminated while getting data from input device NART0 of Line 0 . Event was 60 msecs long.',i+3)])
  result=reconstruct(self.signals(events));self.assertEqual(len(result),2)
  self.assertTrue(all(x['duration_ms']==60 and x['wall_span_ms']==1000 for x in result))
 def test_missing_threshold_recovery_dedup_and_open(self):
  a=e(10,'[CORE] Line 0 reported that flow 0 has not received RTP media for more than 5000 ms')
  b=e(10,'[KPECORE] Line 0 reported that flow 0 has not received RTP media for more than 5 sec',2)
  r=e(12,'[KPECORE] Line 0 reported that flow 0 has re-started receiving RTP media',3)
  result=reconstruct(self.signals([a,b,r]));self.assertEqual(len(result),1)
  self.assertEqual(result[0]['duration_ms'],7000);self.assertEqual(result[0]['duration_basis'],'minimum')
  self.assertEqual(reconstruct(self.signals([a]))[0]['status'],'open')
 def test_orphans_counters_wrong_line(self):
  r=e(12,'[CORE] Line 0 reported that flow 0 has started receiving RTP media again')
  self.assertIsNone(reconstruct(self.signals([r]))[0]['duration_ms'])
  self.assertIsNone(signal(e(10,'[NART0 of Line 0] number of buffer underruns occurred on this ring for this VOD: 5'),'NART0 of Line 0',0))
  self.assertIsNone(signal(r,'NART0 of Line 0',1))
 def test_periodic_ongoing_duration_without_start(self):
  r=e(12,'[AWT] Still in buffer underrun while getting data from input device NART0 of Line 0 . Event is currently 1000 msecs long.')
  episode=reconstruct(self.signals([r]))[0]
  self.assertEqual(episode['duration_ms'],1000);self.assertEqual(episode['duration_basis'],'minimum')

class IncidentIntegrationTests(unittest.TestCase):
 setUp=fixture.EnrichmentTests.setUp
 tearDown=fixture.EnrichmentTests.tearDown
 load=fixture.EnrichmentTests.load
 def test_interval_crossing_filter_and_offsets(self):
  text=e(5,'[AWT] Buffer underrun occurred on output device while trying to get data from input device NART0 of Line 0 .')['text']+'\n'+e(15,'[AWT] Buffer underrun event terminated while getting data from input device NART0 of Line 0 . Event was 10000 msecs long.')['text']
  self.load({'VDlog.txt':text})
  result=diagnostics(self.db,1,start='2026-01-01 12:00:10',end='2026-01-01 12:00:12',offset_a=1)
  episode=result['incidents'][0]
  self.assertEqual(episode['duration_ms'],10000);self.assertTrue(episode['clipped'])
  self.assertEqual(episode['plot_end']-episode['plot_start'],2)
  self.assertEqual(len(episode['evidence']),2)
