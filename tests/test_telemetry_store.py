import copy
import json
import sqlite3
import struct
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.db import connect, init
from app.geography import aggregate
from app.mos import calculate, score
from app.parser import ingest
from app.telemetry import validate
from app.telemetry_store import pending, status
from tests.fixtures import archive


def events():
    example = Path(__file__).resolve().parents[1] / 'docs/examples/telemetry-v1.jsonl'
    templates = {e['type']:e for e in map(json.loads, example.read_text(encoding='utf-8').splitlines())}
    result = []
    def add(kind, ms, **payload):
        e = copy.deepcopy(templates[kind])
        e.update(schema='kpe.telemetry/1.1', event_id=f'evt-{len(result)}', seq=len(result), mono_ms=ms,
                 observed_utc=(datetime(2026,9,26,12)+timedelta(milliseconds=ms)).isoformat()+'Z')
        e['payload'].update(payload)
        if 'stream' in e['payload']:
            e['payload']['stream'].update(call_id='local-demo',sip_call_id='synthetic-call',stream_id='stream-demo')
        result.append(e)
        return e
    add('session',0, platform='android')
    add('media_config',0)
    add('network',0,serving_operator='001-01')
    add('position',0,fix_mono_ms=0,fix_id='fix-a',cached=False)
    add('media_interval',1000,start_mono_ms=0,end_mono_ms=1000,sequence_first=100,sequence_last=149,
        received_in_window_packets=45,semantics_id='rtp-sequence-window/1')
    add('position',1000,fix_mono_ms=1000,fix_id='fix-b',latitude=45.01,cached=False)
    add('media_interval',2000,start_mono_ms=1000,end_mono_ms=2000,sequence_first=150,sequence_last=199,
        received_in_window_packets=50,semantics_id='rtp-sequence-window/1')
    return result


class TelemetryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'test.sqlite3'
        self.db = connect(self.path)
        init(self.db)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def load(self, data, extra=''):
        for e in data:
            self.assertEqual(validate(e), [], e)
        return ingest(self.db, archive({'telemetry.jsonl':'\n'.join(map(json.dumps,data)), 'extra.txt':extra}), 'synthetic.zip')

    def test_intervals_map_network_provenance_and_call_summary(self):
        self.load(events())
        values = calculate(self.db,[1])
        self.assertEqual(len(values),2)
        self.assertEqual([m['loss_percent'] for m in values],[10,0])
        self.assertEqual(sum(m['interval_seconds'] for m in values),2)
        self.assertEqual(values[0]['value'],score(10))
        self.assertEqual(values[0]['clock_domain'],'UTC')
        self.assertGreater(values[1]['ts'],values[1]['start'])
        self.assertEqual(self.db.execute('SELECT end FROM calls').fetchone()[0],'2026-09-26 12:00:02.000000')
        self.assertTrue(values[0]['evidence'])
        mapped = aggregate(self.db,{'access':'cellular','operator':'001-01'})
        self.assertEqual(mapped['seconds'],2)
        self.assertEqual(len(mapped['cells']),2)
        self.assertEqual(aggregate(self.db,{'access':'wifi'})['seconds'],0)
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_cross_export_dedup_all_evidence_and_conflict_retracts(self):
        sample=events()
        self.load(sample)
        before=status(self.db)
        self.load(sample,'overlapping-export')
        after=status(self.db)
        self.assertEqual(after['records'],before['records'])
        self.assertEqual(after['intervals'],2)
        self.assertEqual(after['evidence'],2*before['evidence'])
        self.assertEqual(aggregate(self.db,{})['seconds'],2)
        # An altered config under the same stable event ID invalidates dependent intervals.
        conflict=copy.deepcopy(sample[1]);conflict['payload']['codec']='conflicting-codec'
        self.load([conflict],'conflict')
        self.assertEqual(status(self.db)['conflicts'],1)
        self.assertEqual(status(self.db)['intervals'],0)
        self.assertEqual(aggregate(self.db,{})['seconds'],0)
        pending(self.db)
        self.assertEqual(status(self.db)['intervals'],0)

    def test_positions_never_future_cached_or_cross_source(self):
        sample=events()
        # Both fixes arrive only at the right boundary of their corresponding intervals.
        sample[3]['payload']['cached']=True
        sample[5]['source_id']='other-source'
        self.load(sample)
        self.assertEqual(status(self.db)['intervals'],2)
        self.assertEqual(aggregate(self.db,{})['seconds'],0)

    def test_unknown_semantics_missing_config_clock_jump_and_overlap(self):
        for case in ('semantics','config','clock','overlap'):
            with self.subTest(case=case):
                sample=events()
                for e in sample:e['source_id']=case
                if case=='semantics':
                    for e in sample:
                        if e['type']=='media_interval':e['payload']['semantics_id']='vendor-unverified'
                if case=='config':sample=[e for e in sample if e['type']!='media_config']
                if case=='clock':sample[-1]['observed_utc']='2026-09-26T12:01:02Z'
                if case=='overlap':sample[-1]['payload']['start_mono_ms']=500
                self.load(sample,case)
                self.assertEqual(status(self.db)['intervals'],0)

    def test_rtcp_delta_both_directions_and_reset(self):
        def packet(high,lost):
            return (struct.pack('!BBHI',0x81,201,7,55)+struct.pack('!I',1)+b'\0'+lost.to_bytes(3,'big',signed=True)
                    +struct.pack('!IIII',high,0,0,0)).hex()
        for direction in ('sent','received'):
            sample=events()[:4]
            base=copy.deepcopy(sample[1])
            for i,(high,lost) in enumerate(((100,0),(200,5),(10,0))):
                e=copy.deepcopy(base)
                e.update(type='rtcp',event_id=f'rr-{i}',seq=i+4,mono_ms=i*1000,
                         observed_utc=f'2026-09-26T12:00:0{i}Z')
                stream=copy.deepcopy(base['payload']['stream'])
                stream['direction']='local_receive' if direction=='sent' else 'local_send'
                e['payload']=dict(stream=stream,transport_direction=direction,packet_hex=packet(high,lost))
                sample.append(e)
            for e in sample:e['source_id']=direction
            self.load(sample,direction)
        values=calculate(self.db,[1])
        self.assertEqual(len(values),2)
        self.assertEqual({v['direction'] for v in values},{'incoming','outgoing'})
        self.assertEqual({v['loss_percent'] for v in values},{5})
        self.assertTrue(any('rtcp_reset_gap_or_loss_ambiguous' in x['issues'] for x in status(self.db)['issues']))

    def test_offline_events_validation_and_unresolved_plan(self):
        base=events()[0]
        e=copy.deepcopy(base)
        e.update(type='plan_state',event_id='offline-state',seq=99,mono_ms=5000,observed_utc='2026-09-26T12:00:05Z')
        e['payload']=dict(plan=dict(plan_id='plan-a',revision=2),state='fallback',segment_id=None,profile_id='local',
                          reason='api_timeout',position_basis='unavailable',position_event_id=None,position_uncertainty_m=None)
        self.load([base,e])
        self.assertTrue(any('plan_reference_unresolved' in x['issues'] for x in status(self.db)['issues']))
        e['payload']['position_basis']='measured'
        self.assertTrue(validate(e))

    def test_offline_complete_example_and_expired_activation(self):
        path=Path(__file__).resolve().parents[1]/'docs/examples/telemetry-v1.1.jsonl'
        sample=list(map(json.loads,path.read_text(encoding='utf-8').splitlines()))
        self.load(sample)
        self.assertFalse(any('reference_unresolved' in x['issues'] for x in status(self.db)['issues']))
        e=copy.deepcopy(sample[-1]);e.update(event_id='expired',seq=100,mono_ms=301000,observed_utc='2026-09-26T12:05:01Z')
        e['payload']['state']='activated'
        self.load([e],'late')
        self.assertTrue(any('expired_plan_activation' in x['issues'] for x in status(self.db)['issues']))

    def test_collection_gap_stops_geo_and_sequence_reset_excludes(self):
        sample=events()
        sample[5]['type']='collection'
        sample[5]['payload']=dict(subsystem='position',status='suspended',reason='background')
        self.load(sample)
        self.assertEqual(aggregate(self.db,{})['seconds'],1)
        sample=events()
        for e in sample:e['source_id']='sequence-reset'
        sample[-1]['payload'].update(sequence_first=100,sequence_last=149)
        self.load(sample,'reset')
        self.assertEqual(status(self.db)['intervals'],2)  # only first source's two media windows remain
        self.assertTrue(any('sequence_window_reused' in x['issues'] for x in status(self.db)['issues']))

    def test_schema8_backup_preserves_ids_and_backfills_once(self):
        self.load(events())
        ids=self.db.execute('SELECT id FROM events').fetchall()
        with self.db:
            self.db.execute("INSERT INTO conversations(title,note) VALUES('synthetic','keep')")
            from tests.fixtures import remove_periodic_schema
            remove_periodic_schema(self.db)
            self.db.execute("UPDATE meta SET value='7' WHERE key='schema_version'")
        init(self.db)
        self.assertEqual(self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'11')
        self.assertEqual(self.db.execute('SELECT id FROM events').fetchall(),ids)
        self.assertEqual(self.db.execute('SELECT note FROM conversations').fetchone()[0],'keep')
        old=sqlite3.connect(str(self.path)+'.pre-v8.bak')
        self.assertEqual(old.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'7')
        old.close()
        init(self.db)
        self.assertEqual(status(self.db)['intervals'],2)


if __name__=='__main__':unittest.main()
