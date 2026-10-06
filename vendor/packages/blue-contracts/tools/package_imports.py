"""Explicit local package imports, with generated pins and preserved specifications.

Archives are vendored build inputs. Registry acquisition remains the existing
explicit `pull` command; ordinary builds never resolve tags or use the network.
"""
from pathlib import Path
import re
from package_core import (Language, Repository, config, footer, parse, read_package,
                          read_source, require, safe_name, sha, wire)

LOCK = 'blue-package.lock.json'


def selected_imports(root, cfg):
    imports = cfg.get('imports', {})
    require(isinstance(imports, dict), 'imports must map local prefixes to package paths')
    result = {}
    for prefix, entry in sorted(imports.items()):
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', prefix), 'invalid import prefix')
        require(isinstance(entry, dict) and set(entry) == {'path'}, 'imports require an explicit archive path')
        name = safe_name(entry['path'])
        path = root / name
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                'missing or unsafe imported package: ' + name)
        result[prefix] = read_package(path)
    return result


def descriptor(package, path):
    m = package.manifest
    return {'path': path, 'name': m['name'], 'version': m['version'],
            'archiveSha256': package.archive_sha, 'repositoryIdentity': package.repository.identity,
            'source': m['source'], 'specification': m['specification'],
            'exports': m['exports'], 'importedDefinitions': m.get('importedDefinitions', [])}


def import_lock(root, cfg, packages):
    return {'format': 1, 'imports': {prefix: descriptor(p, cfg['imports'][prefix]['path'])
                                   for prefix, p in packages.items()}}


def lock_imports(root):
    root = Path(root).resolve()
    cfg = config(root)
    if cfg['format'] == 2:
        from package_v2 import lock_v2
        return lock_v2(root, cfg)
    value = import_lock(root, cfg, selected_imports(root, cfg))
    (root / LOCK).write_bytes(wire(value))
    return value


def load_imports(root, cfg):
    packages = selected_imports(root, cfg)
    if not packages:
        require(not (root / LOCK).exists() or parse(read_source(root, LOCK)) == {'format': 1, 'imports': {}},
                'stale imports lock; run lock-imports')
        return {}, {}, []
    actual = import_lock(root, cfg, packages)
    require(parse(read_source(root, LOCK)) == actual, 'import lock mismatch; review the archive and run lock-imports')
    dependencies = []
    for prefix, package in packages.items():
        aliases = {prefix + '/' + e['name']: e['blueId'] for e in package.manifest['exports']}
        dependencies.append(Repository.from_payload('import:' + prefix, aliases, package.repository.records))
    return packages, actual['imports'], dependencies


def associations(imports, reachable):
    """Select only associations belonging to the exact definition closure."""
    found = {}
    for prefix, info in sorted(imports.items()):
        origin = {k: info[k] for k in ('name', 'version', 'archiveSha256', 'repositoryIdentity', 'source')}
        entries = [{**e, 'origin': origin} for e in info['exports']] + info['importedDefinitions']
        for entry in entries:
            tid, spec = entry['blueId'], entry.get('specification')
            if tid not in reachable or not spec:
                continue
            selected = {'blueId': tid, 'name': entry['name'], 'origin': entry['origin'],
                        'specification': {**spec, 'path': 'spec/imported/' + spec['blueId'] + '.md'}}
            if tid in found:
                require(found[tid][0]['specification'] == selected['specification'],
                        'conflicting imported specification association: ' + tid)
            else:
                found[tid] = (selected, prefix, spec['path'])
    return [found[tid] for tid in sorted(found)]


def preserve_specifications(packages, imports, records):
    selected = associations(imports, records)
    files = {}
    for entry, prefix, original_path in selected:
        package = packages[prefix]
        spec = entry['specification']
        data = package.files[original_path]
        require(spec['path'] not in files or files[spec['path']] == data, 'conflicting specification bytes')
        files[spec['path']] = data
        language = Language(repositories=[package.repository])
        records.update(language.load(spec['blueId']).dependency_responses())
    return [entry for entry, _, _ in selected], files


def verify_imports(manifest, repo, files, language, expected_records):
    imports = manifest.get('imports', {})
    declared = manifest.get('importedDefinitions', [])
    require(imports == repo.metadata.get('imports', {}), 'import provenance mismatch')
    require(declared == repo.metadata.get('importedDefinitions', []), 'imported specification metadata mismatch')
    expected = [entry for entry, _, _ in associations(imports, expected_records)]
    require(declared == expected, 'missing or unrelated imported specification associations')
    for entry in declared:
        spec = entry['specification']
        require(spec['path'] in files and sha(files[spec['path']]) == spec['sha256'], 'imported specification bytes mismatch')
        admitted = language.create(wire({'type': 'Text', 'value': files[spec['path']].decode()}).decode())
        require(admitted.blue_id == spec['blueId'] and spec['blueId'] in repo.records, 'imported specification Text mismatch')
        exact = parse(language.verify(entry['blueId']))
        require(exact.get('description', '').endswith(footer(spec, spec.get('section', ''))),
                'imported definition specification binding mismatch')
        expected_records.update(language.load(spec['blueId']).dependency_responses())
