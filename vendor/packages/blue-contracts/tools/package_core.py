"""Draft distribution envelope; all Blue semantics stay in the pinned implementation."""
from __future__ import annotations
import bootstrap
from blue_language import Language, MemoryProvider
from blue_repository import Repository as _Repository

class Repository(_Repository):
    """Package verification selects only Language core, not a default Contracts release.

    The inherited audit uses the unchanged strict Language algorithm. This
    merely prevents implicit authoring aliases from blocking another exact
    Contracts edition before its definitions can be verified.
    """
    def language(self, *, provider=None, **kwargs):
        kwargs.setdefault('core_contracts', False)
        return super().language(provider=provider, **kwargs)

from vendor import yaml
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import unicodedata
from urllib.parse import urlsplit, urlunsplit
import zipfile

FORMAT = 'blue-package/0.1-draft'
ARTIFACT_TYPE = 'application/vnd.blue.package.v1'
FILE_TYPE = 'application/vnd.blue.package.v1+zip'
MAX_BYTES = int(os.environ.get('BLUE_PACKAGE_MAX_BYTES', 64 * 1024 * 1024))
MAX_FILES = int(os.environ.get('BLUE_PACKAGE_MAX_FILES', 4096))

class PackageError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise PackageError(message)

def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()

def wire(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')

def pairs(items):
    out = {}
    for k, v in items:
        require(k not in out, 'duplicate JSON key: ' + k)
        out[k] = v
    return out

def parse(data):
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda v: (_ for _ in ()).throw(PackageError('non-finite JSON')))

class UniqueLoader(yaml.SafeLoader):
    pass

def unique_mapping(loader, node):
    out = {}
    for key_node, value_node in node.value:
        k = loader.construct_object(key_node, deep=True)
        require(isinstance(k, str) and k not in out, 'duplicate/non-string YAML key')
        out[k] = loader.construct_object(value_node, deep=True)
    return out
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

def source(data):
    return yaml.load(data.decode('utf-8'), Loader=UniqueLoader)

def safe_name(name):
    require(isinstance(name, str) and name and '\\' not in name and '\x00' not in name, 'unsafe path')
    path = PurePosixPath(name)
    require(not path.is_absolute() and all(p not in ('', '.', '..') for p in name.split('/')), 'unsafe path: ' + name)
    require(':' not in name and unicodedata.normalize('NFC', name) == name, 'ambiguous path: ' + name)
    return name

def allowed_file(name):
    safe_name(name)
    require(name in ('package.json', 'package.blue.json', 'package-records.json', 'repository.json', 'README.md', 'THIRD-PARTY-NOTICES.md') or
            (name.split('/')[0] in ('docs', 'spec', 'examples', 'conformance') and
             PurePosixPath(name).suffix in ('.md', '.blue', '.json')), 'unexpected payload: ' + name)

def read_source(root, name):
    safe_name(name)
    path = root / name
    require(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(), 'source path escape')
    require(path.is_file(), 'missing configured source: ' + name)
    data = path.read_bytes()
    data.decode('utf-8')
    require(not data.startswith(b'\xef\xbb\xbf') and b'\r' not in data, 'UTF-8 without BOM and LF required: ' + name)
    return data

