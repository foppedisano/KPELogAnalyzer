import unittest
from tests import test_enrichment as fixture
from app.missing_packets import extract, enrich, VERSION
from app.diagnostics import diagnostics
from app.db import init


def message(count=4,current=105,line=0,second=5):
    return (f'[2026-01-01 12:00:{second:02}.000] [NART0 of Line {line}] [INFO] '
        f'Packet loss occurred. Current packet SN is {current} . Previous packet SN was 100 '
        f'SN delta is 5 ( {count} missing packets).\n')


class MissingPacketsTests(unittest.TestCase):
    setUp=fixture.EnrichmentTests.setUp
    tearDown=fixture.EnrichmentTests.tearDown
    load=fixture.EnrichmentTests.load

    def test_count_not_sequence_delta_and_malformed(self):
        self.assertEqual(list(extract(message()))[0]['value'],4)
        for text in [message().replace('4 missing','-4 missing'),message(0),message(999999),
                     message().replace('NART0','AWT'), 'Total missing packets: 100',message().split('SN delta')[0]]:
            self.assertEqual(list(extract(text)),[])

    def test_rotations_distinct_sequence_events_and_idempotency(self):
        self.load({'VDlog.txt':message()+message(current=106),'VDlog-old.txt':message()})
        data=list(self.db.execute("SELECT * FROM metrics WHERE name='vd.missing_packets'"))
        self.assertEqual(len(data),2)
        self.assertTrue(all(x['value']==4 and x['unit']=='packets' and x['sample_kind']=='event' for x in data))
        init(self.db);enrich(self.db,1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM metrics WHERE name='vd.missing_packets'").fetchone()[0],2)
        s=next(s for s in diagnostics(self.db,1)['series'] if s['name']=='vd.missing_packets')
        self.assertEqual(s['unit'],'packets');self.assertEqual(s['kind'],'event')
        self.assertEqual(len(s['points']),2)

    def test_backfill_and_unassigned_line(self):
        self.load({'VDlog.txt':message()+message(line=9)})
        before=self.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0]
        with self.db:
            self.db.execute('DELETE FROM metrics WHERE extractor=?',(VERSION,))
            self.db.execute('DELETE FROM meta WHERE key=?',(VERSION+':1',))
        init(self.db)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0],before)
        missing=list(self.db.execute("SELECT * FROM metrics WHERE name='vd.missing_packets' ORDER BY id"))
        self.assertIsNotNone(missing[0]['perspective_id'])
        self.assertIsNone(missing[1]['perspective_id'])
        self.assertTrue(all(m['source_line'] and m['event_id'] for m in missing))
