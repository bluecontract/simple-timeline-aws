"""Reproducible importer for the supplied Java Blue repository export.

No network resolution. Published identities must verify. Java enum serialization
is canonicalized only when necessary AND the resulting exact body matches the
published ID. Cycles are reconstructed as complete owning-set proofs.
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict
import copy
import hashlib
import json
from typing import Any
from algorithms import blue as B
from blue_language import Language
from vendor import yaml
from .api import Repository, RepositoryError, canonical


def canonical_enums(value: Any, context: B.Context) -> Any:
    if isinstance(value, list):
        return [canonical_enums(x, context) for x in value]
    if not isinstance(value, dict):
        return value
    out = {k: canonical_enums(v, context) for k, v in value.items()}
    schema = out.get('schema')
    if isinstance(schema, dict) and isinstance(schema.get('enum'), list):
        def key(item):
            node = B.normalize(B.parse(canonical(item)), context)
            return B.canonical_text(B.export_tree(node)).encode('utf-8')
        schema['enum'] = sorted(schema['enum'], key=key)
    return out


def import_java(repository_resources: str | Path, contracts_registry: str | Path,
                *, name: str = 'blue-published') -> tuple[Repository, dict]:
    resources, contracts = Path(repository_resources), Path(contracts_registry)
    provider_path = resources / 'BlueRepository.provider.json'
    manifest_path = resources / 'manifest.json'
    bundle = json.loads(provider_path.read_text(encoding='utf-8'), object_pairs_hook=B.pairs_no_duplicates)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'), object_pairs_hook=B.pairs_no_duplicates)
    claimed = manifest.get('providerSourceSha256')
    if hashlib.sha256(provider_path.read_bytes()).hexdigest() != claimed:
        raise RepositoryError('provider bundle bytes do not match Java manifest')
    cm = yaml.safe_load((contracts / 'manifest.yaml').read_text(encoding='utf-8'))
    entries = copy.deepcopy(bundle['entries'])
    inline = copy.deepcopy(bundle.get('inlineTypeDefinitions', []))
    for item in cm['entries']:
        if item.get('fixtureOnly'):
            continue
        path = contracts / item['path']
        if path.parent.resolve() != contracts.resolve():
            raise RepositoryError('registry path escape')
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise RepositoryError('registry source hash mismatch: ' + item['path'])
        raw = yaml.safe_load(path.read_text(encoding='utf-8'))
        entries.append({'qualifiedName': raw['name'], 'blueId': item['blueId'], 'content': raw})
    aliases, records, bodies, cyclic = {}, {}, {}, defaultdict(dict)
    changes = []
    context = Language()._context()
    for item in entries + inline:
        tid, raw = item['blueId'], item['content']
        if 'qualifiedName' in item:
            alias = item['qualifiedName']
            if alias in aliases and aliases[alias] != tid:
                raise RepositoryError('duplicate imported alias: ' + alias)
            aliases[alias] = tid
        if '#' in tid:
            master, index = tid.split('#')
            cyclic[master][int(index)] = raw
            continue
        node = B.normalize(B.parse(canonical(raw)), context)
        if B.identity(node) != tid:
            raw = canonical_enums(raw, context)
            node = B.normalize(B.parse(canonical(raw)), context)
            if B.identity(node) != tid:
                raise RepositoryError('published identity does not verify: ' + tid)
            changes.append({'blueId': tid, 'name': item.get('qualifiedName'),
                            'action': 'canonical schema enum order; published ID preserved'})
        bodies[tid] = raw
        # Canonical exact serialization, not the Java source carrier.
        records[tid] = {'text': B.export_exact(node, context), 'mode': 'exact', 'format': 'json'}
    sets = []
    for master, members in sorted(cyclic.items()):
        if sorted(members) != list(range(len(members))):
            raise RepositoryError('incomplete owning set: ' + master)
        def symbolic(value):
            if isinstance(value, list): return [symbolic(v) for v in value]
            if not isinstance(value, dict): return value
            if set(value) == {'blueId'} and value['blueId'].startswith(master + '#'):
                return {'blueId': 'this#' + value['blueId'].split('#')[1]}
            return {k: symbolic(v) for k,v in value.items()}
        proof = {'members': [symbolic(members[i]) for i in range(len(members))]}
        result = B.finalize_set(proof['members'], context)
        if result['master'] != master or result['ids'] != [master + '#' + str(i) for i in range(len(members))]:
            raise RepositoryError('published cyclic set does not verify: ' + master)
        for i in range(len(members)):
            tid = master + '#' + str(i)
            records[tid] = {'proof': proof, 'body': members[i]}
            bodies[tid] = members[i]
        sets.append({'master': master, 'members': len(members), 'status': 'PASS'})
    report = {'providerSha256': claimed, 'javaRepositoryBlueId': bundle['repositoryBlueId'],
              'namedJavaTypes': len(bundle['entries']), 'aliasesWithContracts': len(aliases),
              'records': len(records), 'cyclicSets': sets, 'carrierCanonicalizations': changes,
              'note': 'Exact content verification, not whole semantic admission.'}
    repository = Repository.from_payload(name, aliases, records, metadata={
        'profile': 'published', 'origin': 'supplied-java-export', 'import': report})
    return repository, report
