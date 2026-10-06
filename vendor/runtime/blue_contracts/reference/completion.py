"""Document-local turns and dependency-unit scheduling (completion-1 A01–A10).

Only owned results cross a frame boundary. Exact Blue references pin all reads;
no callback can look up another member's mutable frame. Cyclic turns read a
single preceding round, and Language seals the merged owned changes together.
"""
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from algorithms import blue as L
from .model import require, integer, digest, canonical, LIMITS, trampoline
from .graph import Graph, components
from .channels import refresh_lifetimes


def committed(domain, row):
    return {**row, 'identity': digest('contracts.' + domain + '/completion-1', row)}


def vector(state, members):
    return {k: {'document': state.documents[k].metadata(),
                'edges': [e.wire() for e in sorted(state.edges.values(), key=lambda e:(e.source, e.path)) if e.source == k]}
            for k in sorted(members)}


@dataclass(frozen=True)
class Ticket:
    parent: str
    parentActivation: int
    path: str
    source: str
    sourceActivation: int
    generation: int

    def wire(self):
        return asdict(self)


@dataclass
class Batch:
    source: str
    serial: int
    completion: str
    output: tuple
    tickets: tuple
    after: dict
    round_seal: str | None = None


@dataclass
class Frame:
    key: str
    before: object
    input: dict
    source_turn: str
    queue: deque = field(default_factory=deque)
    output: list = field(default_factory=list)
    ticket: Ticket | None = None
    consumed: list = field(default_factory=list)
    writer: dict | None = None
    writes: list = field(default_factory=list)


@dataclass
class Phase:
    name: str
    allowed: set
    groups: list
    initial_routes: dict
    initialization: dict
    seeds: dict
    pending: dict = field(default_factory=lambda: defaultdict(list))
    done: set = field(default_factory=set)
    held: list = field(default_factory=list)
    outside: list = field(default_factory=list)
    barrier: bool = False


