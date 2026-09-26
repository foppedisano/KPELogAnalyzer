import json
import sqlite3
import unittest
from pathlib import Path
from tests import test_server as fixture
from tests.fixtures import sample
from app.db import connect,init
from app.mobility import observations,pending,Context


def location(s,lat=45,elapsed=None):
    return f'2026-01-01 12:00:{s:02}:000 I/PhoneService : New location received: Location[fused {lat},9 hAcc=10 et=+{elapsed or s}s]\n'


def interface(s,name):
    return f'2026-01-01 12:00:{s:02}.0000 [info] [1] : Current network interface: {name}\n'


class MobilityTests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    upload=fixture.APITests.upload
    request=fixture.APITests.request

    def test_context_changes_split_mos_and_filter_both_layers(self):
        f=sample();f['application.log']=location(5)+location(10)+location(15)
        f['App.log']=interface(8,'cellular')+interface(15,'wifi')
        self.upload(f)
        all_data=self.request('GET','/api/geography')[1]
        self.assertEqual(all_data['seconds'],10)
        self.assertEqual(all_data['network_known_percent'],100)
        mobile=self.request('GET','/api/geography?upstream=mobile_direct')[1]
        self.assertEqual(mobile['seconds'],5)
        wifi=self.request('GET','/api/geography?access=wifi')[1]
        self.assertEqual(wifi['seconds'],5)
        self.assertEqual(self.request('GET','/api/geography?operator=missing')[1]['cells'],[])
        self.assertEqual(self.request('GET','/api/geography?access=ethernet')[1]['locations'],[])
        self.assertEqual(self.request('GET','/api/geography?platform=desktop')[1]['seconds'],0)
        self.assertEqual(all_data['mobility']['samples'],3)
        self.assertEqual(all_data['mobility']['sequences'],1)
        db=connect();points=db.execute('SELECT ordinal,fix_at,speed_mps FROM movement_samples ORDER BY ordinal').fetchall()
        self.assertEqual([p[0] for p in points],[1,2,3]);self.assertTrue(all(p[1] is None and p[2] is None for p in points));db.close()

    def test_unknown_expiry_and_no_future_context(self):
        f=sample();f['application.log']=location(5);f['App.log']='2026-01-01 11:59:45.0000 [info] [1] : Current network interface: cellular\n'
        self.upload(f)
        self.assertEqual(self.request('GET','/api/geography?access=cellular')[1]['seconds'],5)
        self.assertEqual(self.request('GET','/api/geography?access=unknown')[1]['seconds'],5)
        db=connect();ctx=Context(db,[1]);self.assertEqual(ctx.at(1,'2026-01-01 11:59:44.000000')['access'],'unknown');db.close()

    def test_android_pattern_and_malformed_data(self):
        ts='2026-01-01 12:00:05.000000'
        prefix='2026-01-01 12:00:05:456 I/ProcessCallLogger$Companion(1) : DeviceStatus: '
        result=observations(prefix+json.dumps({'connectionType':'Cellular'}),ts)
        self.assertEqual(result[0]['ts'],'2026-01-01 12:00:05.456000')
        self.assertEqual(result[0]['access'],'cellular')
        for data in ('{bad','[]','null','{"connectionType":12}'):
            self.assertEqual(observations(prefix+data,ts),[])
        self.assertEqual(observations('WiFi on Italo train hotspot',ts),[])
        self.assertEqual(observations(interface(5,'other'),ts)[0]['access'],'unknown')

    def test_sequences_gap_conflict_and_no_cross_import_join(self):
        f=sample();f['application.log']=location(1)+location(2)+location(2,46)+location(3)+location(40)
        self.upload(f)
        db=connect();self.assertEqual(db.execute('SELECT count(*) FROM movement_sequences').fetchone()[0],3)
        self.assertEqual(db.execute('SELECT count(*) FROM movement_samples').fetchone()[0],3)
        before=[r[0] for r in db.execute('SELECT id FROM movement_sequences')];pending(db)
        self.assertEqual(before,[r[0] for r in db.execute('SELECT id FROM movement_sequences')]);db.close()
        f['extra.txt']='another snapshot';self.upload(f)
        db=connect();self.assertEqual(db.execute('SELECT count(*) FROM movement_sequences').fetchone()[0],6);db.close()

    def test_duplicate_unknown_context_does_not_become_known(self):
        f=sample();f['application.log']=location(5);f['App.log']=interface(5,'cellular');self.upload(f)
        del f['App.log'];self.upload(f)
        self.assertEqual(self.request('GET','/api/geography')[1]['seconds'],10)
        self.assertEqual(self.request('GET','/api/geography?access=cellular')[1]['seconds'],0)
        self.assertEqual(self.request('GET','/api/geography?access=unknown')[1]['seconds'],10)

    def test_repeated_fix_and_monotonic_reset(self):
        f=sample();f['application.log']=location(1,elapsed=5)+location(2,elapsed=5)+location(3,elapsed=1)
        self.upload(f)
        db=connect()
        self.assertEqual(db.execute('SELECT count(*) FROM movement_samples').fetchone()[0],2)
        self.assertEqual(db.execute('SELECT count(*) FROM movement_sequences').fetchone()[0],2)
        self.assertTrue(db.execute("SELECT 1 FROM movement_sequences WHERE break_reason='monotonic_reset'").fetchone())
        db.close()

    def test_v7_backup_idempotence_and_annotation_preservation(self):
        self.upload()
        db=connect()
        with db:
            db.execute("INSERT INTO conversations(title,note) VALUES('test','keep')")
            for t in ('movement_samples','movement_sequences','network_observations'):db.execute('DROP TABLE '+t)
            db.execute("DELETE FROM meta WHERE key LIKE 'mobility-%'")
            db.execute("UPDATE meta SET value='6' WHERE key='schema_version'")
        init(db);init(db)
        self.assertEqual(db.execute('SELECT note FROM conversations').fetchone()[0],'keep')
        old=sqlite3.connect(str(Path(self.temp.name)/'kpe.sqlite3')+'.pre-v7.bak')
        self.assertEqual(old.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'6');old.close();db.close()

if __name__=='__main__':unittest.main()
