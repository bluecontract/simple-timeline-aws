"""Local package revision with native specification metadata.
All Language operations are delegated to the pinned Python implementation.
Package and Protocol Specification are ordinary definitions supplied by Language.
The legacy filename is retained to minimize distribution-adapter churn.
"""
from __future__ import annotations
import io
import json
import re
import stat
import zipfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from package_core import (Language, MemoryProvider, Repository, Package, PackageError,
                          config, current_ledger, git, parse, read_package, read_source,
                          require, safe_name, sha, source, version, wire)
import bootstrap

FORMAT = 'blue-package/0.3-local'
SEMANTIC_FORMAT = 'blue-package-model/2-specification-metadata'
LANGUAGE_PROFILE = 'blue-language/2026-09-26-specification-metadata-1'
LOCK = 'blue-package.lock.json'
PREFIX = re.compile(r'@?[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*')
_STANDARD=bootstrap.WORKSPACE/'python/src/registry/standard'
PACKAGE_DEFINITION=json.loads((_STANDARD/'Package.json').read_text())
SPEC_DEFINITION=json.loads((_STANDARD/'ProtocolSpecification.json').read_text())


def merge(target, values):
    for key, value in values.items():
        if key in target and target[key] != value:
            a, b = target[key], value
            require(a.get('mode') == b.get('mode') and parse(a['text']) == parse(b['text']),
                    'conflicting exact content record: ' + key)
        target[key] = value


def base_language(records=None):
    return Language(provider=MemoryProvider(records or {}),core_contracts=False)


def bootstrap_types():
    language = Language(core_contracts=False)
    package = language.admit_definition(wire(PACKAGE_DEFINITION).decode())
    spec = language.admit_definition(wire(SPEC_DEFINITION).decode())
    records = package.dependency_responses()
    merge(records, spec.dependency_responses())
    return package.blue_id, spec.blue_id, records


def admitted(value, records, *, goal='definition'):
    language = base_language(records)
    doc = language.create(wire(value).decode(), goal=goal)
    merge(records, doc.dependency_responses())
    return doc


def ref(value):
    return {'blueId': value}


def text_record(data, records):
    return admitted({'type': 'Text', 'value': data.decode('utf-8')}, records, goal='value')


def _selection(root, cfg):
    result = {}
    entries = cfg.get('imports', {})
    require(isinstance(entries, dict), 'imports must be a prefix map')
    for prefix, entry in sorted(entries.items()):
        require(isinstance(prefix, str) and PREFIX.fullmatch(prefix), 'invalid import prefix: ' + str(prefix))
        require(isinstance(entry, dict) and set(entry) <= {'path', 'source'} and 'path' in entry,
                'imports need a local path; optional source is a retrieval hint, not identity')
        if entry.get('source'):
            require(isinstance(entry['source'], str) and re.fullmatch(r'[a-z0-9.-]+(?::[0-9]+)?/[a-z0-9._/-]+@sha256:[0-9a-f]{64}',entry['source']), 'source must be an exact, credential-free OCI locator')
        path = root / safe_name(entry['path'])
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                'missing/unsafe imported archive: ' + entry['path'])
        p = read_package(path)
        require(p.manifest['format'] == FORMAT, 'v2 imports require a v2 package; preserve legacy artifacts separately')
        result[prefix] = p
    return result


def _pins(root, cfg, packages):
    return {'format': 2, 'imports': {prefix: {
        'path': cfg['imports'][prefix]['path'],
        'packageBlueId': p.manifest['packageBlueId'],
        'archiveSha256': p.archive_sha,
        'repositoryIdentity': p.repository.identity,
        'name': p.manifest['name'], 'version': p.manifest['version'],
        **({'source': cfg['imports'][prefix]['source']} if cfg['imports'][prefix].get('source') else {})
    } for prefix, p in packages.items()}}


def lock_v2(root, cfg=None):
    root = Path(root).resolve()
    cfg = cfg or config(root)
    pins = _pins(root, cfg, _selection(root, cfg))
    tmp = root / (LOCK + '.tmp')
    tmp.write_bytes(wire(pins))
    tmp.replace(root / LOCK)
    return pins