class CompletionMachine:
    def setup_completion(self):
        self.frame = None
        self.phase = None
        self.serials = defaultdict(int)
        self.turns = []
        self.rounds = []
        self.units = []
        self.routed = set()
        self.consumed_observations = set()
        self.turn_count = 0
        self.round_count = 0
        self.allocation = 0
        self.changes = []
        self.topology_changed = False
        self.suspended = []

    def fork_graph(self, state):
        old = self.graph
        graph = Graph(state, self.reg, old.archive, self.meter, self.invocation)
        graph.logical = old.logical
        graph.path_headers = old.path_headers
        graph.verified_bindings = old.verified_bindings
        graph.resets = old.resets
        graph.allocation = self.allocation
        graph.changes = self.changes
        return graph

    def capture_routes(self, source, state=None):
        from .model import segments
        state = self.state if state is None else state
        rows = []
        for edge in sorted(state.edges.values(), key=lambda e:(e.source, segments(e.path), e.generation)):
            if edge.target == source:
                rows.append(Ticket(edge.source, self.activation.get(edge.source, 0), edge.path,
                                   source, self.activation.get(source, 0), edge.generation))
        return tuple(rows)

    def ticket_live(self, ticket, *, charge=False):
        if charge:
            self.meter.owner = ticket.parent
            self.meter.contracts('completionRouteChecked')
        edge = self.state.edges.get((ticket.parent, ticket.path))
        return (edge is not None and edge.target == ticket.source and edge.generation == ticket.generation
                and self.activation.get(ticket.parent, 0) == ticket.parentActivation
                and self.activation.get(ticket.source, 0) == ticket.sourceActivation)

    def continuation_live(self, key, generation, allow_terminating=False):
        if self.frame is not None and self.frame.ticket is not None:
            if not self.ticket_live(self.frame.ticket, charge=True):
                return False
        return allow_terminating or self.live(key) and self.activation.get(key, 0) == generation

    def live(self, key):
        if self.frame is not None and key == self.frame.key:
            return key not in self.terminating and not self.graph.terminated(key)
        return key in self.graph.reachable(active=True, terminating=self.terminating)

    def new_phase(self, name, *, allowed=None, barrier=False):
        self.graph.observe_partition()
        allowed = set(self.graph.reachable() if allowed is None else allowed)
        active=self.graph.reachable(active=True)
        captures = {k: self.state.documents[k].blue_id for k in sorted(allowed)
                    if self.reg.marker(self.state.documents[k].body, 'initialized') is None
                    and k not in self.initializing and (barrier or k in active)}
        if name != 'INITIALIZE':
            captures = {}
        self.initialized.update(captures)
        return Phase(name, allowed, [set(g) for g in components(allowed, self.state.edges.values())],
                     {k: self.capture_routes(k) for k in allowed}, captures,
                     {k: [s for s in self.seeds if s.document == k] for k in allowed}
                     if name == 'PROCESS' else {}, barrier=barrier)

    def drive_phase(self, name, *, allowed=None, barrier=False):
        previous = self.phase
        phase = self.new_phase(name, allowed=allowed, barrier=barrier)
        self.phase = phase
        try:
            while self.next_unit(phase) is not None:
                self.run_unit(phase, self.next_unit(phase))
            return phase.outside
        finally:
            self.phase = previous

    def promote(self, phase, members):
        # Execution units only merge. Actual Language SCCs can still split.
        if not phase.barrier:
            phase.allowed.update(self.graph.reachable())
        known = set().union(*phase.groups) if phase.groups else set()
        phase.groups.extend({k} for k in sorted(phase.allowed - known))
        for component in components(phase.allowed, self.state.edges.values()):
            touched = [g for g in phase.groups if g.intersection(component)]
            if len(touched) > 1:
                union = set().union(*touched)
                phase.groups = [g for g in phase.groups if g not in touched] + [union]
                phase.done.difference_update(tuple(sorted(g)) for g in touched)
        return next((g for g in phase.groups if g.intersection(members)), set(members))

    def next_unit(self, phase):
        self.promote(phase, set())
        active = self.graph.reachable()
        ready = []
        owner = {k: tuple(sorted(g)) for g in phase.groups for k in g}
        for group in phase.groups:
            identity = tuple(sorted(group))
            if identity in phase.done:
                continue
            if not phase.barrier and not group.intersection(active):
                phase.done.add(identity)
                continue
            dependencies = {owner[e.target] for e in self.state.edges.values()
                            if e.source in group and e.target in owner and e.target not in group}
            if dependencies <= phase.done:
                ready.append(identity)
        if ready:
            return set(min(ready))
        require(all(tuple(sorted(g)) in phase.done for g in phase.groups), 'UNSEALED_DEPENDENCY')
        return None

    def has_inputs(self, phase, key):
        return bool(phase.pending[key] or key in phase.initialization or phase.seeds.get(key))

    def run_unit(self, phase, members):
        start = len(self.meter.trace)
        before = vector(self.state, members)
        turn_start = len(self.turns)
        while True:
            members = self.promote(phase, members)
            inputs = [k for k in sorted(members) if self.has_inputs(phase, k)]
            if not inputs:
                break
            cyclic = len(members) > 1 or any(e.source == e.target and e.source in members for e in self.state.edges.values())
            if cyclic:
                self.round_count += 1
                self.meter.owner = ''
                self.meter.contracts('componentRoundOpened')
            preceding = self.state.copy()
            results = []
            for key in inputs:
                incoming = phase.pending.pop(key, [])
                lifecycle = phase.initialization.pop(key, None)
                seeds = phase.seeds.pop(key, [])
                routes = (phase.initial_routes.get(key, self.capture_routes(key))
                          if not any(t['turnInput']['member'] == key and t['turnInput']['phase'] == phase.name for t in self.turns)
                          else self.capture_routes(key, preceding))
                result = self.run_local(preceding, key, incoming, lifecycle, seeds, phase.name, routes)
                results.append(result)
            for result in results:
                self.merge_owned(result)
            previous_reachable=Graph(preceding,self.reg,self.graph.archive).reachable()
            for key in previous_reachable ^ self.graph.reachable():
                self.activation[key]=self.activation.get(key,0)+1
            members = self.promote(phase, members)
            self.graph.dirty.update(r['key'] for r in results)
            self.graph.finalize(members=members)
            self.preflight(members=members)
            round_seal = None
            if cyclic or len(members) > 1:
                round_seal = committed('round-result', {
                    'beforeViews': vector(preceding, set(members) & set(preceding.documents)),
                    'afterViews': vector(self.state, members), 'ordinal': len(self.rounds),
                    'turns': [r['completion']['identity'] for r in results],
                    'members': vector(self.state, members),
                    'bindings': [e.wire() for e in sorted(self.state.edges.values(), key=lambda e:e.key) if e.source in members]})
                self.rounds.append(round_seal)
            for result in results:
                completion = result['completion']
                batch = Batch(result['key'], completion['turnInput']['turnSerial'], completion['identity'],
                              tuple(completion['output']), result['routes'], vector(self.state, [result['key']]),
                              round_seal['identity'] if round_seal else None)
                phase.held.append(batch)
            for batch in phase.held:
                self.route_batch(phase, batch, members, internal=True)
            # A join can introduce an as-yet unprocessed external dependency.
            owner = {k: tuple(sorted(g)) for g in phase.groups for k in g}
            dependencies = {owner[e.target] for e in self.state.edges.values()
                            if e.source in members and e.target in owner and e.target not in members}
            if not dependencies <= phase.done:
                return
        identity = tuple(sorted(members))
        phase.done.add(identity)
        output = []
        for batch in phase.held:
            if batch.source not in members:
                continue
            batch.after = vector(self.state, [batch.source])
            self.route_batch(phase, batch, members, internal=False)
            output.append({'source': batch.source, 'completion': batch.completion, 'output': list(batch.output)})
        self.units.append(committed('unit-result', {
            'members': list(identity), 'beforeViews': before, 'afterViews': vector(self.state, members),
            'turnResults': [t['identity'] for t in self.turns[turn_start:]], 'output': output,
            'workSegment': self.relative_segment(start)}))

    def route_batch(self, phase, batch, members, *, internal):
        grouped = defaultdict(list)
        for ticket in batch.tickets:
            if (ticket.parent in members) != internal:
                continue
            # Pure cyclic identity refresh never schedules an empty round.
            if internal and not batch.output:
                continue
            identity = (batch.completion, digest('ticket', ticket.wire()))
            if identity in self.routed:
                continue
            self.routed.add(identity)
            grouped[ticket.parent].append(ticket)
        for parent, tickets in sorted(grouped.items()):
            selected = Batch(batch.source, batch.serial, batch.completion, batch.output, tuple(tickets),
                             deepcopy(batch.after), batch.round_seal if internal else None)
            if parent in phase.allowed:
                phase.pending[parent].append(selected)
                phase.done.discard(next((tuple(sorted(g)) for g in phase.groups if parent in g), (parent,)))
            else:
                phase.outside.append(selected)

    def relative_segment(self, start):
        return [{**row, 'ordinal': i} for i, row in enumerate(self.meter.trace[start:])]

    def install_inputs(self, key, incoming):
        from .model import segments
        # State is the already sealed coherent dependency inventory. In a cycle
        # this is the previous round, never the isolated source local after-view.
        previous = self.state.documents[key].body
        replacements = []
        for edge in sorted(self.state.edges.values(), key=lambda e:(e.source, segments(e.path))):
            if edge.source != key:
                continue
            node = self.blue.exact(self.blue.select(previous, edge.path))
            target = self.state.documents[edge.target].blue_id
            if self.blue.identity(node) != target:
                self.meter.owner = key
                self.meter.contracts('containingReferenceUpdated')
                replacements.append((edge.path, L.Ref(target)))
        # These paths are disjoint. No handler observes a partially installed
        # dependency inventory, so establish its one completed candidate.
        if replacements:
            candidate = self.blue.substitute(previous, replacements)
            self.graph.logical.establish(candidate, previous)
            self.state.documents[key].body = candidate
        self.graph.finalize_local(key)
        for batch in sorted(incoming, key=lambda b:(b.source, b.serial)):
            self.meter.owner = key
            self.meter.contracts('completionBatchInstalled')
            tickets = [t for t in sorted(batch.tickets, key=lambda t:(segments(t.path), t.generation))
                       if self.ticket_live(t, charge=True)]
            for event in batch.output:
                for ticket in tickets:
                    observation = digest('contracts.embedded-observation/completion-1',
                                         {'source': event['identity'], 'ticket': ticket.wire()})
                    if observation not in self.consumed_observations:
                        self.frame.queue.append(('EMBEDDED', event, ticket, observation))

    def run_local(self, sealed, key, incoming, lifecycle, seeds, phase, routes):
        self.engine.observe_execution('localTurn', member=key, event=self.event_id,
            before=sealed.documents[key].blue_id, phase=phase, initialization=bool(lifecycle),
            receiving=bool(incoming), verifying=getattr(self.engine,'_verifying_completion',False))
        saved = self.state, self.graph, self.frame, self.activation
        self.activation=deepcopy(self.activation)
        self.state = sealed.copy()
        self.graph = self.fork_graph(self.state)
        start = len(self.meter.trace)
        work_start = len(self.work)
        changes_start = len(self.changes)
        serial = self.serials[key]
        self.serials[key] += 1
        descriptor = dict(member=key, activation=self.activation.get(key, 0), beforeView=vector(sealed, [key]),
                          profile=self.meter.policy()['profile'],
                          cause={'kind': 'INITIALIZE'} if self.admission else {'kind': 'PROCESS', 'event': self.event_id, 'timestamp': self.timestamp},
                          phase=phase, turnSerial=serial,
                          dependencies=vector(sealed, {e.target for e in sealed.edges.values() if e.source == key}),
                          incoming=[{'kind':'CYCLIC' if b.round_seal else 'DAG', 'sourceCompletion':b.completion,
                                     **({'roundSeal':b.round_seal} if b.round_seal else {}), 'tickets':[t.wire() for t in b.tickets]}
                                    for b in sorted(incoming, key=lambda b:(b.source,b.serial))],
                          seeds=[asdict(s) for s in seeds],
                          lifecycle={'kind':'INITIALIZE','document':{'blueId':lifecycle}} if lifecycle else {'kind':'NONE'})
        # Execution certificates include invocation-wide logical gas/evidence.
        # They authenticate a batch, but are not its semantic occurrence: an
        # unrelated containing root must not rename the child's next emission.
        # Bind the actual completed state, ordered output and occurrence tickets
        # here; retain the complete certificate above for verification/replay.
        semantic_input = {**descriptor, 'incoming': [dict(
            kind='CYCLIC' if b.round_seal else 'DAG', source=b.source, serial=b.serial,
            after=b.after, output=list(b.output), tickets=[t.wire() for t in b.tickets])
            for b in sorted(incoming, key=lambda b:(b.source,b.serial))]}
        source_turn = digest('contracts.turn-input/completion-1', semantic_input)
        descriptor['logicalContext'] = self.logical_commitment()
        self.frame = Frame(key, deepcopy(sealed.documents[key]), descriptor, source_turn)
        self.suspended.append(self.frame)
        try:
            self.turn_count += 1
            self.meter.owner = key
            self.meter.contracts('localTurnOpened')
            self.install_inputs(key, incoming)
            if lifecycle and self.live(key):
                self.initializing.add(key)
                self.meter.owner = key
                self.meter.contracts('scopeInitialization')
                node = self.runtime_node(self.reg.typed('Document Processing Initiated', document={'blueId':lifecycle}))
                cs = self.reg.contracts(self.state.documents[key].body)
                for channel, declaration in self.ordered(cs):
                    if declaration['_role'] == 'lifecycle' and ('event' not in declaration or self.runtime_matches(node, declaration['event'])):
                        trampoline(self.dispatch(key, channel, node, 'INITIALIZATION'))
                trampoline(self.custom_internal(key, 'INITIALIZATION', node, cs))
            trampoline(self.drain())
            for seed in seeds:
                doc = self.state.documents[key]
                life = doc.channel_lives.get(seed.channel)
                if (self.live(key) and self.activation.get(key, 0) == 0 and life is not None and life.generation == seed.generation):
                    trampoline(self.dispatch(key, seed.channel, self.event, 'EXTERNAL', seed.operation, call=self.call))
                    trampoline(self.drain())
                    self.frame.consumed.append(seed)
            self.settle_local(key, lifecycle)
            self.graph.finalize_local(key)
            self.preflight(members={key})
            require(not self.frame.queue, 'NONQUIESCENT_LOCAL_RESULT')
            self.state.documents[key].blue_id = self.blue.identity(self.state.documents[key].body)
            self.meter.owner = key
            self.meter.contracts('localTurnSealed')
            completion = committed('turn-result', dict(
                turnInput=descriptor, afterView=vector(self.state, [key]), output=deepcopy(self.frame.output),
                memberMetadata=self.state.documents[key].metadata(), edgeChanges=deepcopy(self.changes[changes_start:]),
                consumedSeeds=[asdict(s) for s in self.frame.consumed],
                writes=deepcopy(self.frame.writes),
                retiredTickets=[t.wire() for b in incoming for t in b.tickets if not self.ticket_live(t)],
                workSegment=self.relative_segment(start)))
            self.turns.append(completion)
            new = set(self.state.documents) - set(sealed.documents)
            owned = new | {key}
            return {'key':key, 'documents':{k:deepcopy(self.state.documents[k]) for k in owned},
                    'edges':{k:e for k,e in self.state.edges.items() if e.source in owned},
                    'completion':completion, 'routes':routes}
        finally:
            self.allocation = max(self.allocation, self.graph.allocation)
            self.topology_changed |= self.graph.topology_changed
            self.suspended.pop()
            self.state, self.graph, self.frame, self.activation = saved

    def logical_commitment(self):
        logical = self.graph.logical
        # These keys are already exact identities/recipes, never cache addresses.
        return digest('contracts.logical-prefix/completion-1', {
            'gas': self.meter.trace, 'work': self.work,
            'manifests': sorted(logical.manifests),
            'established': sorted(logical.established,key=canonical),
            'proofs': sorted(logical.proofs,key=canonical),
            'partition': logical.partition,
            'boundIdentities': sorted(logical.bound_identities),
            'exactValues': sorted(((key,identity) for key,(_,identity) in logical.exact_values.items()),key=canonical),
            'carried': sorted(logical.carried_roots)})

    def merge_owned(self, result):
        owned = set(result['documents'])
        self.state.documents.update(result['documents'])
        for document in result['documents'].values():
            if isinstance(document.body,L.Node):self.blue.note_identity(document.body,document.blue_id)
        for edge in list(self.state.edges):
            if edge[0] in owned:
                self.state.edges.pop(edge)
        self.state.edges.update(result['edges'])
        self.graph.allocation = self.allocation
        self.graph.refresh_aliases()

    def settle_local(self, key, lifecycle):
        if lifecycle and self.reg.marker(self.state.documents[key].body, 'initialized') is None:
            self.meter.owner = key
            self.meter.contracts('processorMarkerWritten')
            self.direct_marker(key, 'initialized', self.reg.typed('Processing Initialized Marker', document={'blueId':lifecycle}))
        if key in self.termination and self.reg.marker(self.state.documents[key].body, 'terminated') is None:
            self.meter.owner = key
            self.meter.contracts('processorMarkerWritten')
            cause, reason = self.termination[key]
            self.direct_marker(key, 'terminated', self.reg.typed('Processing Terminated Marker', cause=cause,
                                                             **({'reason':reason} if reason is not None else {})))
        doc = self.state.documents[key]
        marker = self.reg.marker(doc.body, 'checkpoint')
        entries = deepcopy(self.blue.literal(marker).get('entries', {}) if marker else {})
        before = deepcopy(entries)
        for channel in list(entries):
            if channel not in doc.channel_lives or (key, channel) in self.graph.resets:
                entries.pop(channel)
        for seed in self.frame.consumed:
            life = doc.channel_lives.get(seed.channel)
            if life is not None and life.generation == seed.generation:
                entries[seed.channel] = {'timestamp':self.timestamp, 'event':{'blueId':self.event_id}}
        for channel in sorted(set(before) | set(entries)):
            if before.get(channel) != entries.get(channel):
                self.meter.owner = key
                self.meter.contracts('checkpointWritten')
                self.writes.append(dict(document=key,channel=channel,before=before.get(channel),after=entries.get(channel)))
        if entries != before:
            self.direct_marker(key, 'checkpoint', self.reg.typed('Channel Event Checkpoint', entries=entries) if entries else None)

    def emit(self, key, node):
        self.meter.owner = key
        self.graph.logical.establish(node)
        self.meter.contracts('internalEventEnqueued')
        occurrence = committed('event', dict(sourceTurn=self.frame.source_turn, ordinal=len(self.frame.output),
                                             event=self.blue.identity(node)))
        self.frame.output.append(occurrence)
        self.events.append(dict(ordinal=len(self.events), identity=occurrence['identity'], document=key,
                                event=occurrence['event'], sourceTurn=occurrence['sourceTurn'], sourceOrdinal=occurrence['ordinal']))
        self.frame.queue.append(('LOCAL', occurrence, None, occurrence['identity']))

    def drain(self):
        key = self.frame.key
        while self.frame.queue:
            kind, occurrence, ticket, observation = self.frame.queue.popleft()
            self.meter.owner = key
            if kind == 'LOCAL':
                self.meter.contracts('internalEventDequeued')
            else:
                self.consumed_observations.add(observation)
                if not self.ticket_live(ticket, charge=True):
                    continue
            if not self.live(key):
                continue
            node = L.Ref(occurrence['event'])
            cs = self.reg.contracts(self.state.documents[key].body)
            self.frame.ticket = ticket
            try:
                if kind == 'LOCAL':
                    for channel, declaration in self.ordered(cs):
                        if not self.live(key):
                            break
                        if declaration['_role'] == 'triggered' and ('event' not in declaration or self.runtime_matches(node, declaration['event'])):
                            yield self.dispatch(key, channel, node, 'TRIGGERED')
                    yield self.custom_internal(key, 'TRIGGERED', node, cs)
                else:
                    payload = self.runtime_node(self.reg.typed('Embedded Event Delivery', sourcePath=ticket.path,
                                                           event={'blueId':occurrence['event']}))
                    for channel, declaration in self.ordered(cs):
                        if not self.ticket_live(ticket) or not self.live(key):
                            break
                        if declaration['_role'] != 'embedded_event':
                            continue
                        if 'sourcePath' in declaration and declaration['sourcePath'] != ticket.path:
                            continue
                        if 'event' in declaration and not self.runtime_matches(node, declaration['event']):
                            continue
                        yield self.dispatch(key, channel, payload, 'EMBEDDED')
                    yield self.custom_internal(key, 'EMBEDDED', payload, cs)
            finally:
                self.frame.ticket = None

    def creation_barrier(self):
        # Save the creator's private body. Existing members are read-only pins;
        # only newly uninitialized members enter this nested initialization.
        creator = self.frame
        missing = {k for k in self.graph.reachable() if self.reg.marker(self.state.documents[k].body, 'initialized') is None
                   and k not in self.initializing and k not in {f.key for f in self.suspended}}
        if not missing:
            return
        private_state, private_graph = self.state, self.graph
        self.state = private_state.copy()
        for frame in self.suspended:
            self.state.documents[frame.key] = deepcopy(frame.before)
        self.graph = self.fork_graph(self.state)
        try:
            batches = self.drive_phase('INITIALIZE', allowed=missing, barrier=True)
            owned = set(self.state.documents) - set(private_state.documents) | missing
            for key in owned:
                private_state.documents[key] = deepcopy(self.state.documents[key])
            for edge in list(private_state.edges):
                if edge[0] in owned:
                    private_state.edges.pop(edge)
            private_state.edges.update({k:e for k,e in self.state.edges.items() if e.source in owned})
        finally:
            self.state, self.graph = private_state, private_graph
            self.graph.allocation = self.allocation
        self.frame = creator
        self.install_inputs(creator.key, [b for b in batches if any(t.parent == creator.key for t in b.tickets)])
        if self.phase is not None:
            for batch in batches:
                for parent in {t.parent for t in batch.tickets} - {creator.key}:
                    self.phase.pending[parent].append(batch)
        self.graph.refresh_aliases()
