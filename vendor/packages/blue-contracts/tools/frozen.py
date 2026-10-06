"""A stable project ledger plus fail-closed publication history verification."""
from pathlib import Path
import os
import subprocess
from package_core import FROZEN_LEDGER, config, current_ledger, parse, require, safe_name, sha, source

def checked_git(root, *args):
    env = dict(os.environ, GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
    result = subprocess.run([os.environ.get('BLUE_GIT', 'git'), '-C', str(root), *args],
                            env=env, capture_output=True)
    require(result.returncode == 0, 'Git history check failed: ' + ' '.join(args[:2]))
    return result.stdout

def frozen_history(root):
    root = Path(root).resolve()
    config(root)  # Reject a changed ledger pointer even if current bytes happen to match.
    current = current_ledger(root)
    checked_git(root, 'rev-parse', '--verify', 'HEAD')
    shallow = Path(checked_git(root, 'rev-parse', '--git-path', 'shallow').decode().strip())
    if not shallow.is_absolute():
        shallow = root / shallow
    require(not shallow.exists() or not shallow.read_bytes().strip(), 'shallow Git history cannot verify frozen specifications; fetch full history')
    grafts = Path(checked_git(root, 'rev-parse', '--git-path', 'info/grafts').decode().strip())
    if not grafts.is_absolute():
        grafts = root / grafts
    require(not grafts.exists() or not grafts.read_bytes().strip(), 'grafted Git history is unsupported')
    # Traverses every parent; missing commit objects cause failure, not an empty history.
    ancestry = checked_git(root, 'rev-list', '--parents', 'HEAD').decode().splitlines()
    require(ancestry, 'empty/unavailable Git history')
    commitments = {}
    for row in ancestry:
        revision = row.split()[0]
        names = set(checked_git(root, 'ls-tree', '-r', '--name-only', revision).decode().splitlines())
        ledgers = {FROZEN_LEDGER} if FROZEN_LEDGER in names else set()
        selected = None
        if 'blue-package.yaml' in names:
            old_cfg = source(checked_git(root, 'show', revision + ':blue-package.yaml'))
            selected = old_cfg.get('specification')
            if old_cfg.get('protocol'):
                selected = {'path': old_cfg['protocol']['rules'], 'ledger': FROZEN_LEDGER}
            if selected:
                ledger = safe_name(selected.get('ledger', FROZEN_LEDGER))
                require(ledger in names, 'historical selected ledger unavailable at ' + revision)
                ledgers.add(ledger)
        historical = {}
        for path in sorted(ledgers):
            records = parse(checked_git(root, 'show', revision + ':' + path))
            require(isinstance(records, dict), 'invalid historical frozen ledger')
            for name, digest in records.items():
                safe_name(name)
                require(name not in commitments or commitments[name] == digest, 'conflicting historical frozen commitment: ' + name)
                require(current.get(name) == digest, 'frozen ledger changed or removed: ' + name)
                commitments[name] = digest
                historical[name] = digest
        if selected:
            name = safe_name(selected['path'])
            require(name in names and name in historical, 'historical normative commitment unavailable')
            require(sha(checked_git(root, 'show', revision + ':' + name)) == historical[name], 'historical frozen bytes were changed: ' + name)
    return {'scope': 'complete Git ancestry and stable project ledger', 'commits': len(ancestry), 'frozenPaths': sorted(commitments)}
