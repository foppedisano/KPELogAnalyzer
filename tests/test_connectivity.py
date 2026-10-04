"""Synthetic connectivity, ambiguous attempts, stale states and upgrade regression."""
import sqlite3
import unittest
from app.db import init
from app.connectivity import signals, timeline, enrich, attempts, reasons, for_calls
from app.parser import ingest
from tests.fixtures import archive, sample, message
from tests import test_periodic as fixture


def app_line(second, text):
    return f'2026-01-01 12:00:{second:02}.0000 [info] [1] : {text}\n'


class ConnectivityTests(unittest.TestCase):
    setUp = fixture.PeriodicTests.setUp
    tearDown = fixture.PeriodicTests.tearDown

    def load(self):
        f=sample()
        f['App.log']=app_line(3,'Calling number: synthetic-target')+app_line(3,'KPE is not ready yet... the call cannot be established')+app_line(4,'Calling number: second-target')+app_line(6,'KPE is not ready yet... the call cannot be established')+app_line(7,'Calling number: third-target')+app_line(7,'unrelated message')+app_line(7,'KPE is not ready yet... the call cannot be established')
        f['vdklog.txt']='[2026-01-01 12:00:01.000] [STUN] [INFO] SPM: Network UP for both pingers\n[2026-01-01 12:00:04.000] [STUN] [WARNING] SPM: Network DOWN for BOTH pingers\n[2026-01-01 12:00:08.000] [CORE] [INFO] Stopping STUN pinger...\n'
        f['ctilib.log']='[2026-01-01 12:00:05.000] [CTILIB] [INFO] login succeded!\n'
        f['sip_debug.txt']=message(0,'call-a')+message(6,'call-a',response=403,direction='INCOMING')+message(20,'call-a',method='BYE')
        ingest(self.db,archive(f),'synthetic-network.zip')

    def state_at(self,data,layer,t):
        ts=f'2026-01-01 12:00:{t:02}.000000'
        return next(s for s in data['lanes'][layer] if s['start']<=ts<s['end'])

    def test_attempt_pairing_malformed_and_idempotency(self):
        self.load();a=attempts(self.db)
        self.assertEqual(len(a),5)
        self.assertEqual(sum(bool(x['reason_event_id']) for x in a),3)
        self.assertTrue(next(x for x in a if x['target']=='synthetic-target')['reason_event_id'])
        self.assertIsNone(next(x for x in a if x['target']=='second-target')['reason_event_id'])
        self.assertIsNone(next(x for x in a if x['target']=='third-target')['reason_event_id'])
        before=self.db.execute('SELECT COUNT(*) FROM connectivity_events').fetchone()[0]
        enrich(self.db,1);init(self.db)
        self.assertEqual(len(attempts(self.db)),5)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM connectivity_events').fetchone()[0],before)

    def test_separate_layers_expiry_stop_and_conflict(self):
        self.load();d=timeline(self.db,1,'2026-01-01 12:00:00','2026-01-01 12:01:00')
        self.assertEqual(self.state_at(d,'network',0)['state'],'unknown')
        self.assertEqual(self.state_at(d,'network',1)['state'],'up')
        self.assertEqual(self.state_at(d,'network',4)['state'],'down')
        self.assertEqual(self.state_at(d,'network',5)['state'],'transient')
        self.assertEqual(self.state_at(d,'stun',8)['state'],'unknown')
        self.assertEqual(self.state_at(d,'sip',6)['state'],'up')
        self.assertEqual(self.state_at(d,'network',40)['state'],'unknown')
        for layer,segments in d['lanes'].items():
            self.assertEqual(segments[0]['start'],d['start']);self.assertEqual(segments[-1]['end'],d['end'])
            for a,b in zip(segments,segments[1:]):self.assertEqual(a['end'],b['start'])
            for s in segments:
                for e in s['evidence']:self.assertIn(e,d['evidence'])

    def test_exact_sip_reason_no_fuzzy_call_merge(self):
        self.load();calls=[dict(x) for x in self.db.execute('SELECT * FROM calls')];reasons(self.db,calls)
        self.assertIn('SIP 403',next(c for c in calls if c['sip_call_id']=='call-a')['reason'])
        self.assertEqual(len(for_calls(self.db,[calls[0]['id']])),1)
        self.assertTrue(all(x['id']<0 for x in attempts(self.db)))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM calls WHERE call_key LIKE 'attempt%'").fetchone()[0],0)

    def test_source_isolation_and_query_validation(self):
        self.load()
        self.db.execute("INSERT INTO imports(id,name,sha256,label) VALUES(99,'synthetic','other','other')")
        d=timeline(self.db,99,'2026-01-01 12:00:00','2026-01-01 12:01:00')
        self.assertEqual(d['lanes']['network'][0]['state'],'unknown')
        for a,b in [('2026-01-01','2026-01-03'),('2026-01-01','2026-01-01'),('2026-01-01T00:00:00+01:00','2026-01-01T01:00:00+01:00')]:
            with self.assertRaises(ValueError):timeline(self.db,1,a,b)

    def test_media_requires_positive_interval_not_cumulative_or_zero(self):
        self.load()
        e=self.db.execute("SELECT id,ts,call_id FROM events WHERE kind='rtcp' LIMIT 1").fetchone()
        if e is None:
            e=self.db.execute('SELECT id,ts,call_id FROM events ORDER BY id LIMIT 1').fetchone()
        for name,value in [('rtcp.packets_received_interval',2),('rtcp.packets_received',100)]:
            self.db.execute('''INSERT INTO metrics(event_id,call_id,ts,name,value,unit,direction,flow,valid)
                VALUES(?,?,?,?,?,'packets','incoming','0',1)''',(e['id'],e['call_id'],e['ts'],name,value))
        self.db.execute("DELETE FROM meta WHERE key='connectivity:1'")
        enrich(self.db,1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM connectivity_events WHERE layer='media'").fetchone()[0],1)
        self.db.execute("DELETE FROM connectivity_events WHERE layer='media'")
        self.db.execute("UPDATE metrics SET value=0 WHERE name='rtcp.packets_received_interval'")
        self.db.execute("DELETE FROM meta WHERE key='connectivity:1'")
        enrich(self.db,1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM connectivity_events WHERE layer='media'").fetchone()[0],0)

    def test_patterns_are_scoped_and_do_not_read_body_as_status(self):
        for txt,fn in [('Network UP for both pingers','App.log'),('Currently in write error event: no','VDlog.txt'),('Current network interface: wifi','untrusted.txt'),('Calling number:','App.log'),('INCOMING SIP message:\nSIP/2.0 broken\nCSeq: 1 INVITE','sip_debug.txt')]:
            self.assertEqual(list(signals(txt,fn)),[])
        self.assertEqual(list(signals('Current network interface: wifi','App.log'))[0][1],'available')
        self.assertEqual(list(signals('KPE change state from: disconnected to: connecting','PhoneEngine.log'))[0][1],'transient')
        self.assertEqual(list(signals('The remote host closed the connection','ctilib.log'))[0][0],'cti')
        self.assertEqual(list(signals('SSL_read error=5','resip.log'))[0][0],'sip')

    def test_upgrade_preserves_ids_and_has_backup(self):
        self.load();before=self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        with self.db:
            self.db.execute('DROP TABLE connectivity_events');self.db.execute('DROP TABLE user_attempts')
            self.db.execute("DELETE FROM meta WHERE key LIKE 'connectivity:%'")
            self.db.execute("UPDATE meta SET value='11' WHERE key='schema_version'")
        init(self.db)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],before)
        self.assertEqual(len(attempts(self.db)),5)
        backup=sqlite3.connect(str(self.path)+'.pre-v12.bak')
        self.assertEqual(backup.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],'11')
        backup.close()

    def test_exact_copies_only_same_resolved_producer(self):
        self.load()
        self.db.execute("UPDATE import_producers SET producer_key='synthetic-device',status='resolved',role='app' WHERE import_id=1")
        iid=self.db.execute("INSERT INTO imports(name,sha256,label) VALUES('copy','copy','copy')").lastrowid
        self.db.execute("INSERT INTO import_producers(import_id,producer_key,status,role,platform,basis,evidence,method) VALUES(?,'synthetic-device','resolved','app','ios','synthetic','[]','test')",(iid,))
        fid=self.db.execute("INSERT INTO files(import_id,name,size,parser) VALUES(?,'App.log',100,'generic')",(iid,)).lastrowid
        original=self.db.execute("SELECT e.* FROM events e JOIN user_attempts a ON a.event_id=e.id WHERE a.target='synthetic-target'").fetchone()
        for _ in range(2):
            eid=self.db.execute("INSERT INTO events(import_id,file_id,line_no,ts,kind,text) VALUES(?,?,1,?,'generic',?)",(iid,fid,original['ts'],original['text'])).lastrowid
            self.db.execute("INSERT INTO user_attempts VALUES(?,?,?,'synthetic-target','request',NULL)",(eid,iid,original['ts']))
        a=[x for x in attempts(self.db) if x['target']=='synthetic-target']
        self.assertEqual(len(a),2)  # Never collapse two occurrences in a single export.
        self.assertEqual(sorted(x['copies'] for x in a),[1,2])
        self.db.execute("UPDATE import_producers SET status='ambiguous' WHERE import_id=?",(iid,))
        self.assertEqual(len([x for x in attempts(self.db) if x['target']=='synthetic-target']),3)


if __name__=='__main__':unittest.main()
