"""Local HTTP smoke test. --demo explicitly imports deterministic synthetic ZIPs."""
import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8080')
    parser.add_argument('--demo',action='store_true',help='Import synthetic data into this instance')
    args=parser.parse_args()
    def request(path,body=None,headers=None):
        req=urllib.request.Request(args.url.rstrip('/')+'/api/'+path,data=body,headers=headers or {})
        with urllib.request.urlopen(req,timeout=10) as response:
            return json.load(response)
    for attempt in range(20):
        try:
            health=request('health')
            assert health['ok']
            break
        except (urllib.error.URLError,TimeoutError):
            if attempt==19: raise
            time.sleep(2)
    print('Health OK; parser',health['parser_version'])
    if not args.demo: return
    from tests.fixtures import sample
    from tests.test_enrichment import vd
    from tests.test_missing_packets import message
    for index,direction in enumerate(('OUTGOING','INCOMING')):
        files=sample(cid='kpeloganalyzer-smoke@example.test',direction=direction)
        files['VDlog.txt']=vd(5,100,10)+vd(10,100,30)+message(second=12)
        content=io.BytesIO()
        with zipfile.ZipFile(content,'w',zipfile.ZIP_DEFLATED) as z:
            for name,text in sorted(files.items()):
                z.writestr(zipfile.ZipInfo(name,(2026,1,1,0,0,0)),text)
        data=content.getvalue()
        headers={'Content-Type':'application/octet-stream','X-Filename':f'synthetic-smoke-{index}.zip'}
        result=request('imports',data,headers)
        assert request('imports',data,headers)['duplicate']
        perspectives=[p for p in request('perspectives') if p['import_id']==result['id']]
        assert len(perspectives)==1
        cid=perspectives[0]['call_id']
        delta=request(f'metrics?calls={cid}&name=derived.silence_delta')
        assert any(p['value']==20 for p in delta)
        missing=request(f'metrics?calls={cid}&name=vd.missing_packets')
        assert any(p['value']==4 for p in missing)
    print('Synthetic ZIP import, deduplication, delta and missing packets OK')


if __name__=='__main__':
    main()
