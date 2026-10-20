#!/usr/bin/env python3
"""Build and verify one pinned local Blue protocol package; never fetch or upgrade implicitly."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
import bootstrap
from package_core import build,read_package,wire,config,mount,PackageError
from package_v2 import requirements,lock_v2
ROOT=bootstrap.ROOT
REVISION='blue-contracts-2026-10-12-final-gas-1'
def package_path():return ROOT/'dist/package.bluepkg'
def checked_package(path=None):
 p=read_package(path or package_path());r=json.loads((ROOT/'release.json').read_text())
 if p.manifest['packageBlueId']!=r['packageBlueId']:raise RuntimeError('Package differs from release.json')
 if p.archive_sha!=r['archiveSha256']:raise RuntimeError('Archive differs from release.json')
 return p

def runtime_tree(output):
 """Separate derived reference: source bytes unchanged; one runtime rules resource is rebound."""
 output=Path(output)
 shutil.copytree(ROOT.parent/'verification/reference/blue-contracts/python/src',output,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 if config(ROOT)['name']=='blue-contracts':
  wb=output/'blue_workbench';wb.mkdir(exist_ok=True)
  for f in ('__init__.py','guide_extensions.py'):
   shutil.copyfile(ROOT.parent/'verification/reference/blue-contracts/python/apps/workbench'/f,wb/f)
  shutil.copyfile(ROOT/'SPECIFICATION.md',output/'blue_contracts/COMPLETE_SPECIFICATION.md')
  shutil.copytree(ROOT.parent/'verification/reference/blue-contracts/python/tools',output.parent/'tools',dirs_exist_ok=True)
 # Apply only the explicitly published source overrides after copying the frozen base.
 for layer in ('blue-bex', 'blue-contracts'):
  project=ROOT.parent/layer
  selection=json.loads((project/'docs/sources.json').read_text())
  for original,relative in {**selection.get('overrides',{}),**selection.get('resourceOverrides',{})}.items():
   if not original.startswith('src/'):raise ValueError('Invalid runtime override')
   destination=output/original[4:];destination.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(project/relative,destination)
 return output

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('command',choices=['build','verify','inspect','requirements','test','demo','reference-tests','runtime-copy'])
 parser.add_argument('path',nargs='?',type=Path)
 args=parser.parse_args()
 if args.command=='runtime-copy':
  if args.path is None:raise ValueError('runtime-copy requires a destination directory')
  if args.path.resolve().is_relative_to((ROOT.parent/'verification/reference/blue-contracts').resolve()):raise ValueError('Never overwrite the frozen reference')
  runtime_tree(args.path);print(args.path);return 0
 if args.command=='build':
  cfg=config(ROOT);s=ROOT/cfg['protocol']['rules']
  if (ROOT/'SPECIFICATION.md').read_bytes()!=s.read_bytes():raise RuntimeError('Root specification and identified specification differ')
  subprocess.run([sys.executable,str(ROOT.parent/'tools/build_final_gas.py'),'blue-contracts','--check'],check=True)
  checked_package();return 0
 if args.command in ['verify','inspect','requirements']:
  p=checked_package(args.path)
  result={'verified':True,'packageBlueId':p.manifest['packageBlueId'],'archiveSha256':p.archive_sha,'protocol':p.manifest['protocol'],'language':p.manifest['language'],'audit':p.audit}
  if args.command=='inspect':result['exports']=p.manifest['exports']
  if args.command=='requirements':result['requirements']=requirements(p)
  print(json.dumps(result,indent=2));return 0
 if args.command=='test':return subprocess.run([sys.executable,'-m','pytest','-q','tests'],cwd=ROOT).returncode
 if args.command=='demo':return subprocess.run([sys.executable,str(ROOT/'examples/run.py')],cwd=ROOT).returncode
 if args.command=='reference-tests':
  with tempfile.TemporaryDirectory(prefix='blue-reference-') as d:
   src=runtime_tree(Path(d)/'src');env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(src)+os.pathsep+str(src.parent),BLUE_BENCHMARK_ROOT=str(src.parent))
   name=config(ROOT)['name']
   group='bex' if name=='blue-bex' else 'contracts_event'
   return subprocess.run([sys.executable,str(ROOT/'tools/run_reference_tests.py'),str(ROOT.parent/'verification/reference/blue-contracts/python/tests'/group)],cwd=d,env=env).returncode
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:
  print(json.dumps({'status':'FAIL','error':str(e)}),file=sys.stderr);raise SystemExit(1)
