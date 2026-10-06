"""Pure managed-occurrence delta planning, not managed-document admission.

This planner is deliberately separate from ClosureHost: a caller must prove
child admission/history, initialize new children, and atomically publish the
result. Planning never grants authority, resets history, or commits a graph.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from blue_bex.values import segments

class TopologyError(ValueError): pass

def _ordered(values):
    return sorted(values, key=lambda s:s.encode('utf-16-be','surrogatepass'))

def _validate_path(path):
    if not isinstance(path,str) or not path.startswith('/') or path=='/':
        raise TopologyError('managed occurrence must be below the selected root')
    try:parts=segments(path)
    except Exception as error:raise TopologyError('invalid occurrence pointer') from error
    if not parts:raise TopologyError('empty occurrence path')
    if parts[0]=='contracts':raise TopologyError('contract metadata cannot be a managed occurrence')
    return tuple(parts)

@dataclass(frozen=True)
class Occurrence:
    path: str
    target: str
    generation: int

@dataclass(frozen=True)
class Edit:
    kind: str
    before: Occurrence | None
    after: Occurrence | None

@dataclass(frozen=True)
class TopologyState:
    live: tuple[Occurrence,...] = ()
    # Retain generation tombstones when an occurrence disappears.
    generations: tuple[tuple[str,int],...] = ()

    def __post_init__(self):
        live={x.path:x for x in self.live};generations=dict(self.generations)
        if len(live)!=len(self.live) or len(generations)!=len(self.generations):
            raise TopologyError('duplicate occurrence or generation')
        for path,generation in generations.items():
            _validate_path(path)
            if type(generation) is not int or generation<0:raise TopologyError('invalid generation')
        for path,item in live.items():
            _validate_path(path)
            if not isinstance(item.target,str) or not item.target:raise TopologyError('empty target')
            if type(item.generation) is not int or item.generation<0:raise TopologyError('invalid generation')
            if generations.get(path)!=item.generation:raise TopologyError('generation ledger mismatch')
        _validate_nonoverlap(live)

@dataclass(frozen=True)
class TopologyPlan:
    before: TopologyState
    after: TopologyState
    edits: tuple[Edit,...]


def _validate_nonoverlap(paths):
    parsed={p:_validate_path(p) for p in paths}
    rows=list(parsed.items())
    for i,(p,a) in enumerate(rows):
        for q,b in rows[i+1:]:
            if a[:len(b)]==b or b[:len(a)]==a:
                raise TopologyError('overlapping direct managed occurrences: '+p+' and '+q)


def plan_topology(before: TopologyState, requested: Mapping[str,str]) -> TopologyPlan:
    if not isinstance(before,TopologyState):raise TypeError('expected verified TopologyState')
    targets=dict(requested);_validate_nonoverlap(targets)
    if any(not isinstance(t,str) or not t for t in targets.values()):raise TopologyError('empty target')
    old={x.path:x for x in before.live};ledger=dict(before.generations);live=[];edits=[]
    for path in _ordered(set(old)|set(targets)):
        prior=old.get(path);target=targets.get(path)
        if target is None:
            edits.append(Edit('remove',prior,None));continue
        if prior is not None and prior.target==target:
            live.append(prior);continue
        generation=ledger.get(path,-1)+1
        item=Occurrence(path,target,generation);ledger[path]=generation;live.append(item)
        edits.append(Edit('add' if prior is None else 'rebind',prior,item))
    after=TopologyState(tuple(live),tuple((p,ledger[p]) for p in _ordered(ledger)))
    return TopologyPlan(before,after,tuple(edits))