def version(value):
    require(bool(re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?', value)), 'expected release version X.Y.Z or X.Y.Z-prerelease')
    if '-' in value:
        require(all(not x.isdigit() or x == '0' or not x.startswith('0') for x in value.split('-', 1)[1].split('.')), 'numeric prerelease identifiers cannot have leading zeros')
    return value

def config(root):
    out = source(read_source(root, 'blue-package.yaml'))
    require(out.get('format') in (1, 2), 'unsupported source configuration')
    require(isinstance(out.get('exports'), list), 'exports must be a list')
    require(bool(out['exports']) or (out.get('format') == 2 and isinstance(out.get('protocol'), dict)),
            'an empty export list is allowed only for an explicit protocol package')
    require(isinstance(out.get('namespace'), str) and out['namespace'] and '/' not in out['namespace'], 'invalid namespace')
    if out.get('specification'):
        require(out['specification'].get('ledger', 'spec/frozen.json') == 'spec/frozen.json', 'specification ledger is fixed at spec/frozen.json')
    return out

def git(root, *args):
    r = subprocess.run([os.environ.get('BLUE_GIT', 'git'), '-C', str(root), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

FROZEN_LEDGER = 'spec/frozen.json'

def current_ledger(root):
    path = root / FROZEN_LEDGER
    if not path.exists():
        return {}
    ledger = parse(read_source(root, FROZEN_LEDGER))
    require(isinstance(ledger, dict), 'frozen ledger must be an object')
    for name, digest in ledger.items():
        safe_name(name)
        require(name.startswith('spec/') and name.endswith('.md'), 'invalid frozen normative path')
        require(isinstance(digest, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', digest), 'invalid frozen digest')
        require(sha(read_source(root, name)) == digest, 'frozen specification mismatch: ' + name)
    return ledger

def spec_info(root, cfg):
    ledger = current_ledger(root)  # All commitments, even while the selected spec is disabled.
    selected = cfg.get('specification')
    if selected is None:
        return None, None
    name = safe_name(selected['path'])
    require(name.startswith('spec/') and name.endswith('.md'), 'normative input must be a source spec/*.md, never generated output')
    data = read_source(root, name)
    require(not any(x in data for x in (b'{{EXPORT_', b'{{PACKAGE_', b'{{OCI_', b'GENERATED_EXPORT_IDS')), 'circular generated normative input')
    require(ledger.get(name) == sha(data), 'frozen specification mismatch; select and lock a new specification path')
    l = Language()
    doc = l.create(json.dumps({'type': 'Text', 'value': data.decode('utf-8')}))
    return {'path': name, 'blueId': doc.blue_id, 'sha256': sha(data)}, doc

def footer(spec, section):
    return '\n\nNormative specification: blueId:' + spec['blueId'] + '\nSpecification bytes: ' + spec['sha256'] + ('\nSection: ' + section if section else '')

@dataclass
class Package:
    manifest: dict
    repository: Repository
    files: dict[str, bytes]
    archive: bytes
    audit: dict

    @property
    def archive_sha(self):
        return sha(self.archive)

def build(root, output=None, release_version=None, revision=None, source_url=None):
    root = Path(root).resolve()
    cfg = config(root)
    if cfg['format'] == 2:
        from package_v2 import build_v2
        return build_v2(root, output, release_version, revision, source_url)
    ver = version(release_version or cfg['version'])
    rev = revision or git(root, 'rev-parse', 'HEAD') or 'uncommitted'
    url = (git(root, 'remote', 'get-url', 'origin') or '') if source_url is None else source_url
    if url.startswith('git@github.com:'):
        url = 'https://github.com/' + url.removeprefix('git@github.com:').removesuffix('.git')
    if not url.startswith('https://'):
        url = ''
    if url:
        parts = urlsplit(url)
        if source_url:
            require(not parts.username and not parts.password and not parts.query and not parts.fragment, 'source locator must not contain credentials/query/fragment')
        # A local HTTPS Git remote may carry credentials; never ship them.
        host = parts.hostname or ''
        if parts.port:
            host += ':' + str(parts.port)
        url = urlunsplit(('https', host, parts.path.removesuffix('.git'), '', ''))
    if revision is None and git(root, 'status', '--porcelain'):
        # Do not misrepresent an uncommitted local build as the selected commit.
        rev += '+working-tree'
    dependencies = []
    for entry in cfg.get('inputs', []):
        data = read_source(root, entry['path'])
        require(sha(data) == entry['sha256'], 'input byte pin mismatch')
        repo = Repository(data.decode('utf-8'))
        require(repo.identity == entry['identity'], 'input identity pin mismatch')
        dependencies.append(repo)
    from package_imports import load_imports, preserve_specifications
    imported_packages, imports, imported_repos = load_imports(root, cfg)
    dependencies.extend(imported_repos)
    spec, spec_doc = spec_info(root, cfg)
    definitions = {}
    for entry in cfg['exports']:
        alias = cfg['namespace'] + '/' + entry['name']
        require(alias not in definitions, 'duplicate export: ' + alias)
        require(entry['path'].startswith('types/'), 'export source must be under types/')
        raw = source(read_source(root, entry['path']))
        require(isinstance(raw, dict) and 'blueId' not in raw, 'exports must be newly authored definitions; exact imports belong in inputs')
        require('Normative specification: blueId:' not in raw.get('description', ''), 'source already contains generated footer')
        if spec:
            raw['description'] = raw.get('description', '').rstrip() + footer(spec, entry.get('section', ''))
        definitions[alias] = raw
    authored = Repository.from_definitions(cfg['name'], definitions, dependencies=dependencies)
    language = Language(repositories=[authored])
    records = {}
    # The actual SDK computes reachable records and retains cyclic owning proofs.
    for tid in authored.aliases.values():
        records.update(language.load(tid, goal='definition').dependency_responses())
    imported_definitions, imported_files = preserve_specifications(imported_packages, imports, records)
    if spec_doc:
        records.update(spec_doc.dependency_responses())
    metadata = {'builderPolicy': language._policy(), 'supportingInputs': cfg.get('inputs', [])}
    if imports:
        metadata.update(imports=imports, importedDefinitions=imported_definitions)
    repo = Repository.from_payload(cfg['name'], authored.aliases, records, metadata=metadata)
    audit = repo.audit()
    require(audit['failed'] == 0, 'strict definition audit failed: ' + str(audit))
    files = {'repository.json': (repo._json + '\n').encode(), 'README.md': read_source(root, cfg['readme'])}
    for name in cfg.get('files', []):
        allowed_file(name)
        require(name not in files and name != 'package.json', 'duplicate/reserved archive source')
        files[name] = read_source(root, name)
    if spec:
        require(spec['path'] not in files, 'duplicate specification source')
        files[spec['path']] = read_source(root, spec['path'])
    require(not set(imported_files) & set(files), 'imported specification path collision')
    files.update(imported_files)
    exports = []
    for entry in cfg['exports']:
        alias = cfg['namespace'] + '/' + entry['name']
        exports.append({'name': entry['name'], 'alias': alias, 'sourcePath': entry['path'], 'blueId': repo.aliases[alias],
                        'specification': {**spec, 'section': entry.get('section', '')} if spec else None})
    manifest = {'format': FORMAT, 'name': cfg['name'], 'version': ver, 'source': {'revision': rev, 'repository': url},
                'repository': {'path': 'repository.json', 'identity': repo.identity, 'format': 'blue-python-repository/1'},
                'exports': exports, 'specification': spec, 'supportingInputs': cfg.get('inputs', []),
                'toolchain': {'blueArchiveSha256': bootstrap.LOCK['blue']['archiveSha256'], 'languagePolicy': audit['languagePolicy']},
                'validation': {'kind': 'Repository.audit', 'definitions': audit['aliases'], 'passed': audit['passed']},
                'files': {name: {'sha256': sha(data), 'size': len(data)} for name, data in sorted(files.items())}}
    if imports:
        manifest.update(imports=imports, importedDefinitions=imported_definitions)
    files['package.json'] = wire(manifest)
    buf = io.BytesIO()
    # STORED avoids platform/zlib variation while fixing all ZIP header choices.
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data)
    data = buf.getvalue()
    package = verify_bytes(data)
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    return package

def _verify_bytes_uncached(data):
    require(len(data) <= MAX_BYTES, 'archive exceeds host transfer limit')
    files, folded = {}, set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        require(len(entries) <= MAX_FILES and sum(i.file_size for i in entries) <= MAX_BYTES, 'archive exceeds host extraction limits')
        for info in entries:
            name = info.filename
            allowed_file(name)
            require(name.casefold() not in folded, 'duplicate/ambiguous archive path')
            folded.add(name.casefold())
            mode = info.external_attr >> 16
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG) and mode & 0o111 == 0, 'links/directories/executable files forbidden')
            require(not info.flag_bits & 1, 'encrypted archive forbidden')
            raw = archive.read(info)
            raw.decode('utf-8')
            require(b'\r' not in raw and not raw.startswith(b'\xef\xbb\xbf'), 'archive text must be UTF-8/LF without BOM')
            if name.endswith('.json'):
                parse(raw)
            files[name] = raw
    require('package.json' in files and 'repository.json' in files and 'README.md' in files, 'missing required archive files')
    manifest = parse(files['package.json'])
    if manifest.get('format') == 'blue-package/0.3-local':
        from package_v2 import verify_v2
        return verify_v2(data, files, manifest)
    require(manifest.get('format') == FORMAT, 'unsupported package format')
    version(manifest['version'])
    require(set(manifest['files']) == set(files) - {'package.json'}, 'inventory differs from archive')
    for name, entry in manifest['files'].items():
        require(entry == {'sha256': sha(files[name]), 'size': len(files[name])}, 'file integrity mismatch: ' + name)
    repo = Repository(files['repository.json'].decode())
    require(manifest['repository'] == {'path': 'repository.json', 'identity': repo.identity, 'format': 'blue-python-repository/1'}, 'repository identity/profile mismatch')
    require(manifest['name'] == repo.name, 'package/repository name mismatch')
    require(manifest['supportingInputs'] == repo.metadata.get('supportingInputs'), 'supporting provenance mismatch')
    require(manifest['toolchain']['blueArchiveSha256'] == bootstrap.LOCK['blue']['archiveSha256'], 'unsupported Blue snapshot')
    exports = manifest['exports']
    require(len({e['name'] for e in exports}) == len(exports) and len({e['alias'] for e in exports}) == len(exports), 'duplicate exports')
    require({e['alias']: e['blueId'] for e in exports} == repo.aliases, 'export inventory differs from repository aliases')
    audit = repo.audit()
    require(audit['failed'] == 0, 'strict audit failed')
    require(manifest['validation'] == {'kind': 'Repository.audit', 'definitions': len(exports), 'passed': audit['passed']}, 'invalid audit claim')
    require(manifest['toolchain']['languagePolicy'] == audit['languagePolicy'], 'unsupported semantic toolchain policy')
    language = Language(repositories=[repo])
    spec = manifest.get('specification')
    expected_records = {}
    for e in exports:
        expected_records.update(language.load(e['blueId'], goal='definition').dependency_responses())
    from package_imports import verify_imports
    verify_imports(manifest, repo, files, language, expected_records)
    if spec:
        path = spec['path']
        require(path in files, 'specification unavailable in archive')
        require(sha(files[path]) == spec['sha256'], 'specification bytes mismatch')
        admitted = language.create(json.dumps({'type': 'Text', 'value': files[path].decode()}))
        require(admitted.blue_id == spec['blueId'], 'specification Text identity mismatch')
        require(spec['blueId'] in repo.records, 'specification record unavailable')
        exact = language.load(spec['blueId'])
        require(exact.blue_id == admitted.blue_id, 'specification record mismatch')
        expected_records.update(exact.dependency_responses())
    require(set(expected_records) == set(repo.records), 'repository contains missing or unrelated records')
    for e in exports:
        association = e.get('specification')
        if not spec:
            require(association is None, 'unexpected specification association')
            continue
        require(association and {k: association[k] for k in spec} == spec, 'export specification association mismatch')
        definition = parse(language.verify(e['blueId']))
        require(definition.get('description', '').endswith(footer(spec, association['section'])), 'description footer mismatch')
    return Package(manifest, repo, files, data, audit)

def read_package(path):
    path = Path(path)
    if path.is_dir():
        require(not path.is_symlink(), 'cache destination cannot be a symlink')
        package = verify_bytes((path / 'package.bluepkg').read_bytes())
        from distribution import manifest_layer
        receipt = parse((path / 'receipt.json').read_bytes())
        layer = manifest_layer((path / 'oci-manifest.json').read_bytes(), receipt['digest'])
        require(receipt['archiveSha256'] == package.archive_sha == layer['digest'] and layer['size'] == len(package.archive), 'restored artifact receipt mismatch')
        for name, data in package.files.items():
            p = path / name
            require(p.resolve().is_relative_to(path.resolve()) and not p.is_symlink() and p.is_file() and p.read_bytes() == data, 'corrupt restored file: ' + name)
        return package
    return verify_bytes(path.read_bytes())

def mount(language, package, prefix, names):
    require(isinstance(prefix, str) and re.fullmatch(r'@?[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*', prefix) is not None, 'invalid local prefix')
    require(names and len(names) == len(set(names)), 'explicit unique export selection required')
    exports = {e['name']: e['blueId'] for e in package.manifest['exports']}
    require(set(names) <= set(exports), 'unknown selected export')
    aliases = {prefix + '/' + n: exports[n] for n in names}
    # Derived overlay is deliberately its own repository with original provenance.
    overlay = Repository.from_payload('mount:' + prefix, aliases, package.repository.records,
        metadata={'originalRepository': package.repository.identity, 'archive': package.archive_sha})
    language.enable_repository(overlay)  # Runtime validates conflicts before mutation.
    return overlay

def label(package, exact_id):
    return next((e['name'] for e in package.manifest['exports'] if e['blueId'] == exact_id), None)

def admit(package, source_text, mounts, *, source_format='yaml', query=''):
    """Admit caller-selected source under an explicit, local naming environment."""
    language = Language()
    for selection in mounts:
        mount(language, package, selection['prefix'], selection['exports'])
    document = language.create(source_text, format=source_format)
    language.publish_document(document)
    return {'blueId': document.blue_id, 'exact': parse(document.exact_text),
            'query': language.query(document.exact_text, query, mode='exact'),
            'mounted': language.repositories, 'repository': package.repository.identity}

def project_smoke(root, package=None):
    root = Path(root).resolve()
    cfg = config(root)
    package = package or build(root)
    results = []
    for example in cfg.get('examples', []):
        text = read_source(root, example['source']).decode('utf-8')
        result = admit(package, text, example['mounts'], query=example.get('query', ''),
                       source_format=example.get('format', 'yaml'))
        if 'expectedQuery' in example:
            require(result['query'] == example['expectedQuery'], 'project example query mismatch')
        if 'expectedValue' in example:
            observed = result['query']
            require(observed.get('outcome') == 'Established' and observed.get('value', {}).get('value') == example['expectedValue'], 'project example query mismatch')
        results.append({'source': example['source'], **result})
    return {'audit': package.audit, 'examples': results, 'scope': 'current project audit and explicitly selected declarative examples; no downloaded scripts'}


# Bounded process-local reuse of successful verification for identical immutable
# bytes and the exact interpreter policy. Callers receive a defensive copy, so
# mutable manifest edits cannot forge reusable evidence. Changed bytes always
# take the full verification path.
from collections import OrderedDict as _OrderedDict
from copy import deepcopy as _deepcopy
_VERIFIED_PACKAGES = _OrderedDict()
_VERIFIED_PACKAGE_BYTES = 0

def verify_bytes(data):
    global _VERIFIED_PACKAGE_BYTES
    data = bytes(data)
    key = (Language._policy(), sha(data))
    cached = _VERIFIED_PACKAGES.get(key)
    if cached is not None:
        _VERIFIED_PACKAGES.move_to_end(key)
        return _deepcopy(cached)
    package = _verify_bytes_uncached(data)
    if len(data) <= 32 * 1024 * 1024:
        while _VERIFIED_PACKAGES and (len(_VERIFIED_PACKAGES) >= 8 or _VERIFIED_PACKAGE_BYTES + len(data) > 32 * 1024 * 1024):
            _, old = _VERIFIED_PACKAGES.popitem(last=False)
            _VERIFIED_PACKAGE_BYTES -= len(old.archive)
        _VERIFIED_PACKAGES[key] = _deepcopy(package)
        _VERIFIED_PACKAGE_BYTES += len(data)
    return package
