#!/usr/bin/env python3
"""Build this isolated candidate using the shared publisher and installed Blue library.

prepare is an explicit authoring operation: updates pins, frozen rules and source
specification references. Ordinary build/check refuse such changes.
"""
from pathlib import Path
import argparse
import atexit
import importlib.resources
import json
import os
import shutil
import sys
import tempfile
import types
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get('BLUE_PACKAGES_DIR', ROOT.parent)).resolve()
if not (HOME / 'blue-contracts/tools/package_core.py').is_file():
    raise SystemExit('Set BLUE_PACKAGES_DIR to the shared blue-packages checkout.')
sys.dont_write_bytecode = True
sys.path.insert(0, str(HOME / 'blue-contracts/tools'))
_temp = tempfile.TemporaryDirectory(prefix='coordination-publisher-')
atexit.register(_temp.cleanup)
standard = Path(_temp.name) / 'python/src/registry/standard'
standard.mkdir(parents=True)
for name in ('Package.json', 'ProtocolSpecification.json'):
    (standard / name).write_bytes((importlib.resources.files('registry') / 'standard' / name).read_bytes())
with zipfile.ZipFile(HOME / 'blue-contracts/dist/package.bluepkg') as z:
    legacy_toolchain = json.loads(z.read('package.json'))['toolchain']['blueArchiveSha256']
bootstrap = types.ModuleType('bootstrap')
bootstrap.WORKSPACE = Path(_temp.name)
bootstrap.ROOT = HOME / 'blue-contracts'
# Compatibility identifier required by the shared distribution adapter. Actual
# build implementation and source digest are separately recorded in provenance.
bootstrap.LOCK = {'blue': {'archiveSha256': legacy_toolchain}}
sys.modules['bootstrap'] = bootstrap
from package_core import build, wire, Language, Repository, sha, source, verify_bytes, read_package, require, current_ledger
from blue_language.physical import PhysicalCache


def config():
    return json.loads((ROOT / 'blue-package.yaml').read_text())


def dependencies(refresh=False):
    cfg = config()
    packages = {}
    for prefix, item in cfg['imports'].items():
        relative = Path(item['path'])
        require(relative.parts[0] == '..' and '..' not in relative.parts[1:], 'Unsafe import path')
        selected = (HOME / Path(*relative.parts[1:])).resolve()
        require(selected.is_relative_to(HOME), 'Import escapes shared package home')
        packages[prefix] = read_package(selected)
    pins = {'format': 2, 'imports': {prefix: {
        'path': cfg['imports'][prefix]['path'], 'packageBlueId': p.manifest['packageBlueId'],
        'archiveSha256': p.archive_sha, 'repositoryIdentity': p.repository.identity,
        'name': p.manifest['name'], 'version': p.manifest['version']
    } for prefix, p in packages.items()}}
    if not refresh:
        require(pins == json.loads((ROOT / 'blue-package.lock.json').read_text()), 'Dependency pins changed; explicit prepare required')
    return packages, pins


def context(validate=True):
    packages, _ = dependencies(refresh=not validate)
    language = Language(core_contracts=False)
    for prefix, package in packages.items():
        language.enable_repository(Repository.from_payload('import:' + prefix,
            {prefix + '/' + e['name']: e['blueId'] for e in package.manifest['exports']}, package.repository.records))
    rules = language.create(wire({'type': 'Text', 'value': (ROOT / 'spec/coordination.md').read_text()}).decode(), format='json')
    language.publish_document(rules)
    aliases = {}
    for entry in config()['exports']:
        raw = source((ROOT / entry['path']).read_bytes())
        require(raw.get('specification') == {'blueId': rules.blue_id}, 'Incorrect source specification: ' + entry['path'])
        document = language.admit_definition(wire(raw).decode(), format='json')
        language.publish_document(document)
        alias = 'Coordination/' + entry['name']
        language.aliases[alias] = document.blue_id
        aliases[alias] = document.blue_id
    return language, aliases, rules.blue_id