def load_v2_imports(root, cfg):
    packages = _selection(root, cfg)
    actual = _pins(root, cfg, packages)
    require((root / LOCK).is_file(), 'missing package lock; review inputs and run lock-imports')
    require(parse(read_source(root, LOCK)) == actual, 'import lock mismatch; no automatic upgrades; review and run lock-imports')
    return packages, actual


def _source_info(root, revision, source_url):
    rev = revision or git(root, 'rev-parse', 'HEAD') or 'uncommitted'
    if revision is None and git(root, 'status', '--porcelain'):
        rev += '+working-tree'
    url = (git(root, 'remote', 'get-url', 'origin') or '') if source_url is None else source_url
    if url.startswith('git@github.com:'):
        url = 'https://github.com/' + url.removeprefix('git@github.com:').removesuffix('.git')
    if not url.startswith('https://'):
        url = ''
    if url:
        parts = urlsplit(url)
        require(not source_url or not any([parts.username, parts.password, parts.query, parts.fragment]),
                'source URL must not contain credentials or query/fragment')
        url = urlunsplit(('https', parts.hostname + ((':' + str(parts.port)) if parts.port else ''),
                          parts.path.removesuffix('.git'), '', ''))
    return {'revision': rev, 'repository': url}


def _index_merge(dst, src, kind):
    for bid, obj in src.items():
        require(bid not in dst or dst[bid] == obj, 'conflicting ' + kind + ': ' + bid)
        dst[bid] = obj


