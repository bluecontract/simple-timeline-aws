"""Immutable, opt-in repositories of exact Blue definitions.

A repository supplies aliases and verified content. It does NOT supply execution
permissions, admission evidence, runtime implementations, or network access.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Iterable
import hashlib
import json
from blue_language import Language, MemoryProvider
from algorithms import blue as B


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value: Any) -> str:
    return 'sha256:' + hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


class RepositoryError(ValueError):
    """Invalid repository manifest, conflicting binding, or content evidence."""


@dataclass(frozen=True)
class Repository:
    """Immutable serialization, safe to share between Language instances.

    Build with ``from_definitions``, ``from_payload``, or ``load``. A structural
    verification is not semantic admission: ``audit`` performs the latter.
    """
    _json: str

    def __post_init__(self) -> None:
        payload = json.loads(self._json, object_pairs_hook=B.pairs_no_duplicates)
        if set(payload) != {'format', 'name', 'aliases', 'records', 'metadata', 'identity'}:
            raise RepositoryError('repository envelope fields')
        if payload['format'] != 'blue-python-repository/1':
            raise RepositoryError('unsupported repository format')
        if not isinstance(payload['name'], str) or not payload['name'].strip():
            raise RepositoryError('repository name must be nonempty')
        if not isinstance(payload['aliases'], dict) or not isinstance(payload['records'], dict):
            raise RepositoryError('aliases and records must be objects')
        if not isinstance(payload['metadata'], dict):
            raise RepositoryError('metadata must be an object')
        claimed = payload.pop('identity')
        if claimed != digest(payload):
            raise RepositoryError('repository integrity mismatch')
        for alias, tid in payload['aliases'].items():
            if not isinstance(alias, str) or not alias:
                raise RepositoryError('alias must be a nonempty string')
            B.final_id(tid)
            if alias in B.CORE and B.CORE[alias] != tid:
                raise RepositoryError('a repository cannot rebind a core alias')
            if tid not in payload['records'] and tid not in B.CORE_NAME:
                raise RepositoryError('alias has no supplied definition evidence: ' + alias)
        object.__setattr__(self, '_json', canonical({**payload, 'identity': claimed}))
        # Never accept a same-ID body merely because a file checksum matches.
        context = Language(MemoryProvider(payload['records']))._context()
        for tid in sorted(payload['records']):
            B.final_id(tid)
            try:
                B.open_exact(B.Ref(tid), context)
            except (B.Failure, RecursionError) as error:
                raise RepositoryError('invalid exact evidence for ' + tid + ': ' + str(error)) from error
            # Verification work is per record; large repositories are not one
            # unbounded semantic operation. Dependency admission stays separate.
            context.work = 0

    @classmethod
    def from_payload(cls, name: str, aliases: Mapping[str, str], records: Mapping[str, Any],
                     *, metadata: Mapping[str, Any] | None = None) -> 'Repository':
        payload = {'format': 'blue-python-repository/1', 'name': name,
                   'aliases': dict(aliases), 'records': dict(records), 'metadata': dict(metadata or {})}
        return cls(canonical({**payload, 'identity': digest(payload)}))

    @classmethod
    def from_definitions(cls, name: str, definitions: Mapping[str, Any], *,
                         dependencies: Iterable['Repository'] = ()) -> 'Repository':
        """Author named definitions in insertion order using earlier aliases.

        Bodies can be Python JSON values or YAML/JSON strings. Cyclic custom
        types can instead be finalized with Language.finalize and supplied to
        ``from_payload`` with their complete owning-set proofs.
        """
        language = Language(repositories=tuple(dependencies))
        aliases: dict[str, str] = {}
        for alias, value in definitions.items():
            if not isinstance(alias, str) or not alias or alias in language.aliases or alias in B.CORE:
                raise RepositoryError('duplicate or reserved alias: ' + str(alias))
            text, format = (value, 'yaml') if isinstance(value, str) else (canonical(value), 'json')
            document = language.admit_definition(text, format=format)
            language.publish_document(document)
            language.aliases[alias] = document.blue_id
            aliases[alias] = document.blue_id
        return cls.from_payload(name, aliases, language.provider.snapshot(),
                                metadata={'origin': 'python-authoring', 'languagePolicy': language._policy()})

    @classmethod
    def load(cls, path: str | Path) -> 'Repository':
        return cls(Path(path).read_text(encoding='utf-8'))

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(self._json + '\n', encoding='utf-8')

    @property
    def name(self) -> str:
        return json.loads(self._json)['name']

    @property
    def identity(self) -> str:
        return json.loads(self._json)['identity']

    @property
    def aliases(self) -> dict[str, str]:
        return json.loads(self._json)['aliases']

    @property
    def records(self) -> dict[str, Any]:
        return json.loads(self._json)['records']

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self._json)['metadata']

    def language(self, *, provider: MemoryProvider | None = None, **kwargs: Any) -> Language:
        return Language(provider, repositories=(self,), **kwargs)

    def audit(self, names: Iterable[str] | None = None) -> dict[str, Any]:
        """Strictly certify the definitions; report every result, not just counts.

        Uses one operation context for verified immutable dependencies, resetting
        work per root. Cached content is never accepted as semantic validation.
        """
        language = self.language()
        context = language._context()
        aliases = self.aliases
        rows = []
        for name in sorted(aliases if names is None else names):
            try:
                tid = aliases[name]
                context.work = 0
                B.strict_certify(B.Ref(tid), context, 'definition')
                rows.append({'name': name, 'blueId': tid, 'status': 'PASS'})
            except (B.Failure, RecursionError, KeyError) as error:
                rows.append({'name': name, 'status': 'FAIL', 'detail': str(error),
                             **({'diagnostic': error.as_dict()} if isinstance(error, B.Failure) else {})})
        return {'repository': self.identity, 'languagePolicy': language._policy(),
                'aliases': len(rows), 'passed': sum(x['status'] == 'PASS' for x in rows),
                'failed': sum(x['status'] != 'PASS' for x in rows), 'results': rows}
