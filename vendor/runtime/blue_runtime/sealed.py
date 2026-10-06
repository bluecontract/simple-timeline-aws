"""Sealed local results with one canonical receipt, outside the normative model.

The executable reference still constructs an ordinary mutable Outcome. Only its
private finalization path may seal it before it escapes. Encoded observations
and snapshot metadata are immutable bytes; accessors return detached values.
Foreign results are never granted a local execution capability by this module.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from copy import deepcopy
import hashlib
import json

from blue_contracts.reference import model, processor, receiving
from blue_language.physical import PhysicalCache

_ACTIVE = ContextVar('blue_sealed_results', default=None)
_POOL = ContextVar('blue_sealed_byte_pool',default=None)
_FINALIZING = ContextVar('blue_sealing_finalization', default=None)
_FINISH = processor.Run.finish_work
_REMEMBER = receiving.CompletionStore.remember

_FIELDS = {
    'status':'status', 'input_identity':'input', 'invocation':'invocation',
    'public_events':'publicEvents', 'event_trace':'events', 'work_trace':'work',
    'changes':'changes', 'checkpoints':'checkpoints', 'gas':'gas', 'gas_trace':'gasTrace',
    'rejected':'rejected', 'diagnostic':'diagnostic', 'completions':'completions',
    'rounds':'rounds', 'units':'units',
}


@dataclass(frozen=True, slots=True)
class SnapshotSeal:
    metadata: bytes
    bodies: tuple

    @classmethod
    def capture(cls, snapshot):
        proof = PhysicalCache(0)
        bodies = tuple((k, d.body) for k, d in sorted(snapshot.documents.items()))
        if not all(proof.shareable(body) for _, body in bodies):
            raise ValueError('Only immutable exact bodies can be shared')
        return cls(model.canonical(snapshot.wire()), bodies)

    def open(self):
        wire = json.loads(self.metadata); bodies = dict(self.bodies)
        docs = {d['key']: model.Document(d['key'], bodies[d['key']], d['blueId'],
            {k:model.ChannelLife(**v) for k,v in d['channels'].items()},
            d['channelSerials'], d['edgeSerials'], d['birth']) for d in wire['documents']}
        edges = [model.Edge(**row) for row in wire['edges']]
        return model.Snapshot(wire['root'], docs, {e.key:e for e in edges}, wire['generation'],
                              wire['revision'], wire['release'], tuple(wire['runtimes']))


class SealedOutcome(model.Outcome):
    """Public observations are copies; no same-length nested mutation is hidden."""
    def __init__(self, outcome):
        snapshot = SnapshotSeal.capture(outcome.snapshot)
        pool=_POOL.get()
        share=pool.intern if pool is not None else lambda b:b
        fields = tuple((k,share(model.canonical(v))) for k,v in sorted(outcome.observations().items()))
        encoded = b'{' + b','.join(model.canonical(k)+b':'+v for k,v in fields) + b'}'
        # Exactly canonical({'kind': DOMAIN, 'value': observations}); no new hash format.
        digest = hashlib.sha256(b'{"kind":"contracts.result/completion-1","value":'+encoded+b'}').hexdigest()
        object.__setattr__(self, '_sealed_snapshot', snapshot)
        object.__setattr__(self, '_sealed_fields', fields)
        object.__setattr__(self, '_sealed_receipt', 'sha256:'+digest)

    def __getattribute__(self, name):
        key = _FIELDS.get(name)
        if key is not None:
            for field, encoded in object.__getattribute__(self, '_sealed_fields'):
                if key == field: return json.loads(encoded)
        return super().__getattribute__(name)

    def __setattr__(self, name, value): raise TypeError('Sealed outcomes are immutable; open a working snapshot')
    def __delattr__(self, name): raise TypeError('Sealed outcomes are immutable')
    def __deepcopy__(self, memo): memo[id(self)] = self; return self
    @property
    def snapshot(self): return self._sealed_snapshot.open()
    @property
    def receipt(self): return self._sealed_receipt
    def observations(self): return {k:json.loads(v) for k,v in self._sealed_fields}


@contextmanager
def sealed_scope(metrics=None, *, enabled=True, pool=None):
    token = _ACTIVE.set(({} if metrics is None else metrics) if enabled else None)
    storage=_POOL.set(pool if enabled else None)
    try: yield
    finally: _ACTIVE.reset(token);_POOL.reset(storage)


def remember(store, before, outcome, event, timestamp):
    finalization = _FINALIZING.get()
    if _ACTIVE.get() is None or finalization is None:
        return _REMEMBER(store,before,outcome,event,timestamp)
    try: sealed = SealedOutcome(outcome)
    except ValueError: return _REMEMBER(store,before,outcome,event,timestamp)
    metrics = _ACTIVE.get(); metrics['receiptDigests'] = metrics.get('receiptDigests',0)+1
    # The reference remembers immediately before returning the private result.
    # No caller holds that mutable Outcome, so this is not an identity/length cache.
    finalization.append((outcome,sealed))
    store._outcomes[sealed.receipt] = (before.copy(), sealed, event, timestamp)
    while len(store._outcomes) > store.capacity: store._outcomes.popitem(last=False)


def finish_work(run):
    if _ACTIVE.get() is None: return _FINISH(run)
    captured = []; token = _FINALIZING.set(captured)
    try: result = _FINISH(run)
    finally: _FINALIZING.reset(token)
    return next((sealed for original,sealed in captured if original is result),result)


processor.Run.finish_work = finish_work
receiving.CompletionStore.remember = remember