def build_v2(root, output=None, release_version=None, revision=None, source_url=None):
    root = Path(root).resolve()
    cfg = config(root)
    require(not cfg.get('specification'), 'v2 separates protocol from documentation; use protocol explicitly')
    current_ledger(root)
    ver = version(release_version or cfg['version'])
    require(not cfg.get('previewOnly') or '-' in ver,
            'this unqualified candidate permits prerelease versions only; qualification is required before promotion')
    packages, pins = load_v2_imports(root, cfg)
    package_type, spec_type, records = bootstrap_types()
    package_index, spec_index, dependencies = {}, {}, []
    for prefix, p in packages.items():
        merge(records, parse(p.files['package-records.json']))
        _index_merge(package_index, p.manifest['semanticPackages'], 'package witness')
        _index_merge(spec_index, p.manifest['semanticSpecifications'], 'specification witness')
        dependencies.append(Repository.from_payload('import:' + prefix,
            {prefix + '/' + e['name']: e['blueId'] for e in p.manifest['exports']}, p.repository.records))
    # Explicit raw inputs are only for exporting existing exact protocol catalogues.
    inputs = {}
    for entry in cfg.get('inputs', []):
        data = read_source(root, entry['path'])
        require(sha(data) == entry['sha256'], 'input byte pin mismatch')
        repo = Repository(data.decode())
        require(repo.identity == entry['identity'], 'input identity pin mismatch')
        dependencies.append(repo)
        inputs[entry['path']] = repo
        merge(records, repo.records)
    if cfg.get('bootstrapLanguage'):
        require(not packages and cfg.get('language') is None, 'Language bootstrap may not depend on its own package')
        language_ref = None
    else:
        lp = cfg.get('language')
        require(lp in packages, 'language must name an explicitly imported Language package')
        language_ref = packages[lp].manifest['packageBlueId']
        lroot = package_index[language_ref]
        require(lroot['bootstrapLanguage'] is True, 'selected language import is not a Language release')
        for p in packages.values():
            p_root = p.manifest['semanticPackages'][p.manifest['packageBlueId']]
            require((p_root['bootstrapLanguage'] and p.manifest['packageBlueId'] == language_ref) or
                    (not p_root['bootstrapLanguage'] and p_root['language'] == ref(language_ref)),
                    'cross-Language import is unsupported; use a separate interpreter context')
    files = {'README.md': read_source(root, cfg['readme'])}
    for name in cfg.get('files', []):
        safe_name(name)
        require(name not in files and name not in {'package.json','repository.json','package.blue.json','package-records.json'},
                'duplicate or reserved file')
        files[name] = read_source(root, name)
    protocol_id = None
    native_rules_id = None
    protocol = cfg.get('protocol')
    if protocol:
        require(not cfg.get('bootstrapLanguage'), 'Language bootstrap uses selected core rules, not its own protocol requirement')
        path = safe_name(protocol['rules'])
        require(path.startswith('spec/') and path.endswith('.md'), 'protocol rules must be frozen source spec/*.md')
        data = read_source(root, path)
        require(current_ledger(root).get(path) == sha(data), 'protocol rules not committed in frozen ledger')
        files[path] = data
        rules_doc = text_record(data, records)
        native_rules_id = rules_doc.blue_id
        requirements = {}
        for label, prefix in sorted(protocol.get('requires', {}).items()):
            require(prefix in packages, 'protocol prerequisite needs an explicit package import')
            sid = packages[prefix].manifest['protocol']
            require(sid, 'required package declares no protocol: ' + prefix)
            requirements[label] = ref(sid)
        spec_source = {'type': ref(spec_type), 'name': protocol['name'],
            'language': ref(language_ref), 'rules': ref(rules_doc.blue_id),
            'requires': requirements, 'status': protocol.get('status', 'candidate')}
        for field,key in [('effectiveRules','effectiveRules'),('schedulingPolicy','schedulingPolicy')]:
            if protocol.get(key):
                extra=read_source(root,safe_name(protocol[key]));files[protocol[key]]=extra
                spec_source[field]=ref(text_record(extra,records).blue_id)
        doc = admitted(spec_source, records)
        protocol_id = doc.blue_id
        spec_index[protocol_id] = spec_source
    definitions, exact_exports = {}, {}
    own_bindings = {}
    for entry in cfg['exports']:
        alias = cfg['namespace'] + '/' + entry['name']
        require(alias not in definitions and alias not in exact_exports, 'duplicate export')
        if 'fromInput' in entry:
            require(entry['fromInput'] in inputs, 'missing exact catalogue input')
            repo = inputs[entry['fromInput']]
            original = entry['inputAlias']
            require(original in repo.aliases, 'exact catalogue export missing: ' + original)
            exact_exports[alias] = repo.aliases[original]
        else:
            require(entry['path'].startswith('types/'), 'definition source must be under types/')
            raw = source(read_source(root, entry['path']))
            require(isinstance(raw, dict) and 'blueId' not in raw, 'expected a new Source definition')
            require('spec' not in raw, 'use specification for metadata; spec is an ordinary field and is not automatically migrated')
            if protocol_id:
                raw['specification'] = ref(native_rules_id)
            definitions[alias] = raw
    if definitions:
        dependencies.append(Repository.from_payload('package-authoring-context', {}, records))
    authored = Repository.from_definitions(cfg['name'], definitions, dependencies=dependencies) if definitions else None
    own_aliases = dict(authored.aliases) if authored else {}
    own_aliases.update(exact_exports)
    lookup_records = dict(records)
    if authored:
        merge(lookup_records, authored.records)
    language = base_language(lookup_records)
    business_records = {}
    for tid in own_aliases.values():
        merge(business_records, language.load(tid, goal='definition').dependency_responses())
        if protocol_id:
            body=parse(language.verify(tid))
            require(body.get('specification')==ref(native_rules_id), 'export must natively bind the runtime specification: '+tid)
            own_bindings[tid] = {'specification': ref(native_rules_id), 'protocol': ref(protocol_id), 'binding': 'native-metadata'}
    repo = Repository.from_payload(cfg['name'], own_aliases, business_records,
        metadata={'format': SEMANTIC_FORMAT, 'supportingInputs': cfg.get('inputs', [])})
    audit = repo.audit()
    require(audit['failed'] == 0, 'definition audit failed: ' + str(audit))
    merge(records, business_records)
    # Include all deliberately published text assets in the semantic identity,
    # but never source URLs, archive hashes, build commits or retrieval locations.
    docs = {}
    for name, data in sorted(files.items()):
        d = text_record(data, records)
        docs[name] = {'content': ref(d.blue_id), 'sha256': sha(data), 'size': len(data)}
    required = []
    for prefix in cfg.get('executionRequires', []):
        require(prefix in packages, 'executionRequires must select a direct import')
        p = packages[prefix]
        r = package_index[p.manifest['packageBlueId']]
        if r['protocol']:
            required.append(r['protocol'])
        required.extend(r['declaredRequirements'])
    if protocol_id:
        required.append(ref(protocol_id))
    required = [ref(x) for x in sorted({x['blueId'] for x in required})]
    semantic = {'type': ref(package_type), 'format': SEMANTIC_FORMAT, 'name': cfg['name'], 'version': ver,
        'identityProfile': LANGUAGE_PROFILE, 'bootstrapLanguage': bool(cfg.get('bootstrapLanguage')),
        'language': ref(language_ref) if language_ref else None,
        'exports': {e['name']: ref(own_aliases[cfg['namespace'] + '/' + e['name']]) for e in cfg['exports']},
        'imports': {prefix: ref(p.manifest['packageBlueId']) for prefix, p in packages.items()},
        'protocol': ref(protocol_id) if protocol_id else None,
        'specBindings': own_bindings, 'declaredRequirements': required, 'documentation': docs}
    package_doc = admitted(semantic, records)
    package_id = package_doc.blue_id
    package_index[package_id] = semantic
    # Retain only content reachable from the identified package. This keeps
    # unrelated repository records out, while preserving imported package roots.
    records = base_language(records).load(package_id, goal='definition').dependency_responses()
    files['repository.json'] = (repo._json + '\n').encode()
    files['package.blue.json'] = (package_doc.exact_text + '\n').encode()
    files['package-records.json'] = wire(records)
    manifest = {'format': FORMAT, 'name': cfg['name'], 'version': ver,
        'source': _source_info(root, revision, source_url),
        'packageBlueId': package_id, 'language': language_ref, 'protocol': protocol_id,
        'specification': None,  # v1 compatibility surface; protocol is a different, explicit concept.
        'specBindingMode': 'native-specification-metadata',
        'repository': {'path': 'repository.json','identity': repo.identity,'format':'blue-python-repository/1'},
        'exports': [{'name': e['name'], 'alias': cfg['namespace'] + '/' + e['name'],
            'blueId': own_aliases[cfg['namespace'] + '/' + e['name']], 'specification': None,
            'specificationMetadata': native_rules_id if protocol_id else None} for e in cfg['exports']],
        'imports': pins['imports'], 'importedDefinitions': [], 'supportingInputs': cfg.get('inputs', []),
        'semanticPackages': package_index, 'semanticSpecifications': spec_index,
        'languageProfile': LANGUAGE_PROFILE,
        'toolchain': {'blueArchiveSha256': bootstrap.LOCK['blue']['archiveSha256'], 'languagePolicy': audit['languagePolicy']},
        'validation': {'kind':'Repository.audit','definitions':audit['aliases'],'passed':audit['passed']},
        'files': {n:{'sha256':sha(b),'size':len(b)} for n,b in sorted(files.items())}}
    files['package.json'] = wire(manifest)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            i = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
            i.create_system = 3
            i.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(i, data)
    data = buf.getvalue()
    from package_core import verify_bytes
    package = verify_bytes(data)
    if output:
        path = Path(output);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return package


