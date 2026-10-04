"""Read-only inventory: aggregate formats and evidence IDs, never raw log text."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.transients import signals


def inventory(db):
    counts=Counter();first={};episodes=Counter();missing=Counter()
    for row in db.execute("SELECT e.id,e.line_no,f.name,json_extract(s.profile,'$.platform') platform,e.text,e.kind FROM events e JOIN files f ON f.id=e.file_id LEFT JOIN source_profiles s ON s.import_id=e.import_id"):
        text=row['text'];head=text.split('\n',1)[0]
        # Only files supported by the operational extractor count as formats.
        filename=row['name']
        allowed=filename in ('PhoneEngine.log','ios_hwwrapper.log','application.log','application-1.log','App.log') or filename.startswith(('kpelog','VDlog','sip_debug'))
        if allowed:
            for kind,_,_,detail in signals(text if row['kind']=='sip' else head):
                key=(row['platform'],filename,kind,detail)
                counts[key]+=1;first.setdefault(key,(row['id'],row['line_no']))
        if '[NAWT' in head:
            for marker,phase in [('Buffer underrun occurred','start'),('Buffer underrun event terminated','end'),('Still in buffer underrun','ongoing')]:
                if marker in head:episodes[row['platform'],filename,phase]+=1
        low=text.lower()
        for marker in ('audiofocus','audio focus','avaudiosessioninterruption','interruption began','interruption ended'):
            if marker in low:missing[row['platform'],marker]+=1
    return dict(note='Raw occurrences, including repeated exports/rotations; not independent events or proof of complete coverage.',
        formats=[dict(platform=k[0],filename=k[1],type=k[2],format=k[3],occurrences=n,event_id=first[k][0],line_no=first[k][1]) for k,n in sorted(counts.items(),key=lambda kv:str(kv[0]))],
        nawt_episodes=[dict(platform=k[0],filename=k[1],phase=k[2],occurrences=n) for k,n in sorted(episodes.items(),key=lambda kv:str(kv[0]))],
        focus_interruption_candidates=[dict(platform=k[0],marker=k[1],occurrences=n) for k,n in missing.items()])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    args=parser.parse_args()
    db=sqlite3.connect(Path(args.database).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try:print(json.dumps(inventory(db),ensure_ascii=False,indent=2))
    finally:db.close()
