"""Synthetic SIP correlation and Android export regression coverage."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from app.db import connect, init
from app.parser import ingest
from app.conversation_discovery import groups, profiles, sip_headers
from tests.fixtures import archive, sample, message
from tests.test_enrichment import vd

UUID='11111111-2222-4333-8444-555555555555'
OTHER='aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'


class ConversationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.sqlite3'
  self.db=connect(self.path);init(self.db)
 def tearDown(self):
  self.db.close();self.temp.cleanup()
 def load(self,cid,uid=UUID,android=False,elsewhere=False):
  files=sample(cid)
  if uid:files['sip_debug.txt']=files['sip_debug.txt'].replace('Content-Length: 0',f'X-Call-UUID: {{{uid}}}\nContent-Length: 0',1)
  if elsewhere:files['sip_debug.txt']+=message(4,cid,method='CANCEL').replace('Content-Length: 0','Reason: SIP;cause=200;text="Call completed elsewhere"\nContent-Length: 0')
  if android:
   files.pop('CallInfo.log')
   files['kpe-android_0.log']='Android wrapper log'
   files['info.log']='DEVICE MODEL: Synthetic\nOS VERSION: 16\nAPP VERSION: 1.2.3\nPASSWORD: should-not-be-metadata\n'
  else:files['ios_hwwrapper.log']='iOS wrapper'
  files['VDlog.txt']=vd(5)+vd(10,200)
  return ingest(self.db,archive(files),cid+'.zip')
 def test_android_same_extractors_and_export_metadata(self):
  self.load('a');self.load('b',android=True)
  p=profiles(self.db)[2]
  self.assertEqual((p['platform'],p['model'],p['app_version']),('android','Synthetic','1.2.3'))
  self.assertEqual(p['version_scope'],'export_metadata');self.assertFalse(p['has_periodic_callinfo'])
  self.assertNotIn('PASSWORD',str(p));self.assertEqual(len(p['evidence']),3)
  self.assertEqual(self.db.execute('SELECT count(*) FROM app_versions').fetchone()[0],0)
  for pid in (1,2):
   self.assertEqual(self.db.execute("SELECT count(*) FROM metrics WHERE perspective_id=? AND name='vd.buffer'",(pid,)).fetchone()[0],2)
   self.assertEqual(self.db.execute("SELECT value FROM metrics WHERE perspective_id=? AND name='rtcp.rtt'",(pid,)).fetchone()[0],42.25)
 def test_shared_uuid_groups_different_calls_without_merging(self):
  self.load('a');self.load('b',android=True,elsewhere=True)
  g=groups(self.db)[0]
  self.assertEqual(g['call_ids'],[1,2]);self.assertEqual(g['kind'],'uuid');self.assertFalse(g['review'])
  self.assertEqual(g['perspectives'][1]['display_status'],'answered_elsewhere')
  self.assertEqual(len(g['evidence']),2)
  for proof in g['evidence']:
   event=self.db.execute('SELECT text,line_no FROM events WHERE id=?',(proof['event_id'],)).fetchone()
   self.assertIn('X-Call-UUID',event['text'].splitlines()[proof['source_line']-event['line_no']])
  counts=[self.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('calls','metrics','call_correlations')]
  init(self.db);init(self.db)
  self.assertEqual(counts,[self.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('calls','metrics','call_correlations')])
 def test_time_overlap_and_invalid_uuid_do_not_link(self):
  self.load('a',None);self.load('b','not-a-uuid');self.load('c','00000000-0000-0000-0000-000000000000')
  self.assertEqual(groups(self.db),[])
  self.assertEqual(sip_headers('X-Call-UUID: '+UUID),[])
  self.assertEqual(sip_headers(message(0)+'X-Call-UUID: '+UUID),[])
 def test_reused_identifier_is_flagged(self):
  self.load('a');self.load('b')
  with self.db:self.db.execute("UPDATE perspectives SET start='2026-02-01 12:00:00' WHERE id=2")
  self.assertTrue(groups(self.db)[0]['review'])
 def test_conflicting_identifiers_flagged_and_sessions_preserved(self):
  self.load('a');self.load('b')
  files=sample('a');files['sip_debug.txt']=files['sip_debug.txt'].replace('Content-Length: 0',f'X-Call-UUID: {OTHER}\nContent-Length: 0',1)
  ingest(self.db,archive(files),'third.zip')
  with self.db:
   self.db.execute("INSERT INTO conversations(id,title,note) VALUES(1,'Manual','Evidence')")
   self.db.executemany('INSERT INTO conversation_calls VALUES(1,?)',[(1,),(2,)])
   self.db.execute("INSERT INTO observation_roles(perspective_id,session,participant,role) VALUES(1,'Case','A','xcoder')")
  gs=groups(self.db)
  self.assertTrue(all(g['review'] for g in gs if g['kind']=='uuid'))
  self.assertEqual({g['kind'] for g in gs},{'uuid','manual','session'})
 def test_v4_upgrade_backup_and_annotations(self):
  self.load('a');self.load('b',android=True)
  count=self.db.execute('SELECT count(*) FROM metrics').fetchone()[0]
  with self.db:
   self.db.execute("INSERT INTO observation_roles(perspective_id,session,participant,role) VALUES(1,'Case','A','app')")
   for t in ('source_profiles','call_correlations','leg_outcomes'):self.db.execute('DROP TABLE '+t)
   self.db.execute("DELETE FROM meta WHERE key LIKE 'conversation-discovery-%'")
   self.db.execute("UPDATE meta SET value='4' WHERE key='schema_version'")
  init(self.db)
  self.assertEqual(count,self.db.execute('SELECT count(*) FROM metrics').fetchone()[0])
  self.assertEqual(self.db.execute('SELECT participant FROM observation_roles').fetchone()[0],'A')
  with sqlite3.connect(str(self.path)+'.pre-v5.bak') as old:
   self.assertEqual(old.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'4')
  old.close()
  self.assertEqual(profiles(self.db)[2]['platform'],'android')
  self.assertTrue(any(g['kind']=='uuid' for g in groups(self.db)))
