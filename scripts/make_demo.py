"""Generate two synthetic device exports sharing a SIP Call-ID."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.fixtures import archive,sample

target=Path(sys.argv[1]) if len(sys.argv)>1 else Path('data/demo')
target.mkdir(parents=True,exist_ok=True)
for name,direction in [('alice','OUTGOING'),('bob','INCOMING')]:
    (target/f'{name}.zip').write_bytes(archive(sample(direction=direction)))
print(f'Created {target / "alice.zip"} and {target / "bob.zip"}')