def verify_v2(data, files, m):
    require(set(m['files']) == set(files) - {'package.json'}, 'archive inventory mismatch')
    for name, raw in files.items():
        if name != 'package.json':
            require(m['files'][name] == {'sha256':sha(raw),'size':len(raw)}, 'file integrity mismatch: ' + name)
    # The installed reader selects a supported semantic profile before admission.
    # Build-source hashes identify provenance; a Java implementation is not a Python build.
    require(m.get('languageProfile') == LANGUAGE_PROFILE, 'unsupported Language profile')
    require(isinstance(m.get('toolchain'), dict), 'missing producer provenance')
    records = parse(files['package-records.json'])
    language = base_language(records)
    pid = m['packageBlueId']
    root = language.admit_definition(files['package.blue.json'], mode='exact')
    require(root.blue_id == pid, 'package BlueId mismatch')
    package_type, spec_type, _ = bootstrap_types()
    packages, specs = m['semanticPackages'], m['semanticSpecifications']
    require(pid in packages, 'missing package witness')
    allowed_p = {'type','format','name','version','identityProfile','bootstrapLanguage','language',
                 'exports','imports','protocol','specBindings','declaredRequirements','documentation'}
    visited_p, visited_s = set(), set()
    active_p, active_s = set(), set()
    def check_spec(sid, lang):
        require(sid not in active_s, 'cyclic specification requirements are not supported')
        if sid in visited_s:
            require(specs[sid]['language'] == ref(lang), 'cross-Language specification')
            return
        require(sid in specs, 'missing required specification: ' + sid)
        s = specs[sid]
        require({'type','name','language','rules','requires','status'}<=set(s)<= {'type','name','language','rules','requires','status','effectiveRules','schedulingPolicy'} and s['type'] == ref(spec_type),
                'invalid specification witness')
        require(s['language'] == ref(lang), 'specification Language mismatch')
        check = language.admit_definition(wire(s).decode())
        require(check.blue_id == sid, 'specification identity mismatch')
        # Rules must be accessible Text, not merely a claimed external hash.
        observed = language.query(language.load(s['rules']['blueId']).exact_text, '', mode='exact')
        require(observed.get('value', {}).get('kind') == 'Text', 'protocol rules must be Text')
        for field in ('effectiveRules','schedulingPolicy'):
            if field in s:
                extra=language.query(language.load(s[field]['blueId']).exact_text,'',mode='exact')
                require(extra.get('value',{}).get('kind')=='Text', 'protocol supplement must be exact Text')
        active_s.add(sid)
        for need in s['requires'].values():
            require(set(need) == {'blueId'}, 'invalid specification prerequisite')
            check_spec(need['blueId'], lang)
        active_s.remove(sid);visited_s.add(sid)
    def check_package(bid, expected_lang=None):
        require(bid not in active_p, 'cyclic package imports are not supported')
        if bid in visited_p:
            prior = packages[bid]
            require(expected_lang is None or (bid == expected_lang if prior['bootstrapLanguage'] else prior['language'] == ref(expected_lang)),
                    'cross-Language package graph')
            return
        require(bid in packages, 'missing imported package witness: ' + bid)
        p = packages[bid]
        require(set(p) == allowed_p and p['type'] == ref(package_type) and p['format'] == SEMANTIC_FORMAT,
                'invalid package semantic record')
        require(p['identityProfile'] == LANGUAGE_PROFILE, 'package Language profile mismatch')
        require(language.admit_definition(wire(p).decode()).blue_id == bid, 'imported package identity mismatch')
        version(p['version'])
        require(type(p['bootstrapLanguage']) is bool, 'invalid Language bootstrap flag')
        lang = p['language']['blueId'] if p['language'] else None
        if p['bootstrapLanguage']:
            require(expected_lang is None or bid == expected_lang, 'foreign Language bootstrap in one interpretation graph')
            require(lang is None and not p['imports'] and p['protocol'] is None,
                    'invalid Language bootstrap')
        else:
            require(lang in packages and packages[lang]['bootstrapLanguage'], 'missing Language release package')
            require(expected_lang is None or lang == expected_lang, 'cross-Language package graph')
        active_p.add(bid)
        for prefix, target in p['imports'].items():
            require(PREFIX.fullmatch(prefix) and set(target)=={'blueId'}, 'invalid scoped import')
            check_package(target['blueId'], lang)
        if lang:
            require(lang in {v['blueId'] for v in p['imports'].values()}, 'Language must be an explicit import')
        if p['protocol']:
            check_spec(p['protocol']['blueId'],lang)
        for requirement in p['declaredRequirements']:
            check_spec(requirement['blueId'],lang)
        require(set(p['specBindings']) == ({v['blueId'] for v in p['exports'].values()} if p['protocol'] else set()),
                'protocol association coverage mismatch')
        for tid, binding in p['specBindings'].items():
            require(set(binding)=={'specification','protocol','binding'} and p['protocol']==binding['protocol'], 'specification binding mismatch')
            check_spec(binding['protocol']['blueId'],lang)
            require(binding['binding']=='native-metadata','unsupported metadata association')
            require(binding['specification']==specs[binding['protocol']['blueId']]['rules'],'native rules differ from protocol descriptor')
            definition=parse(language.verify(tid))
            require(definition.get('specification')==binding['specification'], 'type native specification mismatch')
        for name, target in p['exports'].items():
            require(name and set(target)=={'blueId'}, 'invalid export')
            language.load(target['blueId'],goal='definition')
        for path, asset in p['documentation'].items():
            safe_name(path)
            require(set(asset)=={'content','sha256','size'}, 'invalid documentation descriptor')
            doc = language.load(asset['content']['blueId'])
            observation = language.query(doc.exact_text, '', mode='exact')
            require(observation.get('value',{}).get('kind')=='Text', 'documentation must be exact Text')
            raw = observation['value']['value'].encode('utf-8')
            require(sha(raw)==asset['sha256'] and len(raw)==asset['size'], 'documentation identity/bytes mismatch')
            if bid == pid:
                require(files.get(path)==raw, 'documentation file differs from package identity')
        active_p.remove(bid);visited_p.add(bid)
    check_package(pid)
    require(set(packages)==visited_p and set(specs)==visited_s, 'unrelated semantic witnesses')
    semantic = packages[pid]
    require(set(files) - {'package.json','package.blue.json','package-records.json','repository.json'} ==
            set(semantic['documentation']), 'archive contains an asset not identified by the package')
    require(m['name']==semantic['name'] and m['version']==semantic['version'], 'package metadata mismatch')
    require(m['language']==(semantic['language']['blueId'] if semantic['language'] else None), 'Language declaration mismatch')
    require(m['protocol']==(semantic['protocol']['blueId'] if semantic['protocol'] else None), 'protocol declaration mismatch')
    require(set(m['imports'])==set(semantic['imports']), 'import metadata scope mismatch')
    for prefix, entry in m['imports'].items():
        require(entry['packageBlueId']==semantic['imports'][prefix]['blueId'], 'import identity mismatch')
        dep = packages[entry['packageBlueId']]
        require(entry['name']==dep['name'] and entry['version']==dep['version'], 'import release witness mismatch')
    require(m['specification'] is None and not m['importedDefinitions'], 'v2 must not use v1 blanket specification footers')
    repo = Repository(files['repository.json'].decode())
    require(m['repository']=={'path':'repository.json','identity':repo.identity,'format':'blue-python-repository/1'}, 'repository metadata mismatch')
    require(repo.name==m['name'] and len({e['name'] for e in m['exports']})==len(m['exports']), 'invalid export names')
    require({e['alias']:e['blueId'] for e in m['exports']}==repo.aliases, 'export aliases mismatch')
    require({e['name']:ref(e['blueId']) for e in m['exports']}==semantic['exports'], 'export identity mismatch')
    require(all(e['specification'] is None and e['specificationMetadata']==(specs[m['protocol']]['rules']['blueId'] if m['protocol'] else None) for e in m['exports']), 'export protocol mismatch')
    audit = repo.audit()
    require(audit['failed']==0 and m['validation']=={'kind':'Repository.audit','definitions':audit['aliases'],'passed':audit['passed']},
            'definition audit failed/claim mismatch')
    require(set(root.dependency_responses())==set(records), 'package has missing or unrelated content records')
    # Every business record is independently verified and bound to the package graph.
    require(set(repo.records)<=set(records),'repository references content outside the package')
    for k,v in repo.records.items():
        require(v==records[k] or (v.get('mode')==records[k].get('mode') and parse(v['text'])==parse(records[k]['text'])),
                'repository and package records differ')
    return Package(m,repo,files,data,audit)


def requirements(package):
    """Declared package requirements, not a document-specific execution acceptance."""
    m = package.manifest
    require(m['format']==FORMAT, 'requirements command needs a v2 package')
    p = m['semanticPackages'][m['packageBlueId']]
    wanted, pending = set(), [r['blueId'] for r in p['declaredRequirements']]
    while pending:
        sid = pending.pop()
        if sid in wanted:continue
        wanted.add(sid)
        pending.extend(r['blueId'] for r in m['semanticSpecifications'][sid]['requires'].values())
    return {'scope':'package-declared prerequisites; not an execution/authority guarantee',
            'packageBlueId':m['packageBlueId'], 'language':m['language'],
            'specs':[{'blueId':sid,'name':m['semanticSpecifications'][sid]['name'],
                      'status':m['semanticSpecifications'][sid]['status']} for sid in sorted(wanted)]}
