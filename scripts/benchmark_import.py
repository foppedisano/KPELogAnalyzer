"""Compare import cost with/without the source-time index on temporary synthetic data.

Run from the repository: python scripts/benchmark_import.py
Never opens the application database or imports into the running service.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile,time,sqlite3
from pathlib import Path
from app.db import connect,init
from app.parser import ingest
from tests.fixtures import archive,sample
with tempfile.TemporaryDirectory() as folder:
 base=connect(Path(folder)/'base.sqlite3');init(base)
 base.execute("INSERT INTO imports(id,name,sha256,label) VALUES(1,'synthetic','synthetic','synthetic')")
 base.execute("INSERT INTO files(id,import_id,name,size,parser) VALUES(1,1,'synthetic.log',0,'generic')")
 base.executemany("INSERT INTO events(import_id,file_id,line_no,ts,kind,text) VALUES(1,1,?,'2025-01-01 00:00:00','generic',?)",((i,'synthetic unrelated history '*20) for i in range(150000)))
 base.commit()
 payload=sample();payload['App.log']=''.join(f'2026-01-01 12:00:10.0000 [info] [1] : Synthetic context {i}\n' for i in range(10000))
 zipped=archive(payload)
 results=[]
 for indexed in (False,True):
  db=connect(Path(folder)/f'{indexed}.sqlite3');base.backup(db)
  if not indexed:db.execute('DROP INDEX event_import_time')
  t=time.perf_counter();result=ingest(db,zipped,'synthetic.zip');elapsed=time.perf_counter()-t
  print('indexed',indexed,'seconds',round(elapsed,3),'events',result['events'],'metrics',result['metrics'],flush=True)
  results.append(result)
  db.close()
 assert results[0]==results[1], 'Import results changed'
 base.close()
