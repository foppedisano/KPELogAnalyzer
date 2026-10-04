"""Unit contracts and synthetic evidence; no private log excerpts."""
import csv
import io
import sqlite3
import unittest

from app.catalog import CATALOG, UNIT_LABELS, catalog
from app.db import connect
from app.periodic import FIELDS, observations
from tests import test_server as fixture
from tests.fixtures import sample
from tests.test_periodic import block


class UnitCatalogTests(unittest.TestCase):
    def test_every_catalog_entry_has_explicit_units_and_evidence(self):
        self.assertEqual(len({m['name'] for m in CATALOG}), len(CATALOG))
        for m in CATALOG:
            with self.subTest(metric=m['name']):
                self.assertTrue(m['source'])
                self.assertTrue(m['unit_note'])
                self.assertTrue(m['units'])
                self.assertIn(m['unit'], m['units'])
                for unit in m['units']:
                    self.assertIn(unit, UNIT_LABELS)
                    self.assertEqual(m['unit_labels'][unit], UNIT_LABELS[unit])
        self.assertEqual({m['name'] for m in CATALOG if m['units'] == ['raw']}, {
            'kpe.audio.dtmf_rtt', 'kpe.audio.jitter', 'kpe.audio.jitter_rfc3550',
            'kpe.audio.ploss_jitter', 'kpe.common.ploss', 'kpe.common.rtt'})

    def test_every_periodic_field_matches_catalog_and_normalization(self):
        by = {m['name']: m for m in CATALOG}
        for label, key, original_unit, _ in FIELDS:
            with self.subTest(metric=key):
                suffix = ' ms' if key.startswith('media_') else ''
                values = list(observations(block(extra=f'{label}: 12000{suffix}'), 'vd'))
                m = next(m for m in values if m['name'] == 'vd.' + key and m.get('raw_value') == 12000)
                expected = 'ms' if original_unit == 'us' else original_unit
                self.assertEqual(m['unit'], expected)
                self.assertIn(expected, by[m['name']]['units'])
                self.assertEqual(m['value'], 12 if original_unit == 'us' else 12000)
                if key.startswith('media_'):
                    raw = next(m for m in observations(block(extra=f'{label}: 12000'), 'vd') if m['name'] == 'vd.' + key)
                    self.assertEqual(raw['unit'], 'raw')
                    self.assertIn('raw', by[raw['name']]['units'])

    def test_catalog_preserves_all_observed_units_without_mutating_defaults(self):
        with sqlite3.connect(':memory:') as db:
            db.row_factory = sqlite3.Row
            db.execute('CREATE TABLE metrics(name TEXT,unit TEXT)')
            db.executemany('INSERT INTO metrics VALUES(?,?)', [
                ('vd.media_read', 'ms'), ('vd.media_read', 'raw'),
                ('kpe.unknown', 'raw'), ('kpe.unknown', 'unconfirmed'),
                ('vd.buffer', '')])
            by = {m['name']: m for m in catalog(db)}
            self.assertEqual(by['vd.media_read']['units'], ['ms', 'raw'])
            self.assertEqual(by['kpe.unknown']['units'], ['raw', 'unconfirmed'])
            self.assertIn('non documentata', by['kpe.unknown']['unit_labels']['unconfirmed'])
            self.assertIn('non dichiarata', by['vd.buffer']['unit_label'])
            self.assertEqual(next(m for m in CATALOG if m['name'] == 'vd.buffer')['units'], ['ms'])


class UnitAPITests(unittest.TestCase):
    setUp = fixture.APITests.setUp
    tearDown = fixture.APITests.tearDown
    request = fixture.APITests.request
    upload = fixture.APITests.upload

    def test_played_delta_milliseconds_menu_chart_diagnostic_and_csv(self):
        files = sample()
        files['VDlog.txt'] = block(5, value=100) + block(10, value=125)
        self.assertEqual(self.upload(files)[0], 201)
        options = self.request('GET', '/api/metric-options?calls=1')[1]
        option = next(m for m in options if m['name'] == 'derived.silence_played_delta')
        self.assertEqual(option['units'], ['ms'])
        self.assertIn('millisecondi', option['unit_label'])
        self.assertIn('msecs', option['unit_note'])
        data = self.request('GET', '/api/metrics?calls=1&name=derived.silence_played_delta')[1]
        self.assertEqual([(m['value'], m['unit']) for m in data], [(25, 'ms')])
        self.assertEqual(data[0]['interval_seconds'], 5)
        self.assertEqual(len(data[0]['evidence']), 2)
        diagnostic = self.request('GET', '/api/diagnostics?a=1')[1]
        series = next(s for s in diagnostic['series'] if s['name'] == option['name'])
        self.assertEqual(series['unit'], 'ms')
        self.assertEqual(series['points'][0]['value'], 25)
        exported = self.request('GET', '/api/metrics?calls=1&name=derived.silence_played_delta&format=csv')[1]
        row = next(csv.DictReader(io.StringIO(exported.decode('utf-8-sig'))))
        self.assertEqual((float(row['value']), row['unit']), (25, 'ms'))
        # An unconfirmed counter must never be relabelled as milliseconds.
        db = connect()
        with db:
            db.execute("UPDATE metrics SET unit='raw' WHERE name='vd.silence_played'")
        db.close()
        self.assertEqual(self.request('GET', '/api/metrics?calls=1&name=derived.silence_played_delta')[1], [])
        diagnostic = self.request('GET', '/api/diagnostics?a=1')[1]
        self.assertNotIn(option['name'], {s['name'] for s in diagnostic['series']})
