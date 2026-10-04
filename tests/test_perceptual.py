import unittest
from app.perceptual import windows, tick, calculate
from app.geography import aggregate
from tests.test_periodic import block
from tests import test_enrichment as fixture


def proof(i): return dict(event_id=i,filename='synthetic.txt',line=i)


def episode(a,b,ms=None,status='closed'):
    return dict(start=a,end=b if status=='closed' else None,last_observed=b,status=status,
                duration_basis='reported' if status=='closed' else 'minimum',duration_ms=ms if ms is not None else (b-a)*1000,evidence=[proof(1)])


def counter(t,value,life='one',valid=1):
    return dict(t=round(t*1000000),value=value,lifecycle=life,valid=valid,evidence=[proof(2)])


class WindowTests(unittest.TestCase):
    def test_600_ms_split_and_boundaries(self):
        out=windows([episode(.8,1.4,600)],[counter(0,0),counter(2,600)],0,2000000)
        self.assertEqual([m['value'] for m in out],[80,60])
        self.assertEqual([m['underrun_ms'] for m in out],[200,400])
        self.assertTrue(all(m['evidence'] for m in out))

    def test_union_not_sum_and_exact_second(self):
        out=windows([episode(0,1),episode(.5,1.5)],[counter(0,0),counter(2,1500)],0,2000000)
        self.assertEqual([m['value'] for m in out],[0,50])

    def test_counters_do_not_gate_baseline_and_open_remains_active(self):
        for counters in [[],[counter(0,0)],[counter(0,0),counter(31,0)],
                         [counter(0,10),counter(2,0)],[counter(0,0),counter(2,10)],
                         [counter(0,0),counter(2,0,'new')],[counter(0,0,valid=0),counter(2,0)]]:
            self.assertEqual([m['value'] for m in windows([],counters,0,2000000)],[100,100])
        self.assertEqual([m['value'] for m in windows([episode(.5,1,status='open')],[],0,2000000)],[50,0])

    def test_full_underrun_without_counters_but_no_invented_edges(self):
        out=windows([episode(.5,2.5)],[],0,3000000)
        self.assertEqual([m['value'] for m in out],[50,0,50])
        out=windows([],[counter(0,0),counter(3,0)],500000,2500000)
        self.assertEqual(len(out),3)
        self.assertEqual(out[0]['value'],100)
        self.assertEqual([m['observed_ms'] for m in out],[500,1000,500])

    def test_partial_second_normalized_to_active_call(self):
        out=windows([episode(.5,1.25)],[],500000,1250000)
        self.assertEqual([m['value'] for m in out],[0,0])
        self.assertEqual([m['underrun_ms'] for m in out],[500,250])
        self.assertEqual([m['observed_ms'] for m in out],[500,250])


