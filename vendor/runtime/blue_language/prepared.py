"""Optional consumer for blue-prepared-repository/1 (data, never executable code).

This SDK adapter leaves the reference algorithms and their semantic policy
unchanged. It replays successful structural preparation under matching limits;
semantic validation always runs in a fresh context. See PREPARED_REPOSITORIES.md.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import secrets
from pathlib import Path
import weakref

from algorithms import blue as B
from .api import Language, AdmittedDocument

FORMAT = 'blue-prepared-repository/1'
DEFAULT_LIMITS = asdict(B.Limits())
_identity = B.identity
_open = B.open_exact
_export = B.export_exact
_identities = {}


def binding():
    """Artifact ABI plus exact selected Language validation policy."""
    return {'format': FORMAT, 'policy': Language._policy(), 'adapter': 1}


def _freeze(value):
    if isinstance(value, list): return tuple(_freeze(v) for v in value)
    if isinstance(value, dict): return tuple((k, _freeze(v)) for k, v in value.items())
    return value


def _register(node, tid):
    key = id(node)
    def remove(ref):
        if _identities.get(key, (None,))[0] is ref: _identities.pop(key, None)
    _identities[key] = (weakref.ref(node, remove), tid)


def _prepared_identity(node, token=None):
    if token is None:
        entry = _identities.get(id(node))
        if entry is not None and entry[0]() is node: return entry[1]
    return _identity(node, token)


def _matching_limits(c):
    return all(getattr(c.limits, k) == v for k, v in DEFAULT_LIMITS.items()
               if k not in ('steps', 'fetches'))


class PreparedRepository:
    """A trusted preparation artifact, not an admission ticket or runtime.

    ``expected_sha256`` must come from the caller's trusted build/release, not
    from a digest inside the same untrusted artifact. Arbitrary repositories
    must first go through the standalone builder's structural verification.
    """
    def __init__(self, data: bytes, *, expected_sha256: str):
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256: raise ValueError('prepared repository digest mismatch')
        raw = json.loads(data)
        if raw['binding'] != binding(): raise ValueError('prepared repository policy/format mismatch; rebuild it')
        self._source = raw['repository']
        self._rows = raw['nodes']
        self._nodes = []
        self._by_shape = {}
        for i, row in enumerate(self._rows):
            node = B.Node(tuple((k, self._decode(v)) for k, v in row['fields']))
            self._nodes.append(node)
            self._by_shape[_freeze(row['fields'])] = i
            _register(node, row['blueId'])
        self._by_object = {id(n): i for i, n in enumerate(self._nodes)}
        self._opens = raw['opens']
        self.artifact_sha256 = actual

    @classmethod
    def load(cls, path, *, expected_sha256):
        return cls(Path(path).read_bytes(), expected_sha256=expected_sha256)

    def _decode(self, value):
        tag, arg = value
        if tag == 'node': return self._nodes[arg]
        if tag == 'ref': return B.Ref(arg)
        if tag == 'tuple': return tuple(self._decode(v) for v in arg)
        if tag == 'int': return int(arg)
        if tag == 'float': return float(arg)
        if tag == 'literal': return arg
        raise ValueError('unknown prepared node tag')

    def _encode(self, value):
        if type(value) is B.Node:
            index = self._by_object.get(id(value))
            if index is None: raise KeyError('new node')
            return ('node', index)
        if type(value) is B.Ref: return ('ref', value.id)
        if type(value) is tuple: return ('tuple', tuple(self._encode(v) for v in value))
        if type(value) is int: return ('int', str(value))
        if type(value) is float: return ('float', repr(value))
        if type(value) in (str, bool, type(None)): return ('literal', value)
        raise KeyError('not immutable prepared data')

    def _row(self, node):
        index = self._by_object.get(id(node))
        if index is None:
            if type(node) is not B.Node or type(node.fields) is not tuple: return None
            try: index = self._by_shape.get(tuple((k, self._encode(v)) for k, v in node.fields))
            except KeyError: return None
        return self._rows[index] if index is not None else None

    @property
    def name(self): return self._source['name']
    @property
    def identity(self): return self._source['identity']
    @property
    def aliases(self): return dict(self._source['aliases'])
    @property
    def records(self): return json.loads(json.dumps(self._source['records']))
    @property
    def metadata(self): return json.loads(json.dumps(self._source['metadata']))

    def language(self, *, provider=None, **kwargs):
        return PreparedLanguage(provider, repositories=(self,), **kwargs)


def _prepared_open(node, c):
    bundles = getattr(c, '_prepared_repositories', ())
    if (bundles and type(node) is B.Ref and node.body is None and node.id not in c.bodies
            and '#' not in node.id and _matching_limits(c)):
        for bundle in bundles:
            for row in bundle._opens.get(node.id, ()):
                # Provider overrides and missing/partial evidence never inherit
                # trust from a repository with the same claimed identity.
                if c.provider.get(node.id) != row['response']: continue
                cost = row['steps']
                if not B.within(c.work + cost,c.limits.steps): return _open(node, c)
                c.step()
                B.final_id(node.id)
                B.require(B.within(len(c.demands)+1,c.limits.fetches), 'OperationLimitExceeded', 'provider count')
                c.demands.append(node.id)
                # Exact reference work and remember order are replayed. At a
                # rejection boundary use the reference for its precise path.
                c.work += cost - 1
                for tid, index in row['remember']: c.bodies[tid] = bundle._nodes[index]
                return bundle._nodes[row['body']]
    return _open(node, c)


def _prepared_export(node, c=None):
    if c is not None and _matching_limits(c):
        for bundle in getattr(c, '_prepared_repositories', ()):
            row = bundle._row(node)
            if row is not None and B.within(row['exportSteps'],c.limits.steps):
                for index in row['remember']: c.remember(bundle._nodes[index])
                return row['exact']
    return _export(node, c)


B.identity = _prepared_identity
B.open_exact = _prepared_open
B.export_exact = _prepared_export


@dataclass(frozen=True)
class PreparedDocument(AdmittedDocument):
    """An issued handle sharing immutable export strings with its repository."""
    _record_items: tuple

    def dependency_responses(self):
        return {tid: dict(items) for tid, items in self._record_items}


class PreparedLanguage(Language):
    """Reference Language API with an optional prepared repository provider.

    Counters, plans, semantic validation and diagnostics remain per invocation.
    The shared bundle contains only immutable structural preparation.
    """
    def enable_repository(self, repository, *, aliases=True):
        if not isinstance(repository, PreparedRepository):
            if not aliases: raise TypeError('content-only mounts require a prepared repository')
            return super().enable_repository(repository)
        name, identity = repository.name, repository.identity
        aliases, records = repository.aliases if aliases else {}, repository.records
        old = self._repositories.get(name)
        if old is not None:
            if old['identity'] == identity and old['aliases'] == aliases: return
            raise ValueError('different repository already enabled under ' + name)
        for alias, tid in aliases.items():
            existing = B.CORE.get(alias, self.aliases.get(alias))
            if existing is not None and existing != tid: raise ValueError('alias conflict: ' + alias)
        current = self.provider.snapshot()
        for mounted in self._repositories.values(): current.update(mounted['records'])
        for tid, response in records.items():
            if tid in current and current[tid] != response:
                context = B.initialize(self._registry, {tid: current[tid]}, limits=self.limits)
                B.open_exact(B.Ref(tid), context)
        for alias, tid in aliases.items():
            if alias not in self._repository_base_aliases: self._repository_base_aliases[alias] = self.aliases.get(alias)
            self.aliases[alias] = tid
        self._repositories[name] = {'identity': identity, 'aliases': aliases, 'records': records, 'prepared': repository}

    def processing_context(self):
        c = super().processing_context()
        c._prepared_repositories = tuple(m['prepared'] for m in self._repositories.values() if 'prepared' in m)
        return c

    def _run(self, fn):
        from .physical import PhysicalCache
        with PhysicalCache().scope():
            return super()._run(fn)

    def _issue(self, payload):
        records = payload['records']
        if not all(type(row) is dict and all(type(k) is str and type(v) is str for k, v in row.items())
                   for row in records.values()):
            return super()._issue(payload)
        # No JSON roundtrip or duplicate dependency strings for an in-process
        # handle. Public publication/export still materializes the same records.
        ticket = secrets.token_hex(32)
        doc = PreparedDocument(payload['blueId'], payload['exactText'], payload['canonicalText'],
            payload['goal'], payload['policy'], payload['originalBlueId'], tuple(payload['removedFields']),
            '', ticket, tuple((tid, tuple(sorted(row.items()))) for tid, row in sorted(records.items())))
        fields = tuple(getattr(doc, key) for key in doc.__dataclass_fields__)
        self._issued[ticket] = (doc, fields)
        return doc

    def _check_handle(self, doc, goal=None):
        if not isinstance(doc, PreparedDocument): return super()._check_handle(doc, goal)
        entry = self._issued.get(doc._ticket)
        B.require(entry is not None and entry[0] is doc and
                  entry[1] == tuple(getattr(doc, key) for key in doc.__dataclass_fields__),
                  'InvalidValidationEvidence', 'handle was not issued by this instance or was changed')
        B.require(doc.policy == self._policy(), 'InvalidValidationEvidence', 'policy changed')
        B.require(goal is None or doc.goal == goal, 'InvalidValidationEvidence', 'validation role mismatch')
        self.last_demands = ()
        return doc
