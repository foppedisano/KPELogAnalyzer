import json
import sqlite3
import unittest
from app import analytics
from app.db import connect, init
from app.mos import score
from tests import test_server as fixture
from tests.fixtures import sample, rtcp


class AnalyticsTests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    request=fixture.APITests.request
    upload=fixture.APITests.upload

    def query(self,sql,**kwargs):
        status,data=self.request('POST','/api/analytics/query',dict(sql=sql,**kwargs))
        self.assertEqual(status,200,data)
        return data

    def test_catalog_views_and_parameters(self):
        self.upload()
        status,catalog=self.request('GET','/api/analytics/catalog')
        self.assertEqual(status,200,catalog)
        for name in catalog['tables']:
            self.query('SELECT COUNT(*) FROM '+name)
        self.assertEqual(self.query('SELECT id FROM a_calls WHERE sip_call_id=:cid',parameters={'cid':'call-a'})['rows'],[[1]])
        for e in catalog['examples']:
            self.query(e['sql'],datasets=e['datasets'],parameters=e['parameters'])
        self.assertEqual(self.query('SELECT * FROM a_calls',scope={'call_ids':[999]})['rows'],[])

    def test_authorizer_scope_and_bounds(self):
        self.upload()
        for sql in ['DELETE FROM a_calls','CREATE TABLE x(a)','PRAGMA database_list',
                    "ATTACH ':memory:' AS other",'SELECT text FROM events',
                    'SELECT COUNT(*) FROM events',"SELECT COUNT(*) FROM 'events'",
                    'WITH a_calls AS (SELECT text FROM events) SELECT * FROM a_calls',
                    'SELECT * FROM sqlite_master','SELECT * FROM a_settings',
                    "SELECT load_extension('x')",'SELECT * FROM pragma_table_info(:name)']:
            code,data=self.request('POST','/api/analytics/query',{'sql':sql,'parameters':{'name':'events'}})
            self.assertEqual(code,400,(sql,data))
        q=self.query('SELECT id FROM a_events ORDER BY id',limit=1)
        self.assertTrue(q['truncated']);self.assertEqual(len(q['rows']),1)
        code,_=self.request('POST','/api/analytics/query',{'sql':'SELECT hex(zeroblob(3000000))'})
        self.assertEqual(code,400)
        self.assertEqual(self.query('SELECT COUNT(*) FROM a_calls')['rows'],[[1]])

    def test_duration_episodes_clipping_evidence_and_gaps(self):
        f=sample();f['rtplog.txt']=rtcp(5).replace('2%.','30%.')+rtcp(10).replace('2%.','30%.')+rtcp(15)
        self.upload(f)
        result=self.query("SELECT covered_seconds,bad_seconds,episode_count,mean FROM a_mos_summary WHERE direction='incoming'",datasets=['mos'])
        covered,bad,episodes,mean=result['rows'][0]
        self.assertEqual((covered,bad,episodes),(15,10,1))
        self.assertAlmostEqual(mean,(score(30)*10+score(2)*5)/15)
        q=self.query("SELECT seconds FROM a_mos_episodes WHERE direction='incoming'",datasets=['mos'],scope={'start':'2026-01-01 12:00:07','end':'2026-01-01 12:00:12'})
        self.assertEqual(q['rows'],[[5]])
        self.assertEqual(self.query('SELECT * FROM a_mos_episodes',datasets=['mos'],min_episode_seconds=11)['rows'],[])
        q=self.query('SELECT e.event_id,e.filename,e.line_no FROM a_mos_evidence e JOIN a_episode_intervals i ON i.interval_id=e.interval_id',datasets=['mos'])
        self.assertTrue(q['rows'])
        status,data=self.request('POST','/api/analytics/evidence',{'event_ids':[q['rows'][0][0],999999]})
        self.assertEqual(status,200);self.assertEqual(data['missing_ids'],[999999]);self.assertFalse(data['raw_text_included'])
        self.assertNotIn('text',data['events'][0])

    def test_invalid_gap_and_separate_streams(self):
        f=sample();f['rtplog.txt']=rtcp(5).replace('2%.','30%.')+rtcp(10).replace('2%.','-1%.')+rtcp(15).replace('2%.','30%.')
        self.upload(f)
        q=self.query("SELECT covered_seconds,episode_count FROM a_mos_summary WHERE direction='incoming'",datasets=['mos'])
        self.assertEqual(q['rows'],[[10,2]])
        q=self.query("SELECT COUNT(*) FROM a_metrics WHERE valid=0")
        self.assertGreater(q['rows'][0][0],0)

    def test_duplicate_exclusion_and_network_expiry(self):
        self.upload();f=sample();f['extra.txt']='Synthetic extra';self.upload(f)
        db=connect()
        with db:
            db.execute("INSERT INTO import_producers(import_id,producer_key,role,platform,status,basis,evidence,method) VALUES(1,'synthetic-source','app','android','recognized','test','[]','test') ON CONFLICT(import_id) DO UPDATE SET producer_key='synthetic-source',role='app'")
            db.execute("INSERT INTO duplicate_perspectives VALUES(2,1,'test')")
        db.close()
        self.assertEqual(self.query('SELECT COUNT(*) FROM a_observations')['rows'],[[1]])
        self.assertEqual(self.query('SELECT COUNT(*) FROM a_observations',scope={'include_duplicates':True})['rows'],[[2]])
        self.assertEqual(self.query('SELECT DISTINCT access,wifi_identity FROM a_mos_network',datasets=['mos'])['rows'],[['unknown',None]])

    def test_recipe_revision_and_current_data(self):
        self.upload()
        recipe=dict(title='Synthetic recipe',question='How many?',definition={'sql':'SELECT COUNT(*) FROM a_calls'})
        code,stored=self.request('POST','/api/analytics/recipes',recipe)
        self.assertEqual(code,201,stored)
        recipe.update(stored);recipe['title']='Updated'
        self.assertEqual(self.request('PATCH','/api/analytics/recipes',recipe)[1]['revision'],2)
        self.assertEqual(self.request('PATCH','/api/analytics/recipes',recipe)[0],400)
        self.upload(sample(cid='another'))
        code,result=self.request('POST','/api/analytics/run-recipe',{'id':stored['id']})
        self.assertEqual(code,200);self.assertEqual(result['rows'],[[2]])
        db=connect();self.assertEqual(db.execute('SELECT COUNT(*) FROM analysis_recipe_revisions').fetchone()[0],2);db.close()

    def test_observer_network_expiry_splits_mos_without_peer_assignment(self):
        from app.mobility import VERSION
        self.upload();db=connect()
        with db:
            db.execute("UPDATE perspectives SET end='2026-01-01 12:00:50.000000'")
            db.execute('''INSERT INTO network_observations(event_id,import_id,source_line,ts,access,upstream,wifi_identity,basis,method)
                VALUES(1,1,1,'2026-01-01 12:00:00.000000','wifi','unknown','synthetic-wifi','synthetic',?)''',(VERSION,))
        db.close()
        q=self.query("SELECT n.access,n.wifi_identity,SUM(n.seconds) FROM a_mos_network n JOIN a_mos m ON m.id=n.interval_id WHERE m.direction='incoming' GROUP BY n.access,n.wifi_identity ORDER BY n.access",datasets=['mos'])
        self.assertEqual(q['rows'],[['unknown',None,10],['wifi','synthetic-wifi',20]])
        q=self.query("SELECT DISTINCT receiver_basis FROM a_mos WHERE direction='outgoing'",datasets=['mos'])
        self.assertEqual(q['rows'],[['remote_unidentified']])

    def test_structured_telemetry(self):
        from tests.test_telemetry_store import events
        self.upload({'telemetry.jsonl':'\n'.join(map(json.dumps,events()))})
        q=self.query('SELECT DISTINCT time_basis FROM a_mos',datasets=['mos'])
        self.assertEqual(q['rows'],[['UTC']])
        q=self.query('SELECT SUM(seconds) FROM a_mos_network',datasets=['mos'])
        self.assertEqual(q['rows'],[[2]])

    def test_upgrade_preserves_data_and_backup(self):
        self.upload();db=connect()
        filename=db.execute('PRAGMA database_list').fetchone()[2]
        with db:
            db.execute('DROP TABLE analysis_recipe_revisions');db.execute('DROP TABLE analysis_recipes')
            from tests.fixtures import remove_periodic_schema
            remove_periodic_schema(db)
            db.execute("UPDATE meta SET value='9' WHERE key='schema_version'")
        init(db);init(db)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],1)
        self.assertEqual(db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'13')
        backup=sqlite3.connect(filename+'.pre-v10.bak')
        self.assertEqual(backup.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'9')
        backup.close();db.close()


if __name__=='__main__':unittest.main()
