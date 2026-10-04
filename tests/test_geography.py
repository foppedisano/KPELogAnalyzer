import sqlite3
import unittest
from pathlib import Path
from app.db import connect,init
from app.geography import extract, aggregate, pending, grid
from app.mos import score
from tests import test_server as fixture
from tests.fixtures import sample,rtcp,message


def fix(second, lat=45, lon=9, kind='New location received:', accuracy=12):
    return f'2026-01-01 12:00:{second:02}:250 I/PhoneService : {kind} Location[fused {lat},{lon} hAcc={accuracy} et=+1h2m3s]\n'


class GeographyTests(unittest.TestCase):
    setUp=fixture.APITests.setUp
    tearDown=fixture.APITests.tearDown
    upload=fixture.APITests.upload
    request=fixture.APITests.request

    def test_split_weighting_filter_and_evidence(self):
        f=sample();f['application.log']=fix(5)+fix(15,lon=9.02)
        f['rtplog.txt']=rtcp(6)+rtcp(12).replace('2%.','12%.')
        self.assertEqual(self.upload(f)[0],201)
        status,data=self.request('GET','/api/geography')
        self.assertEqual(status,200);self.assertEqual(len(data['cells']),2)
        self.assertAlmostEqual(data['seconds'],14)
        self.assertAlmostEqual(data['mean'],(score(2)*6+score(12)*8)/14)
        status,cut=self.request('GET','/api/geography?start=2026-01-01T12:00:14&end=2026-01-01T12:00:16')
        self.assertEqual(status,200);self.assertAlmostEqual(cut['seconds'],2)
        self.assertAlmostEqual(cut['mean'],score(12))
        self.assertNotIn('call_id',str(data));self.assertNotIn('event_id',str(data))
        db=connect()
        self.assertTrue(db.execute('SELECT count(*) FROM geo_mos_evidence').fetchone()[0])
        self.assertEqual(db.execute('SELECT ts FROM geo_positions ORDER BY ts LIMIT 1').fetchone()[0],'2026-01-01 12:00:05.250000')
        db.close()

    def test_cached_and_incoming_sip_never_localize(self):
        f=sample();f['application.log']=fix(5,kind='Last known location refreshed:')
        f['sip_debug.txt']+=message(5,direction='INCOMING').replace('Content-Length:', 'X-Location: geo:45,9;u=10\nContent-Length:')
        self.upload(f)
        for quality in ('fresh','declared'):
            data=self.request('GET','/api/geography?quality='+quality)[1]
            self.assertEqual(data['seconds'],0)
        db=connect();self.assertEqual(db.execute('SELECT count(*) FROM geo_positions').fetchone()[0],2);db.close()

    def test_declared_is_opt_in_and_body_excluded(self):
        f=sample();f['sip_debug.txt']+=message(5).replace('Content-Length:', 'X-Location: geo:45,9;u=10\nContent-Length:')
        self.upload(f)
        self.assertEqual(self.request('GET','/api/geography')[1]['seconds'],0)
        self.assertEqual(self.request('GET','/api/geography?quality=declared')[1]['seconds'],10)
        text=message(5)+'X-Location: geo:45,9\n'
        self.assertEqual(extract(text,'2026-01-01 12:00:05'),[])

    def test_duplicate_exports_and_pending_are_idempotent(self):
        f=sample();f['application.log']=fix(5)
        self.upload(f);before=self.request('GET','/api/geography')[1]
        f['extra.txt']='synthetic rotated export';self.upload(f)
        after=self.request('GET','/api/geography')[1]
        self.assertEqual(before['seconds'],after['seconds'])
        db=connect();count=db.execute('SELECT count(*) FROM geo_mos').fetchone()[0]
        pending(db);init(db)
        self.assertEqual(db.execute('SELECT count(*) FROM geo_mos').fetchone()[0],count)
        self.assertEqual(db.execute('SELECT count(*) FROM geo_mos_evidence').fetchone()[0],8)
        db.close()

    def test_conflict_invalid_and_no_future_position(self):
        f=sample();f['application.log']=fix(5)+fix(5,lon=10)+fix(25)
        self.upload(f)
        self.assertEqual(self.request('GET','/api/geography')[1]['seconds'],0)
        self.assertEqual(extract(fix(5,lat=999),'2026-01-01 12:00:05')[0]['valid'],0)
        self.assertEqual(extract(fix(5,accuracy=-1),'2026-01-01 12:00:05')[0]['valid'],0)
        self.assertEqual(extract('Location[fused broken','2026-01-01 12:00:05'),[])

    def test_age_expiry_and_missing_report_gap(self):
        f=sample();f['application.log']=fix(5)
        f['rtplog.txt']=rtcp(6)+rtcp(12).replace('2%.','-1%.')+rtcp(18)
        self.upload(f)
        data=self.request('GET','/api/geography')[1]
        self.assertEqual(data['seconds'],8)
        db=connect()
        with db:
            db.execute("UPDATE geo_positions SET ts='2026-01-01 11:00:00.000000'")
            db.execute('DELETE FROM geo_mos_evidence');db.execute('DELETE FROM geo_mos')
            db.execute("DELETE FROM meta WHERE key LIKE 'geo-mos-%'")
        # Pure association expiry using an older fix in a separate call archive.
        db.close()
        f=sample(cid='older');f['application.log']='2026-01-01 11:00:00:000 I/PhoneService : New location received: Location[fused 45,9 hAcc=12]\n'
        self.upload(f)
        self.assertEqual(self.request('GET','/api/geography')[1]['seconds'],0)

    def test_schema_six_backup_preserves_records(self):
        self.upload()
        db=connect();ids=db.execute('SELECT id FROM calls').fetchall()
        with db:
            for table in ('geo_mos_evidence','geo_mos','geo_positions'):db.execute('DROP TABLE '+table)
            db.execute("DELETE FROM meta WHERE key LIKE 'geo-mos-%'")
            from tests.fixtures import remove_periodic_schema
            remove_periodic_schema(db)
            db.execute("UPDATE meta SET value='5' WHERE key='schema_version'")
        init(db)
        self.assertEqual(db.execute('SELECT id FROM calls').fetchall(),ids)
        self.assertEqual(db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'12')
        with sqlite3.connect(str(Path(self.temp.name)/'kpe.sqlite3')+'.pre-v6.bak') as old:
            self.assertEqual(old.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'5')
        old.close()
        init(db);db.close()

    def test_cross_export_conflict_and_role_exclusion(self):
        f=sample();f['application.log']=fix(5)
        self.upload(f)
        f['application.log']=fix(5,lon=10)
        self.upload(f)
        data=self.request('GET','/api/geography')[1]
        self.assertEqual(data['seconds'],0)
        self.assertGreater(data['conflicting_intervals'],0)
        db=connect()
        with db:
            db.execute("INSERT INTO observation_roles(perspective_id,session,participant,role) VALUES(2,'test','receiver','xcoder')")
        db.close()
        self.assertEqual(self.request('GET','/api/geography')[1]['seconds'],10)

    def test_overlapping_intervals_union_and_period_boundary(self):
        f=sample();f['application.log']=fix(5)
        self.upload(f)
        db=connect()
        r=dict(db.execute("SELECT * FROM geo_mos WHERE quality='fresh' AND direction='downstream'").fetchone())
        with db:
            r.pop('id');r['start']='2026-01-01 12:00:12.000000'
            columns=','.join(r);marks=','.join('?' for _ in r)
            oid=db.execute(f'INSERT INTO geo_mos({columns}) VALUES({marks})',list(r.values())).lastrowid
            evidence=db.execute('SELECT metric_id,position_id FROM geo_mos_evidence LIMIT 1').fetchone()
            db.execute('INSERT INTO geo_mos_evidence VALUES(?,?,?)',(oid,*evidence))
        self.assertEqual(aggregate(db,{})['seconds'],10)
        self.assertEqual(aggregate(db,{'start':'2026-01-01T12:00:11','end':'2026-01-01T12:00:13'})['seconds'],2)
        db.close()

    def test_tile_cache_uses_identification_and_no_second_download(self):
        from app.map_tiles import tile
        from unittest.mock import patch,MagicMock
        response=MagicMock();response.read.return_value=b'\x89PNG\r\n\x1a\nsynthetic'
        response.headers={'ETag':'synthetic-etag'}
        response.__enter__.return_value=response
        with patch('app.map_tiles.urlopen',return_value=response) as request:
            self.assertEqual(tile(2,1,1,'http://127.0.0.1:8080/'),response.read.return_value)
            tile(2,1,1,'http://127.0.0.1:8080/')
            self.assertEqual(request.call_count,1)
            self.assertIn('KPELogAnalyzer',request.call_args.args[0].get_header('User-agent'))
            self.assertEqual(request.call_args.args[0].get_header('Referer'),'http://127.0.0.1:8080/')

    def test_filters_basemap_and_grid(self):
        self.assertEqual(self.request('GET','/basemap.json')[0],200)
        for query in ('cell=0','direction=bad','quality=all','start=2026-02-01&end=2026-01-01','start=bad'):
            self.assertEqual(self.request('GET','/api/geography?'+query)[0],400)
        key,bounds=grid(45,9,100)
        self.assertTrue(bounds[0]<=9<=bounds[2]);self.assertTrue(bounds[1]<=45<=bounds[3])
        self.assertEqual(self.request('GET','/api/map-tile?z=99&x=0&y=0')[0],400)

if __name__=='__main__':unittest.main()
