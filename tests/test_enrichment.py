import sqlite3
import tempfile
import unittest
from pathlib import Path
from app.db import connect, init, SCHEMA
from app.parser import ingest
from app.enrichment import observations
from app.diagnostics import diagnostics, interpolate
from tests.fixtures import archive, sample


def vd(second, buffer=100, silence=0):
 return f'[2026-01-01 12:00:{second:02}.000] [AWT] [INFO]\nDevice name: NART0 of Line 0\nAudio currently in buffer (ms): {buffer}\nsilence msecs skipped so far: {silence}\nring current max buffer usecs (for dynamic dejittering): 20000\nDevice name: Default Audio Input\nAudio currently in buffer (ms): 999\n'


class EnrichmentTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'kpe.sqlite3';self.db=connect(self.path);init(self.db)
 def tearDown(self):
  self.db.close();self.temp.cleanup()
 def load(self, extra, direction='OUTGOING'):
  files=sample(direction=direction);files.update(extra)
  return ingest(self.db,archive(files),'synthetic.zip')
 def test_device_scope_units_twenty_ms_and_rotation(self):
  text=vd(5)
  self.load({'VDlog.txt':text,'VDlog-1.txt':text})
  rows=list(self.db.execute("SELECT * FROM metrics WHERE name LIKE 'vd.%'"))
  self.assertEqual(len(rows),3)
  self.assertTrue(all(m['call_id'] for m in rows))
  self.assertEqual([m['value'] for m in rows if m['name']=='vd.buffer'],[100])
  target=next(m for m in rows if m['name']=='vd.dejitter_target')
  self.assertEqual((target['value'],target['raw_value'],target['source_line']),(20,20000,5))
 def test_legacy_and_warning(self):
  text='[NART0 of Line 0] [WARNING] Found new max for  m_maxPktArrivalTimeDelay to ms  409.19 . Previous value was ms  20 .'
  m=list(observations(text,'VDlog.txt'))[0]
  self.assertEqual((m['value'],m['sample_kind']),(409.19,'event'))
  old='[x]\nDevice name: NART0 of Line 0\nbuffer len in usecs: 125000\nsilence usecs skipped so far: 2000000'
  self.assertEqual([m['value'] for m in observations(old,'VDlog.txt')],[125,2000])
  rtp='[2026-01-01 12:00:10.000] [RTP SESSION FOR LINE 0 FLOW 0]\nRTT by this source: 47607microseconds'
  self.load({'rtplog-old.txt':rtp})
  self.assertEqual(self.db.execute("SELECT value FROM metrics WHERE extractor='vd-1'").fetchone()[0],47.607)
 def test_unscoped_warning_never_guesses_device(self):
  self.assertEqual(list(observations('[WARNING] m_maxPktArrivalTimeDelay to ms 9','VDlog.txt')),[])
 def test_version_marker_and_idempotent_enrichment(self):
  self.load({'PhoneEngine.log':'[2026-01-01 12:00:00.000] KPE setAppInfo configured with name=Example, version=1.5.0','VDlog.txt':vd(5)})
  count=self.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0]
  init(self.db);init(self.db)
  self.assertEqual(count,self.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0])
  self.assertEqual(diagnostics(self.db,1)['coverage'][0]['version']['version'],'1.5.0')
 def test_delta_reset_and_sum_interpolation(self):
  self.load({'VDlog.txt':vd(5,100,100)+vd(10,200,300)+vd(15,300,20)})
  self.load({'VDlog.txt':vd(5,50,0)+vd(15,150,100)},'INCOMING')
  result=diagnostics(self.db,1,2)
  summed=next(s for s in result['series'] if s['name']=='derived.buffer_sum')
  self.assertEqual([p['value'] for p in summed['points']],[150,300,450])
  delta=next(s for s in result['series'] if s['name']=='derived.silence_delta' and s['side']=='A')
  self.assertEqual([p['value'] for p in delta['points']],[200])
  self.assertEqual(len(delta['points'][0]['evidence']),2)
  with self.assertRaises(ValueError): diagnostics(self.db,1,1)
 def test_no_interpolation_across_gap_or_extrapolation(self):
  points=[dict(t=0,value=1,evidence=1),dict(t=40,value=10,evidence=2)]
  self.assertIsNone(interpolate(points,20));self.assertIsNone(interpolate(points,-1))
  self.assertEqual(interpolate(points,40),(10,[2]))
 def test_migration_preserves_data_and_creates_backup(self):
  self.db.close();self.path.unlink()
  self.db=connect(self.path);self.db.executescript(SCHEMA)
  with self.db:
   self.db.execute("INSERT INTO imports(id,name,sha256,label,clock_offset) VALUES(1,'old.zip','hash','Label',2.5)")
   self.db.execute("INSERT INTO calls(id,call_key,start) VALUES(8,'manual','2026-01-01 12:00:00.000000')")
   self.db.execute("INSERT INTO conversations(id,title,note) VALUES(4,'Keep','Evidence')")
  init(self.db)
  self.assertTrue(self.path.with_name('kpe.sqlite3.pre-v2.bak').exists())
  self.assertEqual(self.db.execute('SELECT clock_offset FROM imports').fetchone()[0],2.5)
  self.assertEqual(self.db.execute('SELECT id FROM calls').fetchone()[0],8)
  self.assertEqual(self.db.execute('SELECT note FROM conversations').fetchone()[0],'Evidence')
  self.assertEqual(self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'13')
  init(self.db)

 def test_offsets_affect_overlap_without_changing_raw_timestamps(self):
  self.load({'VDlog.txt':vd(5,100)+vd(15,200)})
  self.load({'VDlog.txt':vd(5,50)+vd(15,150)},'INCOMING')
  original=self.db.execute('SELECT ts FROM metrics ORDER BY id LIMIT 1').fetchone()[0]
  with self.db: self.db.execute('UPDATE imports SET clock_offset=60 WHERE id=2')
  result=diagnostics(self.db,1,2)
  self.assertEqual(next(s for s in result['series'] if s['name']=='derived.buffer_sum')['points'],[])
  self.assertEqual(self.db.execute('SELECT ts FROM metrics ORDER BY id LIMIT 1').fetchone()[0],original)
 def test_multiple_nart_sections_keep_lines_separate(self):
  text=vd(5)+'Device name: NART1 of Line 9\nAudio currently in buffer (ms): 888\n'
  self.load({'VDlog.txt':text})
  m=self.db.execute("SELECT call_id,device FROM metrics WHERE name='vd.buffer' AND value=888").fetchone()
  self.assertIsNone(m['call_id']);self.assertEqual(m['device'],'NART1 of Line 9')
