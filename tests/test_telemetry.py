"""Only synthetic telemetry. Exercise archival without changing legacy MOS."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.db import connect, init
from app.parser import ingest
from app.telemetry import decode, records, validate, schema
from tests.fixtures import archive, sample


EXAMPLE = Path(__file__).resolve().parents[1] / 'docs/examples/telemetry-v1.jsonl'


class TelemetryTests(unittest.TestCase):
    def examples(self):
        return [json.loads(line) for line in EXAMPLE.read_text(encoding='utf-8').splitlines()]

    def test_all_event_examples_and_schema(self):
        examples = self.examples()
        self.assertEqual(len(examples), len(schema('kpe.telemetry/1')['oneOf']))
        for event in examples:
            self.assertEqual(validate(event), [], event['type'])
            self.assertEqual(decode(json.dumps(event))[1], [])

    def test_invalid_numbers_types_ranges_and_time(self):
        position = next(e for e in self.examples() if e['type'] == 'position')
        for key, value in [('latitude', 91), ('longitude', True), ('speed_mps', -1),
                           ('fix_mono_ms', position['mono_ms'] + 1), ('accuracy_m', '10')]:
            event = copy.deepcopy(position)
            event['payload'][key] = value
            self.assertTrue(validate(event), key)
        for value in ['2026-09-26T12:00:00', '2026-02-30T12:00:00Z', '2026-09-26T12:00:00+02:00']:
            event = dict(position, observed_utc=value)
            self.assertTrue(validate(event))
        self.assertTrue(validate(dict(position, schema='kpe.telemetry/2')))
        self.assertTrue(validate(dict(position, validity='invalid')))
        self.assertFalse(validate(dict(position, validity='invalid', invalid_reason='sensor_unreliable')))
        interval = next(e for e in self.examples() if e['type'] == 'media_interval')
        interval['payload']['end_mono_ms'] = interval['payload']['start_mono_ms']
        self.assertTrue(validate(interval))

    def test_malformed_truncated_nonfinite_duplicates_and_bounds(self):
        for text in ['{', '[]', '{"schema":NaN}', '{"schema":1,"schema":2}',
                     '{"extensions":{"x":1e309}}', '[' * 1000 + ']' * 1000,
                     '{"x":"' + 'x' * 65536 + '"}']:
            self.assertTrue(decode(text)[1])
        event = self.examples()[0]
        event['extensions'] = {'vendor': {'nullable': None, 'value': 1}}
        self.assertFalse(decode(json.dumps(event))[1])

    def test_physical_lines_and_unknown_fields(self):
        event = self.examples()[0]
        text = '\r\n' + json.dumps(event) + '\r\r\n{\r\n'
        result = list(records(text))
        self.assertEqual([r[0] for r in result], [2, 3])
        self.assertEqual(result[0][1], event['observed_utc'])
        self.assertIsNone(result[1][1])
        event['typo'] = 1
        self.assertTrue(validate(event))

    def test_import_mixed_legacy_provenance_and_no_fuzzy_association(self):
        with tempfile.TemporaryDirectory() as folder:
            db = connect(Path(folder) / 'test.sqlite3')
            try:
                init(db)
                examples = self.examples()
                media = next(e for e in examples if e['type'] == 'media_interval')
                media['payload']['stream']['sip_call_id'] = 'call-a'
                files = sample()
                files['nested/telemetry-phoneengine.jsonl'] = '\n'.join(map(json.dumps, examples)) + '\n{'
                data = archive(files)
                result = ingest(db, data, 'synthetic.zip')
                self.assertEqual(result['calls'], 1)
                self.assertTrue(any('non conformi' in w for w in result['warnings']))
                rr = db.execute("SELECT e.*,f.name FROM events e JOIN files f ON f.id=e.file_id WHERE f.parser='telemetry' ORDER BY e.line_no").fetchall()
                self.assertEqual(len(rr), len(examples) + 1)
                self.assertEqual(rr[-1]['kind'], 'telemetry.invalid')
                self.assertEqual(rr[-1]['text'], '{')
                self.assertEqual([r['line_no'] for r in rr], list(range(1, len(rr)+1)))
                linked = [r for r in rr if r['call_id'] is not None]
                self.assertEqual(len(linked), 1)
                self.assertEqual(linked[0]['kind'], 'telemetry.media_interval.valid')
                self.assertEqual(db.execute("SELECT count(*) FROM metrics m JOIN events e ON e.id=m.event_id WHERE e.kind LIKE 'telemetry.%'").fetchone()[0], 0)
                self.assertTrue(ingest(db, data, 'again.zip')['duplicate'])
                # An overlapping export retains evidence, never creates calls by local IDs.
                second = ingest(db, archive({'telemetry.jsonl': json.dumps(media)}), 'overlap.zip')
                self.assertEqual(second['calls'], 0)
                self.assertEqual(db.execute('SELECT count(*) FROM calls').fetchone()[0], 1)
                self.assertIsNone(db.execute('SELECT call_id FROM events WHERE import_id=?', (second['id'],)).fetchone()[0])
            finally:
                db.close()

    def test_cli_does_not_open_database(self):
        with tempfile.TemporaryDirectory() as folder:
            command = [sys.executable, '-m', 'app.telemetry']
            # Child uses repository cwd for module lookup; data dir must stay absent.
            import os
            env = dict(os.environ, KPE_DATA_DIR=str(Path(folder) / 'must-not-exist'))
            good = subprocess.run(command + [str(EXAMPLE)], capture_output=True, env=env)
            self.assertEqual(good.returncode, 0, good.stderr)
            bad_file = Path(folder) / 'bad.jsonl'
            bad_file.write_text('{', encoding='utf-8')
            bad = subprocess.run(command + [str(bad_file)], capture_output=True, env=env)
            self.assertEqual(bad.returncode, 1)
            self.assertFalse((Path(folder) / 'must-not-exist').exists())


if __name__ == '__main__':
    unittest.main()
