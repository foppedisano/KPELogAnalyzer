"""Automation-friendly entry point: python -m app.cli --help."""
import argparse
import json
from pathlib import Path

from .db import connect, init
from .parser import ingest
from .server import readonly_query


def main():
    parser=argparse.ArgumentParser(description='KPELogAnalyzer local import and read-only SQL')
    sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import',help='Import one or more ZIP exports')
    imp.add_argument('archives',nargs='+',type=Path)
    imp.add_argument('--label',default='')
    query=sub.add_parser('query',help='Run read-only SQL; JSON output')
    query.add_argument('sql')
    sub.add_parser('serve',help='Start the web service')
    args=parser.parse_args()
    if args.command=='serve':
        from .server import main as serve
        return serve()
    db=connect()
    try:
        init(db)
        if args.command=='import':
            for path in args.archives:
                result=ingest(db,path.read_bytes(),path.name,args.label)
                print(json.dumps(result,ensure_ascii=False))
        else:
            db.setlimit(__import__('sqlite3').SQLITE_LIMIT_LENGTH,4*1024*1024)
            print(json.dumps(readonly_query(db,args.sql),ensure_ascii=False))
    finally:
        db.close()


if __name__=='__main__':
    main()
