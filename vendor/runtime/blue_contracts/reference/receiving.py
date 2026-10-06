"""Retained source completion delivery through the document-local kernel.

Capabilities are issued only for locally completed successful invocations. Data
received from another process is replayed before it can acquire that provenance.
A receiving invocation installs source state and batches before any receiver turn;
it never supplies external seeds or re-executes the source's business handlers.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from secrets import token_hex
from blue_host import HostIncomplete, HOST_FAILURES, incomplete, host_boundary
from algorithms import blue as L
from .model import require, digest
from .completion import Batch, vector
from .graph import Graph


@dataclass(frozen=True)
class SourceCompletion:
    _store: object
    _token: str

    @property
    def descriptor(self):
        return deepcopy(self._store.read(self)['descriptor'])


class CompletionStore:
    """Bounded, process-local provenance. A digest alone is never authority."""
    def __init__(self, capacity=128):
        self.capacity = capacity
        self._outcomes = OrderedDict()
        self._capabilities = OrderedDict()

    def remember(self, before, outcome, event, timestamp):
        self._outcomes[outcome.receipt] = (before.copy(), deepcopy(outcome), event, timestamp)
        while len(self._outcomes) > self.capacity:
            self._outcomes.popitem(last=False)

    def capture(self, outcome, members):
        record = self._outcomes.get(outcome.receipt)
        require(record is not None and record[1].observations() == outcome.observations(),
                'UNESTABLISHED_SOURCE_COMPLETION')
        before, result, event, timestamp = record
        members = frozenset(members)
        require(members and members <= result.snapshot.documents.keys(), 'INVALID_SOURCE_MEMBERS')
        require(members <= before.documents.keys(), 'SOURCE_BIRTH_REQUIRES_OWNER_COMMIT')
        # An existing cyclic execution unit is inseparable.
        for unit in result.units:
            owned = set(unit['members'])
            require(not owned.intersection(members) or owned <= members, 'PARTIAL_SOURCE_UNIT')
        descriptor = dict(receipt=result.receipt, before=vector(before, members),
                          after=vector(result.snapshot, members), members=sorted(members),
                          event=event, timestamp=timestamp, release=before.release,
                          runtimes=list(before.runtimes))
        descriptor['identity'] = digest('contracts.retained-completion/1', descriptor)
        token = token_hex(24)
        self._capabilities[token] = dict(descriptor=descriptor, before=before, outcome=result,
                                         event=event, timestamp=timestamp, members=members)
        while len(self._capabilities) > self.capacity:
            self._capabilities.popitem(last=False)
        return SourceCompletion(self, token)

    def read(self, capability):
        require(type(capability) is SourceCompletion and capability._store is self,
                'FOREIGN_SOURCE_COMPLETION')
        require(capability._token in self._capabilities, 'EXPIRED_SOURCE_COMPLETION')
        return self._capabilities[capability._token]


def begin_receiving(processor, snapshot, completions, *, live=False, evidence=None):
    try:
        attempt = _begin_receiving(processor, snapshot, completions, live=live, evidence=evidence)
    except HOST_FAILURES as error:raise incomplete(error) from error
    except Exception as error:
        processor.observe_execution('adoptionRejected', code=getattr(error, 'code', type(error).__name__))
        raise
    if attempt.outcome is not None and not attempt.outcome.commits:
        processor.observe_execution('adoptionRejected', code=attempt.outcome.status)
    return attempt


def _begin_receiving(processor, snapshot, completions, *, live=False, evidence=None):
    from .processor import Run
    from .chunks import Attempt
    require(type(completions) in (list, tuple) and completions, 'MISSING_SOURCE_COMPLETIONS')
    records = [processor._completion_store.read(c) for c in completions]
    require(len({r['descriptor']['identity'] for r in records}) == len(records), 'DUPLICATE_SOURCE_COMPLETION')
    causes = {(r['event'], r['timestamp']) for r in records}
    require(len(causes) == 1, 'MIXED_SOURCE_CAUSES')
    event, timestamp = next(iter(causes))
    owners = set()
    for record in records:
        require(not owners.intersection(record['members']), 'OVERLAPPING_SOURCE_COMPLETIONS')
        owners.update(record['members'])
        require(record['before'].release == snapshot.release and record['before'].runtimes == snapshot.runtimes,
                'INCOMPATIBLE_SOURCE_RUNTIME')
    require(snapshot.root not in owners, 'CYCLIC_RECEIVING_REQUIRES_ATOMIC_INVOCATION')

    class ReceivingRun(Run):
        def begin_work(self):
            self.meter.contracts('processInvocation')
            self.meter.contracts('closureInvocation')
            self.preflight()
            self.engine.validate(self.input)
            if live:
                # Freeze admission against the original receiver input, before
                # installing any completed child. Incoming handlers can then
                # retire a seed through the normal Contracts lifetime checks.
                from .runtime import prepare_admissions
                from .channels import recognize_call, select_seeds
                prepare_admissions(self)
                self.call, self.call_record = recognize_call(self.reg, self.event)
                self.seeds = tuple(s for s in select_seeds(self) if s.document not in owners)
            before_routes = {k: self.capture_routes(k) for k in owners}
            carried = {}
            for record in records:
                source_after = record['outcome'].snapshot
                pending = list(record['members'])
                closure = set()
                while pending:
                    member = pending.pop()
                    if member in closure:continue
                    closure.add(member)
                    pending.extend(e.target for e in source_after.edges.values() if e.source == member)
                require(self.input.root not in closure, 'CYCLIC_RECEIVING_REQUIRES_ATOMIC_INVOCATION')
                for member in closure - owners:
                    document = source_after.documents[member]
                    if member in carried:
                        require(carried[member].metadata() == document.metadata(), 'INCOMPATIBLE_SOURCE_DEPENDENCIES')
                    carried[member] = document
                    self.state.documents[member] = deepcopy(document)
                    for edge in list(self.state.edges):
                        if edge[0] == member:del self.state.edges[edge]
                    self.state.edges.update({k:deepcopy(e) for k,e in source_after.edges.items() if e.source == member})
            for record in records:
                source_before, source_after = record['before'], record['outcome'].snapshot
                for member in sorted(record['members']):
                    require(member in self.input.documents, 'MISSING_RECEIVING_SOURCE')
                    require(vector(self.input, [member]) == vector(source_before, [member]),
                            'SOURCE_PREDECESSOR_MISMATCH', member=member)
                    self.state.documents[member] = deepcopy(source_after.documents[member])
                    for edge in list(self.state.edges):
                        if edge[0] == member:
                            del self.state.edges[edge]
                    self.state.edges.update({k: deepcopy(e) for k, e in source_after.edges.items() if e.source == member})
                # Births cannot be installed as a detached fragment. Their
                # complete verified source owner outcome includes the birth.
                newborn = set(source_after.documents) - set(source_before.documents)
                for member in sorted(newborn):
                    require(member not in self.input.documents, 'CONFLICTING_MEMBER_BIRTH')
                    self.state.documents[member] = deepcopy(source_after.documents[member])
                self.state.edges.update({k: deepcopy(e) for k, e in source_after.edges.items() if e.source in newborn})
            self.graph = self.fork_graph(self.state)
            self.graph.refresh_aliases()
            completed_closure = owners | set(carried)
            if live:
                self.seeds = tuple(s for s in self.seeds if s.document not in completed_closure)
            # Containing references intentionally still name the selected
            # predecessor here. install_inputs updates them before the local
            # receiving turn; the complete outcome validates the resulting graph.
            self.phase = self.new_phase('PROCESS' if live else 'RECEIVE')
            for group in self.phase.groups:
                require(not group.intersection(owners) or group <= owners,
                        'CYCLIC_RECEIVING_REQUIRES_ATOMIC_INVOCATION')
                if group <= completed_closure:
                    self.phase.done.add(tuple(sorted(group)))
            for record in records:
                result = record['outcome']
                for member in sorted(record['members']):
                    turns = [t for t in result.completions if t['turnInput']['member'] == member]
                    # State-only steps still deliver an empty batch.
                    output = tuple(e for t in turns for e in t['output'])
                    batch = Batch(member, 0, record['descriptor']['identity'], output,
                                  before_routes[member], vector(self.state, [member]))
                    self.route_batch(self.phase, batch, owners, internal=False)
            self.engine.observe_execution('adoption', count=len(records), members=sorted(owners), live=live)

    run = ReceivingRun(processor, snapshot, L.Ref(event) if event else None, timestamp,
                       processor.gas_limit, admission=event is None, local_limits=processor.local_limits,
                       admission_evidence=evidence)
    run.receiving = True
    run.invocation = digest('contracts.receiving/1', dict(input=snapshot.identity,
        sources=[r['descriptor']['identity'] for r in records], policy=run.meter.policy()))
    run.graph.invocation = run.invocation
    return Attempt(run)
