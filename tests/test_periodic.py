"""Synthetic recent-format records; no corpus excerpts or personal evidence."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db import connect, init
from app.parser import ingest, metrics
from app.periodic import observations, enrich
from app.analytics import query, evidence, catalog
from tests.fixtures import archive, sample, remove_periodic_schema


def block(second=5, observer='AWT', value=10, extra='', device='NART0 of Line 0'):
    return f'''[2026-01-01 12:00:{second:02}.000] [{observer}] [INFO]
******** READING Virtual Output Device Running Info ********
Device name: Default Audio Output
Currently in total buffer underrun: no
******** CONNECTED INPUT DEVICE N.1 ********
Device name: {device}
Audio currently in buffer (ms): 20
silence msecs played out for buffer underruns occurred on this ring for this VOD: {value}
number of buffer underruns occurred on this ring for this VOD: 2
Currently in buffer underrun on this VOD: yes
Currently in underrun for this VOD  since 5 msecs.
{extra}
'''


class PeriodicTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'test.sqlite3'
        self.db=connect(self.path);init(self.db)

    def tearDown(self):
        self.db.close();self.temp.cleanup()

    def load(self,text,rtcp=None):
        files=sample();files['VDlog.txt']=text
        if rtcp is not None:files['rtplog.txt']=rtcp
        return ingest(self.db,archive(files),'synthetic.zip')

    def test_observers_inputs_duplicates_units_and_scope(self):
        extra='''Total bytes read from source: 200
Total bytes read from source: 200
ring current max buffer usecs (for dynamic dejittering): 20000
******** CONNECTED INPUT DEVICE N.2 ********
Device name: NART1 of Line 8
silence msecs played out for buffer underruns occurred on this ring for this VOD: 7
Device name: unrelated
Audio currently in buffer (ms): 99'''
        self.load(block(extra=extra)+block(observer='VD synthetic.wav',extra=extra))
        data=list(self.db.execute("SELECT * FROM metrics WHERE name='vd.silence_played'"))
        self.assertEqual(len(data),4)
        self.assertEqual({m['observer'] for m in data},{'AWT','VD synthetic.wav'})
        self.assertTrue(all(m['input_device']==m['device'] for m in data))
        self.assertEqual(sum(m['call_id'] is None for m in data),2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM metrics WHERE name='vd.bytes_read'").fetchone()[0],2)
        self.assertEqual(self.db.execute("SELECT value,raw_value,raw_unit FROM metrics WHERE name='vd.dejitter_target'").fetchone()[:],(20,20000,'us'))
        self.assertIsNone(self.db.execute("SELECT call_id FROM metrics WHERE value=99").fetchone()[0])

    def test_counters_resets_invalid_gaps_and_conflicts(self):
        self.load(block(1,value=10)+block(5,value=30)+block(7,value=2)+block(8,value=-1)+block(9,value=4)+block(10,value=5)+block(10,value=6)+block(11,value=7)+block(50,value=8))
        with self.db:
            self.db.execute("UPDATE metrics SET perspective_id=1,call_id=1 WHERE name='vd.silence_played'")
        result=query(self.db,dict(sql="SELECT status,delta FROM a_counter_intervals WHERE name=:n ORDER BY ts,id",parameters={'n':'vd.silence_played'}))
        self.assertEqual(result['rows'],[['initial',None],['ok',20],['reset',None],['invalid',None],['invalid',None],['conflict',None],['conflict',None],['conflict',None],['gap',None]])

    def test_lifecycle_and_overlapping_reused_lines(self):
        create='[2026-01-01 12:00:06.000] [VD] [INFO] Creating device NART0 of Line 0\n'
        self.load(block(5)+create+block(7,value=30))
        lives={r[0] for r in self.db.execute("SELECT lifecycle FROM metrics WHERE name='vd.silence_played'")}
        self.assertEqual(len(lives),2)
        with self.db:
            cid=self.db.execute("INSERT INTO calls(call_key) VALUES('overlap')").lastrowid
            self.db.execute("INSERT INTO perspectives(call_id,import_id,line_id,start,end) VALUES(?,1,0,'2026-01-01 12:00:00','2026-01-01 12:00:20')",(cid,))
            self.db.execute("DELETE FROM meta WHERE key='periodic-1:1'")
        # The ledger does not change IDs or silently reassociate old evidence.
        before=[tuple(r) for r in self.db.execute('SELECT id,event_id,call_id FROM metrics')]
        with self.db:enrich(self.db,1)
        self.assertEqual(before,[tuple(r) for r in self.db.execute('SELECT id,event_id,call_id FROM metrics')])

    def test_recent_states_counters_and_truncated_blocks(self):
        text=block(extra='''Number of device reset for scheduling delay: 1.  Accumulated delay is 30 ms.
Total media sent out : 250 ms.
Total media sent to middleware: 12
Current processing stage: INPUT_BEFORE_READ(16). Timestamp  01.01.2026 12:00:05.000
Last read processing stage known: END_NO_RTP_PCKT
RTP last pkt GOOD ROC: 3
RTP first BAD pkt SN: 8
Running cycles - Tbody Runs, Read, Decode, AdaptToMw, Append - : 7, 6, 5, 4, 3.
Number of Read Errors: NaN
Number of Write Errors: 1e309
audio samples skipped so far: 1.5
Device name: other
Current processing stage:''')
        data=list(observations(text,'vd'));by={m['name']:m for m in data}
        self.assertEqual(by['vd.scheduling_resets']['value'],1)
        self.assertEqual(by['vd.media_sent']['unit'],'ms')
        self.assertEqual(by['vd.media_middleware']['unit'],'raw')
        self.assertEqual(by['vd.cycles_append']['value'],3)
        self.assertEqual(by['vd.samples_skipped']['valid'],0)
        self.assertNotIn('vd.read_errors',by);self.assertNotIn('vd.write_errors',by)
        self.assertEqual(json.loads(by['vd.current_processing_stage']['value_json'])['code'],16)
        self.assertEqual(json.loads(by['vd.rtp_last_pkt_good_roc']['value_json']),3)

    def test_every_numeric_inventory_field_and_boolean_family(self):
        from app.periodic import FIELDS
        for label,key,unit,kind in FIELDS:
            with self.subTest(label=label):
                data=list(observations(block(extra=label+': 12'+(' ms.' if key.startswith('media_') else '')),'vd'))
                m=next(m for m in data if m['name']=='vd.'+key and m.get('raw_value')==12)
                self.assertEqual(m['sample_kind'],kind)
                self.assertEqual(m['unit'],'ms' if unit=='us' else unit)
        for state in ('partial buffer underrun','total buffer underrun','buffer underrun on this VOD',
                      'read error event','write error event','encoding error event','decoding error event'):
            data=list(observations(block(extra='Currently in '+state+': yes'),'vd'))
            self.assertTrue(any(m.get('value_json')=='true' and state.lower().replace(' ','_') in m['name'] for m in data))

    def test_heartbeat_monitor_and_non_nart(self):
        text='[2026-01-01 12:00:05.000] [NAWT0 of Line 0] [INFO] ---- VD 8 ( NAWT0 of Line 0 ) is alive and kicking --- written bytes 80 . Running cycles (last 1000 ms) - Tbody Runs, ReadFromMW, AdaptToCodec, Encode, Write - : 9, 8, 7, 6, 5.\n'
        data={m['name']:m for m in observations(text,'vd')}
        self.assertEqual(data['vd.heartbeat_bytes_written']['value'],80)
        self.assertEqual(data['vd.cycles_write']['sample_kind'],'reported statistic')
        self.assertEqual(data['vd.cycles_write']['direction'],'outgoing')
        monitor=list(observations('[2026-01-01 12:00:05.000] [VD Monitor Line 0] [INFO] NAWT status: END_OF_RUN_CYCLE(32). Timestamp 01.01.2026 12:00:05.000','vd'))[0]
        self.assertEqual((monitor['line_id'],monitor['flow']),(0,'?'))
        text=block().replace('Default Audio Output','NAWT0 of Line 0').replace('NART0 of Line 0','Default Audio Input')
        self.load(text)
        row=self.db.execute("SELECT * FROM metrics WHERE name='vd.silence_played'").fetchone()
        self.assertEqual((row['direction'],row['call_id']),('outgoing',1))

    def test_rtcp_scientific_both_directions_and_nonfinite(self):
        text='''[2026-01-01 12:00:10.000] [RTP SESSION FOR LINE 0 FLOW 2] [INFO]
RTCP ARRIVED
SSRC of this source: abc
RTCP Message n.: 2
Sender Report - ntp timestamp received from this source: Thu Jan 1 12:00:10 2026
Sender Report -  rtp timestamp corresponding to ntp time: 123
Packet loss we perceive from this source (since last report): 1.2e+9%
Receiver Report - remote peer pkt loss (since last RR): 2.5e-1%
Jitter we perceive from this source (since last report): -2e3 ms
RTT to this source: NaN ms
Packet we received from this source (total): 4e2
Sender Report - Number of packets sent by this remote peer (total): 5e2
Sender Report - Number of packets sent by this remote peer (since last report): 3e1
Packet we received from this source (since last report): 2e1
Receiver Report - pkt lost by this peer (total): -2
Receiver Report - pkt lost by this peer (since last report): 1.5
'''
        self.load('',text)
        data=list(self.db.execute("SELECT * FROM metrics WHERE name LIKE 'rtcp.%'"))
        self.assertEqual(len(data),9)
        self.assertEqual(sum(m['valid']==0 for m in data),4)
        self.assertTrue(all(m['ssrc']=='abc' and m['flow']=='2' for m in data))
        self.assertTrue(all(m['source_line'] for m in data))
        for bad in ('NaN','N/A','Infinity','1e309','1e','12oops'):
            self.assertEqual(list(metrics(dict(parser='rtcp',text='RTCP ARRIVED\nPacket we received from this source (total): '+bad))),[])

    def test_upgrade_backup_ids_annotations_and_replay(self):
        self.load(block())
        with self.db:
            remove_periodic_schema(self.db)
            self.db.execute("UPDATE meta SET value='10' WHERE key='schema_version'")
            self.db.execute("INSERT INTO conversations(title,note) VALUES('Synthetic','keep')")
        before=[tuple(r) for r in self.db.execute('SELECT id,event_id,name,value FROM metrics')]
        init(self.db)
        backup=sqlite3.connect(str(self.path)+'.pre-v11.bak')
        self.assertEqual(backup.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'10');backup.close()
        self.assertEqual(before,[tuple(r) for r in self.db.execute('SELECT id,event_id,name,value FROM metrics WHERE id<=?',(len(before),))])
        first=[tuple(r) for r in self.db.execute('SELECT * FROM metrics')]
        with self.db:self.db.execute("DELETE FROM meta WHERE key='periodic-1:1'")
        init(self.db);init(self.db)
        self.assertEqual(first,[tuple(r) for r in self.db.execute('SELECT * FROM metrics')])
        self.assertEqual(self.db.execute('SELECT note FROM conversations').fetchone()[0],'keep')

    def test_existing_backup_is_never_overwritten(self):
        self.load(block())
        with self.db:
            remove_periodic_schema(self.db)
            self.db.execute("UPDATE meta SET value='10' WHERE key='schema_version'")
        backup=Path(str(self.path)+'.pre-v11.bak');backup.write_bytes(b'reserved synthetic backup')
        with self.assertRaisesRegex(RuntimeError,'Backup already exists'):init(self.db)
        self.assertEqual(backup.read_bytes(),b'reserved synthetic backup')
        self.assertEqual(self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'10')

    def test_interrupted_backfill_rolls_back_and_resumes(self):
        from unittest.mock import patch
        self.load(block())
        with self.db:
            remove_periodic_schema(self.db)
            self.db.execute("UPDATE meta SET value='10' WHERE key='schema_version'")
        def interrupted(db,iid):
            enrich(db,iid)
            raise RuntimeError('synthetic interruption')
        with patch('app.periodic.enrich',side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError,'synthetic interruption'):init(self.db)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM periodic_metadata').fetchone()[0],0)
        self.assertIsNone(self.db.execute("SELECT value FROM meta WHERE key='periodic-1:1'").fetchone())
        init(self.db)
        self.assertGreater(self.db.execute('SELECT COUNT(*) FROM periodic_metadata').fetchone()[0],0)
        self.assertIsNotNone(self.db.execute("SELECT value FROM meta WHERE key='periodic-1:1'").fetchone())

    def test_api_metadata_authorizer_scope_and_evidence(self):
        self.load(block())
        result=query(self.db,dict(sql='SELECT name,value_json FROM a_periodic_metadata',limit=1))
        self.assertTrue(result['truncated'])
        eid=self.db.execute('SELECT event_id FROM periodic_metadata LIMIT 1').fetchone()[0]
        self.assertTrue(evidence(self.db,{'event_ids':[eid]})['events'][0]['periodic_metadata'])
        self.assertIn('a_counter_intervals',catalog(self.db)['tables'])
        for sql in ('SELECT * FROM periodic_metadata','DELETE FROM a_periodic_metadata','SELECT * FROM periodic_evidence'):
            with self.assertRaises((ValueError,sqlite3.DatabaseError)):query(self.db,dict(sql=sql))

    def test_counter_episode_comparison_keeps_separate_measures(self):
        self.load(block(5)+'''[2026-01-01 12:00:06.000] [AWT] [INFO] Buffer underrun occurred on input device NART0 of Line 0 .
[2026-01-01 12:00:07.000] [AWT] [INFO] Buffer underrun event terminated on input device NART0 of Line 0 . Event was 60 msecs long.
'''+block(10,value=70)+block(10,observer='VD other.wav',value=70))
        sql='SELECT observer,silence_delta_ms,incident_duration_ms FROM a_counter_incident_matches'
        self.assertEqual(query(self.db,dict(sql=sql))['rows'],[])
        self.assertEqual(query(self.db,dict(sql=sql,datasets=['incidents']))['rows'],[['AWT',60,60]])

    def test_manual_window_moves_metadata_and_unassigned_input(self):
        from app.manual import manual_window
        text=block().replace('Default Audio Output','NAWT0 of Line 0').replace('NART0 of Line 0','Default Audio Input')
        ingest(self.db,archive({'VDlog.txt':text}),'synthetic.zip')
        window=manual_window(self.db,dict(import_id=1,line_id=0,start='2026-01-01 12:00:00',end='2026-01-01 12:00:10'))
        pid=window['perspective_id']
        self.assertEqual(self.db.execute("SELECT perspective_id FROM metrics WHERE name='vd.silence_played'").fetchone()[0],pid)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM periodic_metadata WHERE perspective_id=?',(pid,)).fetchone()[0],2)
        manual_window(self.db,dict(perspective_id=pid,line_id=0,start='2026-01-01 12:00:06',end='2026-01-01 12:00:10'),edit=True)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM periodic_metadata WHERE perspective_id=?',(pid,)).fetchone()[0],0)
        self.assertIsNone(self.db.execute("SELECT perspective_id FROM metrics WHERE name='vd.silence_played'").fetchone()[0])


if __name__=='__main__':unittest.main()
