"""Read and cross-check publication metadata without changing semantic resources."""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def constant(path, name):
    for statement in ast.parse(path.read_text()).body:
        if isinstance(statement, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name for target in statement.targets):
            return ast.literal_eval(statement.value)
    raise ValueError(f'Missing release constant {name} in {path}')


def current_release(root=ROOT):
    root = Path(root)
    language_path = root / 'specifications/language/TRACEABILITY.json'
    revision = json.loads(language_path.read_text())['revision']
    if revision != constant(root / 'tools/build_specification.py', 'REVISION'):
        raise ValueError('Language publication revision disagrees with its authoritative builder')
    paths = [language_path, root / 'tools/build_specification.py', root / 'tools/build_specs.py']
    for name in ('src/SPECIFICATION_1.0.md', 'specifications/language/COMPLETE_SPECIFICATION.md'):
        path = root / name
        match = re.search(r'^\*\*Status:\*\* implementation candidate, revision `([^`]+)`', path.read_text(), re.M)
        if not match or match[1] != revision:
            raise ValueError('Language publication revision mismatch: ' + name)
        paths.append(path)
    editions = {}
    for layer, key in (('bex', 'EDITION'), ('contracts', 'CONTRACTS_EDITION'), ('coordination', 'COORDINATION_EDITION')):
        path = root / 'specifications' / layer / 'RELEASE.json'
        edition = json.loads(path.read_text())['edition']
        if edition != constant(root / 'tools/build_specs.py', key):
            raise ValueError('Release edition disagrees with its authoritative builder: ' + layer)
        editions[layer] = edition
        paths.append(path)
    return {'packageRevision': revision, 'layerEditions': editions,
            'releaseMetadata': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


if __name__ == '__main__':
    print(json.dumps(current_release(), indent=2))
