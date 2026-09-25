import json
import sqlite3
import unittest
from app.analyses import save
from app.identity import candidates,confirm
from app.manual import import_text,manual_window
from app.diagnostics import diagnostics
from app.db import init
from tests import test_enrichment as fixtures
vd=fixtures.vd
from tests.fixtures import message

class WorkspaceTests(unittest.TestCase):
 setUp=fixtures.EnrichmentTests.setUp
 tearDown=fixtures.EnrichmentTests.tearDown
 load=fixtures.EnrichmentTests.load
 def test_both_sums_jitter_loss_and_time_filter(self):
  self.load({'VDlog.txt':vd(5,100)+vd(10,200)+vd(15,300)})
  self.load({'VDlog.txt':vd(5,50)+vd(15,150)},'INCOMING')
  result=diagnostics(self.db,1,2,start='2026-01-01 12:00:05',end='2026-01-01 12:00:10')
  names={s['name'] for s in result['series']}
  self.assertTrue({'rtcp.jitter','rtcp.loss','derived.buffer_sum','derived.dejitter_sum'}<=names)
  target=next(s for s in result['series'] if s['name']=='derived.dejitter_sum')
  self.assertEqual([p['value'] for p in target['points']],[40])
  loss=[s for s in result['series'] if s['name']=='rtcp.loss' and s['side']=='A']
  self.assertEqual({s['direction'] for s in loss},{'incoming','outgoing'})
  self.assertEqual({s['unit'] for s in loss},{'%'})
  for s in result['series']:
   self.assertTrue(all(result['window']['start']<=p['t']<=result['window']['end'] for p in s['points']))
 def test_save_reload_revision_and_style_validation(self):
  self.load({'VDlog.txt':vd(5)})
  cfg=dict(a=1,b=None,metrics=['rtcp.loss','vd.silence_skipped'],silence_unit='ms',offset_a=3,styles={'series':{'color':'#ff00aa','symbol':'triangle','visible':False}})
  row=save(self.db,dict(title='Case',config=cfg));self.assertEqual(json.loads(row['config'])['offset_a'],3)
  changed=save(self.db,dict(id=row['id'],revision=1,title='Changed',config=cfg),True)
  self.assertEqual(changed['revision'],2)
  with self.assertRaises(ValueError):save(self.db,dict(id=row['id'],revision=1,title='Stale',config=cfg),True)
  cfg['styles']['series']['color']='url(javascript:x)'
  with self.assertRaises(ValueError):save(self.db,dict(title='Bad',config=cfg))
  init(self.db);self.assertEqual(self.db.execute('SELECT title FROM saved_analyses').fetchone()[0],'Changed')
 def test_window_edit_preserves_ids_reassigns_and_audits(self):
  imported=import_text(self.db,dict(files=[dict(name='VDlog.txt',text=vd(5)+vd(15))]))
  w=manual_window(self.db,dict(import_id=imported['id'],line_id=0,start='2026-01-01 12:00:00',end='2026-01-01 12:00:20'))
  changed=manual_window(self.db,dict(perspective_id=w['perspective_id'],line_id=0,start='2026-01-01 12:00:10',end='2026-01-01 12:00:20',title='Fixed'),True)
  self.assertEqual(w,changed)
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM metrics WHERE call_id IS NULL').fetchone()[0],3)
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM window_revisions').fetchone()[0],1)
  with self.assertRaises(ValueError):manual_window(self.db,dict(import_id=imported['id'],line_id=0,start='2026-01-01 12:00:18',end='2026-01-01 12:00:30'))
 def test_sip_identity_does_not_confuse_peer_or_responses(self):
  outgoing=message(0,method='REGISTER').replace('From: <sip:','From: "Alice Test" <sip:')
  self.load({'sip_debug-local.txt':outgoing})
  result=candidates(self.db,1)
  registered=[c for c in result['candidates'] if c['basis'].startswith('REGISTER')]
  self.assertEqual(len(registered),1)
  self.assertEqual(registered[0]['display_name'],'Alice Test')
  self.assertIn('alice',registered[0]['account'])
  self.assertNotIn('Authorization',json.dumps(result))
  confirm(self.db,dict(import_id=1,name='Confirmed Alice',account=registered[0]['account'],event_ids=[registered[0]['evidence'][0]['event_id']]))
  self.assertEqual(candidates(self.db,1)['confirmed']['name'],'Confirmed Alice')
  with self.assertRaises(ValueError):confirm(self.db,dict(import_id=1,name='Bad',event_ids=[999999]))
 def test_schema_two_upgrade_preserves_rows(self):
  self.load({'VDlog.txt':vd(5)})
  before=self.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0]
  with self.db:
   for table in ['saved_analyses','source_identities','window_revisions','observation_roles']:self.db.execute('DROP TABLE '+table)
   self.db.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
  init(self.db)
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0],before)
  backup=sqlite3.connect(self.path.with_name('kpe.sqlite3.pre-v3.bak'))
  self.assertEqual(backup.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'2');backup.close()
  init(self.db)

class WorkspaceAPITests(unittest.TestCase):
 from tests import test_server as server_fixture
 setUp=server_fixture.APITests.setUp
 tearDown=server_fixture.APITests.tearDown
 request=server_fixture.APITests.request
 upload=server_fixture.APITests.upload
 def test_save_identity_and_window_routes(self):
  self.upload()
  status,row=self.request('POST','/api/saved-analyses',dict(title='API example',config=dict(a=1,metrics=['rtcp.loss'],silence_unit='ms')))
  self.assertEqual(status,201)
  self.assertEqual(len(self.request('GET','/api/saved-analyses')[1]),1)
  status,updated=self.request('PATCH','/api/saved-analyses',dict(id=row['id'],revision=1,title='Updated',config=json.loads(row['config'])))
  self.assertEqual(status,200);self.assertEqual(updated['revision'],2)
  self.assertEqual(self.request('GET','/api/identities?import=1')[0],200)
  self.assertEqual(self.request('POST','/api/identities',dict(import_id=1,name='Analyst label',note='Synthetic manual association'))[0],200)
  self.assertEqual(self.request('GET','/api/windows')[1],[])
  self.assertEqual(self.request('PATCH','/api/windows',dict(perspective_id=1,line_id=0,start='2026-01-01 12:00:00',end='2026-01-01 12:00:10'))[0],400)
  response=self.request('GET','/api/diagnostics?a=1&start=2026-01-01%2012:00:09&end=2026-01-01%2012:00:11')[1]
  self.assertIn('rtcp.loss',[s['name'] for s in response['series']])
