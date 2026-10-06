"""Describe a benchmark source without requiring Git in an extracted archive."""
import json
from pathlib import Path
import subprocess


def git_metadata(root):
    root = Path(root).resolve()

    def git(*args):
        return subprocess.check_output(
            ['git', *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()

    try:
        if Path(git('rev-parse', '--show-toplevel')).resolve() == root:
            return {'kind': 'git-checkout', 'commit': git('rev-parse', 'HEAD'),
                    'dirtyPaths': git('status', '--porcelain').splitlines(),
                    'dirtyDiff': git('diff', 'HEAD'), 'archiveCommit': None}
    except (OSError, subprocess.CalledProcessError):
        pass
    # A manifest's commit is an origin hint, not a claim that edited archive
    # contents still equal that commit. Benchmarks independently hash sources.
    archive_commit = None
    try:
        manifest = json.loads((root / 'ARCHIVE_CONTENTS.json').read_text())
        if isinstance(manifest, dict) and isinstance(manifest.get('baseCommit'), str):
            archive_commit = manifest['baseCommit']
    except (OSError, ValueError):
        pass
    return {'kind': 'source-archive' if archive_commit else 'unversioned-source',
            'commit': None, 'dirtyPaths': None, 'dirtyDiff': None,
            'archiveCommit': archive_commit}
