"""Indexed physical execution of the unchanged Contracts graph algorithms.

The reference remains independently runnable. These adapters are installed once,
but only dispatch inside an explicit context-local acceleration scope. Mutable
maps have local revisions; no identity, gas charge or semantic output is cached.
"""
from collections import OrderedDict, defaultdict
from collections.abc import ValuesView
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import heapq

from blue_contracts.reference import graph, completion
from blue_contracts.reference.model import require

_ACTIVE = ContextVar('blue_topology_acceleration', default=None)
_REFERENCE_REACHABLE = graph.Graph.reachable
_REFERENCE_COMPONENTS = graph.components
_REFERENCE_PROMOTE = completion.CompletionMachine.promote
_REFERENCE_NEXT = completion.CompletionMachine.next_unit


def count(name, amount=1):
    metrics = _ACTIVE.get()
    if metrics is not None: metrics[name] = metrics.get(name, 0) + amount


@contextmanager
def topology_scope(metrics=None, *, enabled=True):
    token = _ACTIVE.set(({} if metrics is None else metrics) if enabled else None)
    try: yield
    finally: _ACTIVE.reset(token)


class RevisionMap(dict):
    """Snapshot-owned map: edge changes or document membership advance revision.

    Documents remain mutable working values. Replacing a document at an existing
    key changes content/lifecycle, but not the structural membership index.
    """
    def __init__(self, values=(), *, membership=False):
        super().__init__(values); self.membership = membership; self.version = 0
        self.partitions = OrderedDict()

    def __setitem__(self, key, value):
        changed = key not in self or not self.membership and self[key] != value
        super().__setitem__(key, value)
        if changed: self.version += 1; self.partitions.clear()

    def __delitem__(self, key):
        super().__delitem__(key); self.version += 1; self.partitions.clear()

    def pop(self, key, *default):
        if key not in self:
            if default: return default[0]
            raise KeyError(key)
        value = self[key]; del self[key]; return value

    def popitem(self):
        if not self: raise KeyError('popitem(): dictionary is empty')
        key = next(reversed(self)); return key, self.pop(key)

    def clear(self):
        if self: super().clear(); self.version += 1; self.partitions.clear()

    def update(self, values=(), **kwargs):
        for key, value in dict(values, **kwargs).items(): self[key] = value

    def setdefault(self, key, default=None):
        if key not in self: self[key] = default
        return self[key]

    def __ior__(self, values): self.update(values); return self
    def values(self): return ValuesView(self)

    def __deepcopy__(self, memo):
        result = RevisionMap(membership=self.membership); memo[id(self)] = result
        for k, v in self.items(): dict.__setitem__(result, deepcopy(k, memo), deepcopy(v, memo))
        # A restored/copied working snapshot starts a distinct physical index.
        return result


class Changes(set):
    def __init__(self, values=()): super().__init__(values); self.changes = []
    def add(self, value):
        if value not in self: super().add(value); self.changes.append((value, True))
    def discard(self, value):
        if value in self: super().discard(value); self.changes.append((value, False))
    def remove(self, value):
        if value not in self: raise KeyError(value)
        self.discard(value)
    def difference_update(self, values):
        for value in tuple(values): self.discard(value)
    def update(self, values):
        for value in values: self.add(value)
    def clear(self): self.difference_update(tuple(self))
    def __deepcopy__(self, memo):
        result = Changes(self); memo[id(self)] = result; return result


class Topology:
    def __init__(self, state):
        self.edges, self.documents, self.root = state.edges, state.documents, state.root
        self.revision = (state.edges.version, state.documents.version)
        self.forward = defaultdict(list); self.reverse = defaultdict(list)
        for _, edge in sorted(state.edges.items(), reverse=True):
            self.forward[edge.source].append(edge); self.reverse[edge.target].append(edge)
            count('topologyIndexEdgeVisits')
        self.live = self.reachable(state.root)
        count('topologyIndexBuilds')

    def __deepcopy__(self, memo):
        # Derived indexes never travel across a cloned working snapshot.
        return None

    def reachable(self, root):
        seen = set(); pending = [root]
        while pending:
            member = pending.pop()
            if member in seen: continue
            seen.add(member)
            outgoing = self.forward.get(member, ())
            count('reachabilityEdgeVisits', len(outgoing))
            pending.extend(e.target for e in outgoing)
        return frozenset(seen)

    def matches(self, state):
        return (self.edges is state.edges and self.documents is state.documents and self.root == state.root
                and self.revision == (state.edges.version, state.documents.version))