def prepare():
    packages, pins = dependencies(refresh=True)
    (ROOT / 'blue-package.lock.json').write_bytes(wire(pins))
    rules_text = (ROOT / 'spec/coordination.md').read_text()
    lang = Language(core_contracts=False)
    rules = lang.create(wire({'type': 'Text', 'value': rules_text}).decode(), format='json')
    (ROOT / 'spec/frozen.json').write_bytes(wire({'spec/coordination.md': sha(rules_text.encode())}))
    for entry in config()['exports']:
        path = ROOT / entry['path']
        raw = source(path.read_bytes())
        raw['specification'] = {'blueId': rules.blue_id}
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
    _, aliases, _ = context()
    print('Prepared', len(aliases), 'types; rules', rules.blue_id)


def compile_package():
    cfg = config()
    packages, pins = dependencies()
    current_ledger(ROOT)
    language, aliases, rules = context()
    with tempfile.TemporaryDirectory(prefix='coordination-build-') as temp:
        stage = Path(temp).resolve()
        names = {cfg['readme'], cfg['protocol']['rules'], 'spec/frozen.json', *cfg['files']}
        for name in names:
            path = stage / name
            require(path.resolve().is_relative_to(stage), 'Unsafe source path')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        (stage / 'inputs').mkdir()
        stage_pins = json.loads(json.dumps(pins))
        for prefix, p in packages.items():
            relative = 'inputs/' + prefix + '.bluepkg'
            (stage / relative).write_bytes(p.archive)
            cfg['imports'][prefix]['path'] = relative
            stage_pins['imports'][prefix]['path'] = relative
        repository = Repository.from_payload(cfg['name'], aliases, language.provider.snapshot())
        data = (repository._json + '\n').encode()
        relative = 'inputs/authored.repository.json'
        (stage / relative).write_bytes(data)
        cfg['inputs'] = [{'path': relative, 'sha256': sha(data), 'identity': repository.identity}]
        cfg['exports'] = [{'name': e['name'], 'fromInput': relative, 'inputAlias': 'Coordination/' + e['name']} for e in cfg['exports']]
        (stage / 'blue-package.yaml').write_bytes(wire(cfg))
        (stage / 'blue-package.lock.json').write_bytes(wire(stage_pins))
        package = build(stage, revision='coordination-inputs-0.2.0-rc.2-20261006', source_url='')
        verify_bytes(package.archive)
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'build', 'check', 'verify', 'inspect'])
    args = parser.parse_args()
    with PhysicalCache(65536).scope():
        if args.command == 'prepare':
            prepare()
            return
        if args.command in ('inspect', 'verify'):
            p = read_package(ROOT / 'dist/package.bluepkg')
        else:
            p = compile_package()
            expected = {**p.files, 'package.bluepkg': p.archive}
            if args.command == 'build':
                out = ROOT / 'dist'
                out.mkdir(exist_ok=True)
                for obsolete in sorted(out.rglob('*'), reverse=True):
                    if obsolete.is_file() and obsolete.relative_to(out).as_posix() not in expected:
                        obsolete.unlink()
                    elif obsolete.is_dir() and not any(obsolete.iterdir()):
                        obsolete.rmdir()
                for name, data in expected.items():
                    path = out / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            else:
                actual = {x.relative_to(ROOT / 'dist').as_posix(): x.read_bytes() for x in (ROOT / 'dist').rglob('*') if x.is_file()}
                require(actual == expected, 'Source-to-distribution mismatch')
        print(json.dumps({'verified': True, 'name': p.manifest['name'], 'version': p.manifest['version'],
            'packageBlueId': p.manifest['packageBlueId'], 'archiveSha256': p.archive_sha,
            'exports': len(p.manifest['exports'])}, indent=2))

if __name__ == '__main__':
    main()