class IntegrationTests(unittest.TestCase):
    setUp=fixture.EnrichmentTests.setUp
    tearDown=fixture.EnrichmentTests.tearDown
    load=fixture.EnrichmentTests.load

    def audio(self):
        def b(second,value):
            return block(second,value=value).replace('Currently in buffer underrun on this VOD: yes','Currently in buffer underrun on this VOD: no')
        return b(5,0)+'[2026-01-01 12:00:05.800] [AWT] Buffer underrun occurred while getting data from input device NART0 of Line 0 .\n'+'[2026-01-01 12:00:06.400] [AWT] Buffer underrun event terminated while getting data from input device NART0 of Line 0 . Event was 600 msecs long.\n'+b(7,600)+b(10,600)

    def test_metric_api_contract_and_point_map(self):
        self.load({'VDlog.txt':self.audio(),'PhoneEngine.log':'[2026-01-01 12:00:06.200] New location received: Location[gps 45.0,9.0 hAcc=5]\n'})
        out=calculate(self.db,[1]);self.assertEqual([m['value'] for m in out],[100,100,100,80,60]+[100]*13)
        self.assertTrue(all(m['evidence'] and m['unit']=='PQ' for m in out))
        data=aggregate(self.db,dict(metric='perceptual',cell='50'))
        self.assertEqual(data['samples'],1);self.assertEqual(data['cells'][0]['mean'],60)
        self.assertEqual(data['max_age_seconds'],0)
        self.assertTrue(data['cells'][0]['evidence'][0]['position_event_ids'])

    def test_no_position_hold_duplicate_fixes_and_filters(self):
        self.load({'VDlog.txt':self.audio(),'PhoneEngine.log':
                   '[2026-01-01 12:00:06.200] New location received: Location[gps 45.0,9.0 hAcc=5]\n'+
                   '[2026-01-01 12:00:06.500] New location received: Location[gps 45.0,9.0 hAcc=5]\n'+
                   '[2026-01-01 12:00:11.000] New location received: Location[gps 46.0,10.0 hAcc=5]\n'})
        data=aggregate(self.db,dict(metric='perceptual'))
        self.assertEqual(data['samples'],2);self.assertEqual(len(data['locations']),2)
        self.assertEqual(aggregate(self.db,dict(metric='perceptual',start='2026-01-01 12:00:06.1'))['samples'],1)
        with self.assertRaises(ValueError): aggregate(self.db,dict(metric='perceptual',direction='upstream'))

    def test_multiple_cells_same_second_ambiguous(self):
        self.load({'VDlog.txt':self.audio(),'PhoneEngine.log':
                   '[2026-01-01 12:00:06.200] New location received: Location[gps 45.0,9.0]\n'+
                   '[2026-01-01 12:00:06.500] New location received: Location[gps 46.0,10.0]\n'})
        data=aggregate(self.db,dict(metric='perceptual'))
        self.assertEqual(data['samples'],0);self.assertEqual(data['conflicting_intervals'],1)

    def test_wrong_observer_truncation_and_reused_line(self):
        self.load({'VDlog.txt':self.audio().replace('[AWT]','[NAWT0 of Line 0]')})
        self.assertEqual([m['value'] for m in calculate(self.db,[1])],[100]*18)

    def test_no_awt_no_line_still_has_quality_and_map(self):
        from tests.fixtures import sample,archive
        from app.parser import ingest
        files=sample()
        files={k:v for k,v in files.items() if k.startswith('sip')}
        files['PhoneEngine.log']='[2026-01-01 12:00:06.200] New location received: Location[gps 45.0,9.0]\n'
        ingest(self.db,archive(files),'synthetic-sip-only.zip')
        self.assertIsNone(self.db.execute('SELECT line_id FROM perspectives').fetchone()[0])
        result=calculate(self.db,[1])
        self.assertEqual([m['value'] for m in result],[100]*18)
        self.assertTrue(all(m['evidence'][0]['basis']=='call_lifecycle' for m in result))
        self.assertEqual(aggregate(self.db,dict(metric='perceptual'))['mean'],100)

    def test_unattributed_underrun_is_not_silently_healthy(self):
        self.load({'VDlog.txt':self.audio()})
        self.db.execute('UPDATE perspectives SET line_id=NULL')
        self.db.execute("UPDATE events SET call_id=NULL,perspective_id=NULL WHERE kind='vd'")
        result=calculate(self.db,[1])
        self.assertNotIn('2026-01-01 12:00:05.000000',[m['ts'] for m in result])
        self.assertTrue(all(m['value']==100 for m in result))

    def test_truncated_duration_does_not_fill_gap(self):
        self.load({'VDlog.txt':self.audio().replace('Event was 600 msecs long.','Event was malformed')})
        self.assertEqual([m['value'] for m in calculate(self.db,[1])],[100,100,100,80,60]+[100]*13)

    def test_overlapping_line_not_assigned_by_time(self):
        self.load({'VDlog.txt':self.audio()})
        self.db.execute("INSERT INTO calls(id,call_key,start,end) VALUES(99,'synthetic-overlap','2026-01-01 12:00:00','2026-01-01 12:00:20')")
        self.db.execute("INSERT INTO perspectives(id,call_id,import_id,line_id,start,end) VALUES(99,99,1,0,'2026-01-01 12:00:00','2026-01-01 12:00:20')")
        self.assertFalse(any(m['value']<100 for m in calculate(self.db,[1])))

    def test_android_milliseconds(self):
        import re
        text=re.sub(r'\[2026-01-01 12:00:(\d\d)\.(\d{3})\]',r'2026-01-01 12:00:\1:\2',self.audio())
        self.load({'VDlog.txt':text})
        self.assertEqual([m['value'] for m in calculate(self.db,[1])][3:5],[80,60])

    def test_missing_end_uses_last_call_evidence(self):
        self.load({'VDlog.txt':self.audio()})
        self.db.execute('UPDATE perspectives SET end=NULL')
        result=calculate(self.db,[1])
        self.assertTrue(result)
        self.assertEqual(result[-1]['valid_until'],'2026-01-01 12:00:20.000001')
        self.assertEqual(result[-1]['end_basis'],'last_call_evidence')
        self.assertEqual(result[-1]['value'],100)


class APITests(unittest.TestCase):
    from tests.test_server import APITests as Fixture
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    request=Fixture.request
    upload=Fixture.upload

    def test_map_dispatch_and_metric_csv(self):
        from tests.fixtures import sample
        files=sample();files['VDlog.txt']=IntegrationTests().audio()
        files['PhoneEngine.log']='[2026-01-01 12:00:06.200] New location received: Location[gps 45.0,9.0]\n'
        self.assertEqual(self.upload(files)[0],201)
        status,d=self.request('GET','/api/geography?metric=perceptual&cell=50')
        self.assertEqual(status,200);self.assertEqual(d['metric'],'perceptual');self.assertEqual(d['mean'],60)
        self.assertEqual(self.request('GET','/api/geography?metric=invalid')[0],400)
        status,d=self.request('GET','/api/metrics?calls=1&name=derived.perceptual_quality')
        self.assertEqual(status,200);self.assertEqual([m['value'] for m in d][3:5],[80,60])
        self.assertIn(b'underrun_percent',self.request('GET','/api/metrics?calls=1&name=derived.perceptual_quality&format=csv')[1])
