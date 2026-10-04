import sqlite3
import unittest

from app.db import init
from app.diagnostics import diagnostics
from app.parser import ingest
from app.topology import save, listing, decorate
from tests import test_enrichment as enrichment_fixture
from tests.test_enrichment import vd
from tests.fixtures import archive, sample, kpe, summary, rtcp, message


def logsets():
    """Two apps and one shared xcoder, four independently identified SIP legs."""
    a, b = sample(cid='app-a'), sample(cid='app-b')
    a['VDlog.txt'], b['VDlog.txt'] = vd(5, 40)+vd(10, 60), vd(5, 80)+vd(10, 90)
    server = {
        'sip_debug.txt': ''.join(message(0,cid)+message(20,cid,method='BYE') for cid in ['server-a','server-b']),
        'kpelog.txt': ''.join(kpe(0,f'Call on lineId [ {line} ] with direction [ 2 ] added to the call list.')+summary(cid=cid,line=line) for line,cid in enumerate(['server-a','server-b'])),
        'rtplog.txt': rtcp(line=0)+rtcp(line=1),
        'VDlog.txt': vd(5,120)+vd(10,140)+(vd(5,160)+vd(10,180)).replace('Line 0','Line 1'),
    }
    return [a,b,server]


class TopologyTests(unittest.TestCase):
    setUp = enrichment_fixture.EnrichmentTests.setUp
    tearDown = enrichment_fixture.EnrichmentTests.tearDown

    def load(self):
        for i,files in enumerate(logsets()):
            ingest(self.db,archive(files),f'synthetic-{i}.zip')

    def test_four_observations_shared_server_no_call_merging(self):
        self.load()
        before = self.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0]
        for pid,person,role in [(1,'Alice','app'),(2,'Bob','app'),(3,'Alice','xcoder'),(4,'Bob','xcoder')]:
            save(self.db,dict(perspective_id=pid,session='Synthetic session',participant=person,role=role,node='Shared node' if role=='xcoder' else person))
        observations=listing(self.db)
        self.assertEqual(len(observations),4)
        self.assertEqual(len({x['call_id'] for x in observations}),4)
        self.assertEqual(len({x['import_id'] for x in observations if x['role']=='xcoder'}),1)
        for pid,device,expected in [(1,'NART0 of Line 0',40),(2,'NART0 of Line 0',80),(3,'NART0 of Line 0',120),(4,'NART0 of Line 1',160)]:
            d=diagnostics(self.db,pid,device_a=device)
            buffer=next(s for s in d['series'] if s['name']=='vd.buffer')
            self.assertEqual(buffer['points'][0]['value'],expected)
            self.assertTrue(buffer['points'][0]['evidence']['event_id'])
            self.assertIn('app' if pid<3 else 'xcoder',d['coverage'][0]['label'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0],before)
        init(self.db)
        self.assertEqual(len(listing(self.db)),4)

    def test_validation_revision_and_no_implicit_roles(self):
        self.load()
        self.assertTrue(all(x['role'] is None for x in listing(self.db)))
        obj=dict(perspective_id=1,session='Case',participant='Person',role='app')
        save(self.db,obj)
        with self.assertRaises(ValueError):save(self.db,obj)
        changed=save(self.db,dict(obj,revision=1,role='unknown'))
        self.assertEqual(changed['revision'],2)
        for bad in [dict(obj,perspective_id=999),dict(obj,role='gateway'),dict(obj,session=''),dict(obj,node=['bad'])]:
            with self.assertRaises(ValueError):save(self.db,bad)

    def test_schema_three_backup_and_annotations_preserved(self):
        self.load()
        before=self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        with self.db:
            from tests.fixtures import remove_periodic_schema
            remove_periodic_schema(self.db)
            for table in ['source_profiles','call_correlations','leg_outcomes']:
                self.db.execute('DROP TABLE '+table)
            self.db.execute("DELETE FROM meta WHERE key LIKE 'conversation-discovery-%'")
            self.db.execute('DROP TABLE observation_roles')
            self.db.execute("UPDATE meta SET value='3' WHERE key='schema_version'")
            self.db.execute("INSERT INTO source_identities(import_id,name) VALUES(1,'Preserved')")
        init(self.db)
        backup=sqlite3.connect(str(self.path)+'.pre-v4.bak')
        self.assertEqual(backup.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'3')
        backup.close()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],before)
        self.assertEqual(self.db.execute('SELECT name FROM source_identities').fetchone()[0],'Preserved')
        self.assertEqual(self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'12')
        init(self.db)


class TopologyAPITests(unittest.TestCase):
    from tests.test_server import APITests
    setUp=APITests.setUp
    tearDown=APITests.tearDown
    request=APITests.request
    upload=APITests.upload

    def test_routes_and_perspective_labels(self):
        self.upload()
        obj=dict(perspective_id=1,session='Demo',participant='Alice',role='xcoder',node='Node one')
        self.assertEqual(self.request('POST','/api/topology',obj)[0],200)
        self.assertEqual(self.request('GET','/api/topology')[1][0]['role'],'xcoder')
        p=self.request('GET','/api/perspectives')[1][0]
        self.assertEqual(p['observation']['participant'],'Alice')
        self.assertIn('xcoder',p['label'])
        self.assertEqual(self.request('POST','/api/topology',obj)[0],400)
        self.assertEqual(self.request('GET','/topology.js')[0],200)