def topology(g):
    state = g.state
    if not isinstance(state.edges, RevisionMap): state.edges = RevisionMap(state.edges)
    if not isinstance(state.documents, RevisionMap): state.documents = RevisionMap(state.documents, membership=True)
    index = getattr(g, '_physical_topology', None)
    if index is None or not index.matches(state):
        index = g._physical_topology = Topology(state)
    return index


def reachable(g, *, active=False, terminating=frozenset()):
    if _ACTIVE.get() is None: return _REFERENCE_REACHABLE(g, active=active, terminating=terminating)
    index = topology(g)
    if not active: return set(index.live)
    # Eligibility is deliberately re-observed, in the reference traversal order.
    # A changed termination marker cannot be hidden by a structural cache hit.
    seen = set(); pending = [g.state.root]
    while pending:
        member = pending.pop()
        if member in seen or member in terminating or g.terminated(member): continue
        seen.add(member)
        outgoing = index.forward.get(member, ())
        count('activeReachabilityEdgeVisits', len(outgoing))
        pending.extend(e.target for e in outgoing)
    return seen


def components(vertices, edges):
    if _ACTIVE.get() is None: return _REFERENCE_COMPONENTS(vertices, edges)
    owner_map = edges._mapping if isinstance(edges, ValuesView) else None
    key = frozenset(vertices)
    if isinstance(owner_map, RevisionMap) and key in owner_map.partitions:
        count('sccCacheHits'); owner_map.partitions.move_to_end(key)
        return list(owner_map.partitions[key])
    count('sccBuilds')
    vs = sorted(key); outgoing = {v: set() for v in vs}; reverse = {v: set() for v in vs}
    for edge in edges:
        count('sccEdgeVisits')
        if edge.source in outgoing and edge.target in outgoing:
            outgoing[edge.source].add(edge.target); reverse[edge.target].add(edge.source)
    seen = set(); finish = []
    for start in vs:
        if start in seen: continue
        stack = [(start, False)]
        while stack:
            member, leaving = stack.pop()
            if leaving: finish.append(member); continue
            if member in seen: continue
            seen.add(member); stack.append((member, True))
            stack.extend((v, False) for v in sorted(outgoing[member], reverse=True) if v not in seen)
    seen = set(); groups = []
    for start in reversed(finish):
        if start in seen: continue
        group = []; stack = [start]
        while stack:
            member = stack.pop()
            if member in seen: continue
            seen.add(member); group.append(member); stack.extend(sorted(reverse[member] - seen, reverse=True))
        groups.append(tuple(sorted(group)))
    owner = {v: g for g in groups for v in g}
    deps = {g: {owner[w] for v in g for w in outgoing[v] if owner[w] != g} for g in groups}
    dependents = defaultdict(list)
    for g, values in deps.items():
        for d in values: dependents[d].append(g)
    remaining = {g: len(values) for g, values in deps.items()}
    ready = [g for g in groups if not remaining[g]]; heapq.heapify(ready); result = []
    while ready:
        group = heapq.heappop(ready); result.append(group); count('condensationQueuePops')
        for dependent in dependents[group]:
            remaining[dependent] -= 1
            if not remaining[dependent]: heapq.heappush(ready, dependent)
    require(len(result) == len(groups), 'INTERNAL_COMPONENT_ORDER')
    if isinstance(owner_map, RevisionMap):
        owner_map.partitions[key] = tuple(result)
        while len(owner_map.partitions) > 8: owner_map.partitions.popitem(last=False)
    return result


