"""Apply a reviewed sibling package change set, guarding original bytes and keeping backups."""
from pathlib import Path
import argparse,hashlib,json,os,shutil
ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.work/shared-candidate';DEST=ROOT.parent/'blue-packages'
IGNORED={'.git','__pycache__','.DS_Store','.idea','build','verification','releases'}

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def staged():return {p.relative_to(STAGE).as_posix():p for p in STAGE.rglob('*') if p.is_file() and not any(x in IGNORED for x in p.relative_to(STAGE).parts) and p.suffix!='.pyc'}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    baseline=json.loads((ROOT/'.work/shared-candidate-baseline.json').read_text());files=staged()
    changes=[name for name,p in files.items() if baseline.get(name)!=digest(p)];removed=sorted(set(baseline)-set(files))
    for name in changes+removed:
        p=DEST/name;expected=baseline.get(name)
        if p.is_symlink():raise SystemExit('Refusing symlink '+name)
        if expected is None:
            if p.exists():raise SystemExit('New file already exists in destination: '+name)
        elif not p.is_file() or digest(p)!=expected:raise SystemExit('Concurrent change detected: '+name)
    for name in removed:
        if not name.startswith(('blue-coordination/','blue-coordination-temp/')) and '/dist/' not in name:
            raise SystemExit('Unexpected removal: '+name)
    temporary=DEST/'blue-coordination-temp'
    if temporary.exists():
        for path in temporary.rglob('*'):
            rel=path.relative_to(DEST)
            if path.is_file() and rel.as_posix() not in baseline and not any(x in IGNORED for x in rel.parts) and path.suffix!='.pyc':
                raise SystemExit('New temporary-package file requires review: '+str(rel))
    summary={'changedOrAdded':len(changes),'removed':len(removed),'paths':sorted(changes),'removedPaths':removed}
    (ROOT/'.work/promotion-review.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not args.apply:print(json.dumps({k:v for k,v in summary.items() if k in ('changedOrAdded','removed')},indent=2));return
    backup=ROOT/'.local/package-promotion-backup'
    if backup.exists():raise SystemExit('Backup already exists; inspect the previous promotion before retrying')
    backup.mkdir(parents=True)
    for name in changes+removed:
        p=DEST/name
        if p.exists():
            out=backup/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
    # Copy a recoverable complete temporary package before removing leftover generated files.
    temporary=DEST/'blue-coordination-temp'
    if temporary.exists():shutil.copytree(temporary,backup/'complete-blue-coordination-temp')
    for name in changes:
        out=DEST/name;out.parent.mkdir(parents=True,exist_ok=True);temp=out.with_name(out.name+'.timeline-promotion-tmp')
        shutil.copy2(files[name],temp);os.replace(temp,out)
    for name in removed:(DEST/name).unlink()
    if temporary.exists():shutil.rmtree(temporary)
    for name in changes:
        if digest(DEST/name)!=digest(files[name]):raise SystemExit('Copy verification failed: '+name)
    (ROOT/'.local/package-promotion.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'promoted':True,'changedOrAdded':len(changes),'removed':len(removed),'backup':str(backup)},indent=2))
if __name__=='__main__':main()
