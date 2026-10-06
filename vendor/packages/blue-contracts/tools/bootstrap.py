"""Select and integrity-check the included reference; no installation or network access."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent/'verification/reference/blue-contracts'
if sys.version_info<(3,13):raise RuntimeError('Python 3.13 or newer is required')
SOURCE_LOCK=json.loads((WORKSPACE/'SOURCE-LOCK.json').read_text())
LOCK={'blue':{'archiveSha256':SOURCE_LOCK['sourceArchiveSha256'],'files':SOURCE_LOCK['files']}}
for name,digest in SOURCE_LOCK['files'].items():
 p=WORKSPACE/'python'/name
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
  raise RuntimeError('Pinned reference mismatch: '+name)
sys.dont_write_bytecode=True
sys.path.insert(0,str(WORKSPACE/'python/src'))
