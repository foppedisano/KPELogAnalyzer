"""Synthetic fixtures only. No personal log material belongs in this repository."""
import io
import json
import zipfile


def archive(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            # Stable fixture bytes: ZIP wall-clock timestamps otherwise make
            # duplicate-import tests depend on crossing a two-second boundary.
            z.writestr(zipfile.ZipInfo(name,date_time=(2020,1,1,0,0,0)),text,
                       compress_type=zipfile.ZIP_DEFLATED)
    return out.getvalue()


def kpe(second, text):
    return f'[2026-01-01 12:00:{second:02}.000] [KPECORE] [INFO] {text}\n'


def message(second, cid='call-a', method='INVITE', response=None, direction='OUTGOING'):
    first = f'SIP/2.0 {response} Result' if response else f'{method} sip:bob@example.test SIP/2.0'
    return f'''[2026-01-01 12:00:{second:02}.000] [SIPDEBUG] [INFO] {direction} SIP message:
Message:
{first}
From: <sip:alice@example.test>;tag=a
To: <sip:bob@example.test>;tag=b
Call-ID: {cid}
CSeq: 1 {method}
Content-Length: 0

'''


def summary(second=20, cid='call-a', line=0):
    return kpe(second, f'Info about call finished on line  {line} : '+json.dumps({'callInfo':{'call-id':cid,'caller':'alice@example.test','callee':'bob@example.test'}}))


def rtcp(second=10,line=0):
    return f'''[2026-01-01 12:00:{second:02}.000] [RTP SESSION FOR LINE {line} FLOW 0] [INFO]
<------------------------ RTCP ARRIVED ---------------------->
SSRC of this source: abcdef12
Packet we received from this source (total): 400
Packet loss we perceive from this source (since last report): 2%.
Jitter we perceive from this source (since last report): 3.5 ms.
RTT to this source: 42.25 ms.
Receiver Report - remote peer pkt loss (since last RR): 1%
Receiver Report - jitter perceived by this remote peer(since last report): -42000 ms.
'''


def sample(cid='call-a',direction='OUTGOING'):
    return {
        'sip_debug.txt': message(0,cid,direction=direction)+message(2,cid,response=200)+message(20,cid,method='BYE'),
        'kpelog.txt': kpe(0,'Call on lineId [ 0 ] with direction [ 2 ] added to the call list.')+kpe(2,'Call on lineId [ 0 ] found. Call status changed to 1')+summary(cid=cid),
        'rtplog.txt': rtcp(),
        'CallInfo.log': '2026-01-01 12:00:10.0000 [info] [1] : call flow metric line (0): '+json.dumps({'incoming':{'common':{'rtt':{'last':'42250','avg':'N/A','min':'NaN','max':'Infinity'}}}})+'\n',
    }


def remove_periodic_schema(db):
    """Only synthetic upgrade fixtures: restore the pre-11 table shape."""
    db.execute('DROP TABLE periodic_evidence')
    db.execute('DROP TABLE periodic_metadata')
    db.execute('DROP INDEX metric_event')
    db.execute('DROP INDEX metric_perspective')
    for column in ('observer','output_device','input_device','lifecycle'):
        db.execute('ALTER TABLE metrics DROP COLUMN '+column)
    db.execute("DELETE FROM meta WHERE key LIKE 'periodic-1:%'")
