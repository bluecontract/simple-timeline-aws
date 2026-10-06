"""Run against the Contracts dependency's integrity-checked reference runtime."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_HOME = Path(os.environ.get('BLUE_PACKAGES_DIR', ROOT.parent)).resolve()
command = sys.argv[1] if len(sys.argv) > 1 else 'verify'
if command == 'test':
    args = ['-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_*.py','-v']
elif command == 'examples':
    args = [str(ROOT/'tools/examples.py')]
else:
    args = [str(ROOT/'tools/package.py'),command]
with tempfile.TemporaryDirectory(prefix='coordination-runtime-') as temp:
    runtime = Path(temp)/'src'
    # This official dependency tool verifies SOURCE-LOCK before copying, and
    # rebinds the one rules resource to its published Contracts specification.
    subprocess.run([sys.executable,'-B',str(PACKAGE_HOME/'blue-contracts/tools/release.py'),
                    'runtime-copy',str(runtime)],check=True,stdout=subprocess.DEVNULL)
    env = dict(os.environ, PYTHONPATH=str(runtime), BLUE_PACKAGES_DIR=str(PACKAGE_HOME), PYTHONDONTWRITEBYTECODE='1')
    raise SystemExit(subprocess.call([sys.executable,'-B',*args,*sys.argv[2:]],env=env,cwd=ROOT))