class Schedule:
    def __init__(self, machine, phase, index):
        self.index = index
        if not isinstance(phase.done, Changes): phase.done = Changes(phase.done)
        if not phase.barrier: phase.allowed.update(index.live)
        owner = {k: i for i, group in enumerate(phase.groups) for k in group}
        for member in sorted(phase.allowed - owner.keys()):
            owner[member] = len(phase.groups); phase.groups.append({member})
        # Reconcile SCCs with monotonic execution groups using direct ownership.
        # SCCs may split; execution units in this phase only merge.
        for component in components(phase.allowed, machine.state.edges.values()):
            touched = {owner[k] for k in component}; count('promotionMemberVisits', len(component))
            if len(touched) > 1:
                union = set().union(*(phase.groups[i] for i in touched))
                phase.done.difference_update(tuple(sorted(phase.groups[i])) for i in touched)
                for i in touched: phase.groups[i] = set()
                # Append, exactly as the reference's remove + append ordering.
                position = len(phase.groups); phase.groups.append(union)
                for k in union: owner[k] = position
        phase.groups = [g for g in phase.groups if g]
        self.owner = {k: tuple(sorted(g)) for g in phase.groups for k in g}
        self.positions = {tuple(sorted(g)): i for i, g in enumerate(phase.groups)}
        self.groups = {tuple(sorted(g)): g for g in phase.groups}
        self.deps = {identity: set() for identity in self.groups}
        self.reverse = defaultdict(set)
        for edge in machine.state.edges.values():
            count('scheduleEdgeVisits')
            source, target = self.owner.get(edge.source), self.owner.get(edge.target)
            if source is not None and target is not None and source != target: self.deps[source].add(target)
        for source, targets in self.deps.items():
            for target in targets: self.reverse[target].add(source)
        if not phase.barrier:
            for identity, group in self.groups.items():
                if not group.intersection(index.live): phase.done.add(identity)
        self.remaining = {g: len(values - phase.done) for g, values in self.deps.items()}
        self.ready = []; self.queued = set(); self.pending = set(self.groups) - phase.done
        phase.done.changes.clear()
        for g in self.pending: self.enqueue(g)
        count('scheduleBuilds')

    def __deepcopy__(self, memo):
        return None  # A chunk clone rebuilds from its own graph and phase.done.

    def enqueue(self, identity):
        if identity in self.pending and not self.remaining[identity] and identity not in self.queued:
            heapq.heappush(self.ready, identity); self.queued.add(identity); count('readyQueuePushes')

    def sync_done(self, phase):
        changes, phase.done.changes = phase.done.changes, []
        for identity, done in changes:
            if identity not in self.groups: continue
            if done: self.pending.discard(identity)
            else: self.pending.add(identity)
            for dependent in self.reverse[identity]:
                self.remaining[dependent] += -1 if done else 1
                self.enqueue(dependent); count('dependencyUpdates')
            self.enqueue(identity)

    def select(self, phase):
        self.sync_done(phase)
        while self.ready:
            identity = self.ready[0]
            if identity in self.pending and not self.remaining[identity]: return set(identity)
            heapq.heappop(self.ready); self.queued.discard(identity); count('readyQueuePops')
        require(not self.pending, 'UNSEALED_DEPENDENCY')
        return None


def schedule(machine, phase):
    index = topology(machine.graph)
    cached = getattr(phase, '_physical_schedule', None)
    if cached is None or cached.index is not index:
        cached = phase._physical_schedule = Schedule(machine, phase, index)
    return cached


def promote(machine, phase, members):
    if _ACTIVE.get() is None: return _REFERENCE_PROMOTE(machine, phase, members)
    plan = schedule(machine, phase)
    identities = {plan.owner[k] for k in members if k in plan.owner}
    if not identities: return set(members)
    return plan.groups[min(identities, key=plan.positions.__getitem__)]


def next_unit(machine, phase):
    if _ACTIVE.get() is None: return _REFERENCE_NEXT(machine, phase)
    return schedule(machine, phase).select(phase)


def install():
    # Every call without the explicit scope is the unchanged executable reference.
    graph.Graph.reachable = reachable
    graph.components = completion.components = components
    completion.CompletionMachine.promote = promote
    completion.CompletionMachine.next_unit = next_unit
    from blue_contracts.reference import processor
    processor.components = components


install()
