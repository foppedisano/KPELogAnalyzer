import json
import unittest
from app.ios_positions import extract,enrich,VERSION
from app.call_route import route
from app.geography import aggregate,pending
from tests import test_enrichment as fixture


def config(second=5,lat=45,core='KPECORE'):
    value=f'geo:{lat},9;u=5'
    body={'extraHeaders':[{'headerName':'X-Location','values':[
        {'msgType':method,'headerVal':value} for method in ('INVITE','200','BYE')]}]}
    return f'[2026-01-01 12:00:{second:02}.000] [{core}] [INFO] Adding extra headers to sip messages:  '+json.dumps(body)+'\n'


class ParserTests(unittest.TestCase):
    def test_headers_only_and_invalid(self):
        ts='2026-01-01 12:00:05'
        self.assertEqual(len(extract(config(),ts)),1)
        self.assertEqual(extract(config(lat=999),ts)[0]['valid'],0)
        for text in [config()[:-5],config().replace('"X-Location"','null'),
                     config().replace('"extraHeaders": [','"extraHeaders": null, "other": ['),
                     config().replace('Adding extra headers to sip messages:','INCOMING SIP message:'),
                     'untrusted body '+config(),config(lat='1e999')]:
            self.assertEqual(extract(text,ts),[])


class BackfillTests(unittest.TestCase):
    setUp=fixture.EnrichmentTests.setUp
    tearDown=fixture.EnrichmentTests.tearDown
    load=fixture.EnrichmentTests.load

    def test_import_dedup_repeated_positions_and_evidence(self):
        self.load({'vdklog.txt':config(core='CORE')+config(15,core='CORE'),
                   'kpelog-1.txt':config()+config().replace('.000]','.005]')+config(15)})
        positions=list(self.db.execute("SELECT * FROM geo_positions WHERE kind='sip_config'"))
        self.assertEqual(len(positions),2)
        self.assertTrue(all(p['event_id'] and p['source_line'] for p in positions))
        data=route(self.db,1)
        self.assertEqual(len(data['points']),2)
        self.assertEqual([p['value'] for p in data['points']],[100,100])
        self.assertEqual(aggregate(self.db,dict(metric='perceptual',quality='declared'))['samples'],2)
        self.assertEqual(aggregate(self.db,dict(metric='perceptual',quality='fresh'))['samples'],0)

    def test_historical_backfill_idempotent_preserves_existing_ids(self):
        self.load({'kpelog-1.txt':config()})
        self.db.execute("DELETE FROM geo_positions WHERE kind='sip_config'")
        self.db.execute('DELETE FROM meta WHERE key=?',(VERSION+':1',))
        calls=list(self.db.execute('SELECT * FROM calls'))
        events=list(self.db.execute('SELECT id FROM events'))
        # Legacy geography marker stays set: additive backfill must still run.
        pending(self.db)
        before=[tuple(r) for r in self.db.execute('SELECT * FROM geo_positions')]
        pending(self.db)
        self.assertEqual(len(before),1)
        self.assertEqual(before,[tuple(r) for r in self.db.execute('SELECT * FROM geo_positions')])
        self.assertEqual(calls,list(self.db.execute('SELECT * FROM calls')))
        self.assertEqual(events,list(self.db.execute('SELECT id FROM events')))

    def test_conflicts_and_overlapping_calls_remain_unassigned(self):
        self.load({'kpelog-1.txt':config()+config(lat=46)})
        self.assertEqual(len(route(self.db,1)['points']),2)
        self.assertTrue(all(p['value'] is None for p in route(self.db,1)['points']))
        self.db.execute("INSERT INTO calls(id,call_key,start,end) VALUES(99,'overlap','2026-01-01 12:00:00','2026-01-01 12:00:20')")
        self.db.execute("INSERT INTO perspectives(id,call_id,import_id,line_id,start,end) VALUES(99,99,1,1,'2026-01-01 12:00:00','2026-01-01 12:00:20')")
        self.assertEqual(route(self.db,1)['points'],[])
