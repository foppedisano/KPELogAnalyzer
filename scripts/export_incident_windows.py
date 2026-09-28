"""Export all paginated incident windows and evidence from the local analytics API."""
import argparse
import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8080')
    parser.add_argument('--call-id',required=True,help='Exact SIP Call-ID')
    parser.add_argument('--observer',default='AWT%',help='SQL LIKE pattern, default AWT%%')
    parser.add_argument('--window',type=float,default=1)
    parser.add_argument('--basis',choices=['reported_end','log_span'],default='reported_end')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    def query(definition):
        req=Request(args.url.rstrip('/')+'/api/analytics/query',data=json.dumps(definition).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=40) as response:return json.load(response)
    identity=query({'sql':'SELECT id FROM a_calls WHERE sip_call_id=:cid','parameters':{'cid':args.call_id}})
    if len(identity['rows'])!=1:raise ValueError('Call-ID inesistente o non univoco')
    cid=identity['rows'][0][0]
    definition=dict(datasets=['incidents'],scope={'call_ids':[cid]},incident_window_seconds=args.window,incident_time_basis=args.basis,limit=1000)
    def pages(sql,params):
        result=[];offset=0;responses=[]
        while True:
            r=query(dict(definition,sql=sql+' LIMIT 1001 OFFSET :page_offset',parameters=dict(params,page_offset=offset)))
            if responses and r['snapshot']!=responses[0]['snapshot']:raise ValueError('Database cambiato durante export: ripetere')
            responses.append({k:v for k,v in r.items() if k!='rows'})
            result.extend(dict(zip(r['columns'],row)) for row in r['rows'])
            if not r['truncated']:return result,responses
            offset+=len(r['rows'])
            if offset>100000:raise ValueError('Export troppo grande')
    windows,requests=pages('SELECT * FROM a_incident_windows WHERE observer LIKE :observer ORDER BY series_key,window_index',{'observer':args.observer})
    episodes,episode_requests=pages('SELECT * FROM a_incidents WHERE observer LIKE :observer ORDER BY id',{'observer':args.observer})
    evidence,evidence_requests=pages('SELECT e.* FROM a_incident_evidence e JOIN a_incidents i ON i.id=e.incident_id WHERE i.observer LIKE :observer ORDER BY e.incident_id,e.event_id',{'observer':args.observer})
    if any(r['snapshot']!=identity['snapshot'] for r in requests+episode_requests+evidence_requests):
        raise ValueError('Database cambiato durante export: ripetere')
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/'windows.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(windows[0]) if windows else ['series_key','window_index','percent']);writer.writeheader();writer.writerows(windows)
    (args.output/'analysis.json').write_text(json.dumps(dict(call_id=cid,sip_call_id=args.call_id,windows=windows,episodes=episodes,evidence=evidence,
        requests=requests+episode_requests+evidence_requests),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'call_id':cid,'windows':len(windows),'episodes':len(episodes),'evidence_rows':len(evidence),'output':str(args.output)}))


if __name__=='__main__':main()
