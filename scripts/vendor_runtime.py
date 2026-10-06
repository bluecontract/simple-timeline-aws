"""Vendor the selected packages and their integrity-checked Contracts reference."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
PACKAGE_HOME=Path(os.environ.get('TIMELINE_PACKAGE_HOME',ROOT.parent/'blue-packages')).resolve()
RUNTIME_SOURCE=Path(os.environ.get('TIMELINE_REFERENCE_HOME',ROOT.parent/'blue-packages')).resolve()
out=ROOT/'vendor';out.mkdir(exist_ok=True)
runtime=out/'runtime'
if runtime.exists():shutil.rmtree(runtime)
subprocess.run([sys.executable,'-B',str(RUNTIME_SOURCE/'blue-contracts/tools/release.py'),'runtime-copy',str(runtime)],check=True)
for name in ['blue-language','blue-contracts','blue-coordination']:
 target=out/'packages'/name
 if target.exists():shutil.rmtree(target)
 target.mkdir(parents=True)
 paths=['dist/package.bluepkg']
 if name=='blue-contracts':paths+=['tools']
 if name=='blue-coordination':paths+=['types','spec','tools','blue-package.yaml','blue-package.lock.json']
 for relative in paths:
  src=PACKAGE_HOME/name/relative;dst=target/relative;dst.parent.mkdir(parents=True,exist_ok=True)
  if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  else:shutil.copy2(src,dst)
manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Vendored',len(manifest),'verified runtime/package files')
