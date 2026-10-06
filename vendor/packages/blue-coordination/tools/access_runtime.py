"""Execute the packaged access document with the pinned Contracts processor.

The external channel verifies signed public history; standard Contracts/BEX runs
its update operation. This reference harness is not a hosted provider runtime.
"""
from blue_contracts import Processor, RuntimeBinding
from blue_contracts.reference.runtime import data_copy
from reference import check, ref, Verifier, validate_access_sets


def control_timeline(e, access):
    channel = e.get(access)['contracts']['provider']
    return e.typed('Signed Timeline', provider=channel['provider'], url=channel['url'], publicRead=True)


def access_document(e, timelines, keys, provider, url):
    return e.typed('Timeline Access', allowedTimelines=[ref(e.identity(t)) for t in timelines], allowedKeys=list(keys),
        contracts={'provider': e.typed('Public Timeline Channel', provider=provider, url=url),
                   'update': {'type': 'Coordination/Update Timeline Access'}})


class PublicChannel:
    def __init__(self, exact, provider, control, declaration):
        self.e = exact
        self.verifier = Verifier(exact, provider)
        self.control = control
        self.declaration = self.e.identity(declaration)

    def verify_admission(self, context):
        proof = data_copy(context.evidence)
        check(proof is not None, 'MISSING_PUBLIC_HISTORY')
        coverage = self.verifier.range(proof['checkpoint'], list(proof['entries']))
        check(coverage.timeline == self.e.identity(self.control), 'WRONG_CONTROL_TIMELINE')
        check(context.event in coverage.entries, 'UNAUTHENTICATED_INPUT')
        entry = self.e.get(ref(context.event))
        check(entry['timestamp'] == context.timestamp, 'WRONG_EVENT_TIME')
        check(coverage.complete_before > context.timestamp, 'INCOMPLETE_INPUT')
        # Header projections expand inherited values and are not exact Blue content.
        # Bind admission to the processor's exact declaration and occurrence instead.
        recipients = [{key: row[key] for key in ('member', 'document', 'channel', 'generation')}
                      for row in context.members if row['declaration'] == self.declaration]
        check(bool(recipients), 'WRONG_CHANNEL_DECLARATION')
        return {'event': context.event, 'timeline': coverage.timeline, 'recipients': recipients}

    def accept(self, context):
        context.gas.charge('accept')
        # The declaration was validated against the adopted signed descriptor.
        # Verify the immutable invocation observation, never a caller's Boolean.
        check(context.evidence is not None, 'MISSING_PUBLIC_HISTORY')
        recipient = {key: getattr(context, key) for key in ('member', 'document', 'channel', 'generation')}
        return (recipient in context.evidence['recipients'] and
                context.evidence['timeline'] == self.e.identity(self.control))


class AccessExecution:
    def __init__(self, exact, access, descriptor, checkpoint, entries):
        self.e = exact
        self.access = self.e.require_kind(access, 'Timeline Access')
        channel = self.access['contracts']['provider']
        self.e.require_kind(channel, 'Public Timeline Channel')
        self.control = control_timeline(self.e, self.access)
        self.v = Verifier(self.e, channel['provider'])
        declared = self.v.attestation(descriptor)
        check(self.e.identity(declared['controlTimeline']) == self.e.identity(self.control), 'INVALID_CONTROL_TIMELINE')
        validate_access_sets(self.e, channel['provider'], self.access['allowedTimelines'], self.access['allowedKeys'])
        # Instances may inherit the shipped program, but cannot replace it.
        update = self.access['contracts']['update']
        expected = {'type': 'Coordination/Update Timeline Access'}
        check(self.e.identity(update) == self.e.identity(expected), 'CHANGED_ACCESS_PROGRAM')
        check(set(self.access['contracts']) == {'provider', 'update'}, 'EXTRA_ACCESS_CONTRACT')
        self.checkpoint = self.e.get(checkpoint)
        self.entries = [self.e.get(x) for x in entries]
        self.coverage = self.v.range(checkpoint, entries)
        check(self.coverage.timeline == self.e.identity(self.control), 'WRONG_CONTROL_TIMELINE')
        self.p = Processor(self.e.language, local_driver=True)
        self.binding = self.e.aliases['Coordination/Public Timeline Channel']
        self.p.install_runtime(RuntimeBinding(self.binding, self.e.rules, 'external-channel', ('provider','url'), (),
            'coordinationPublicTimeline', (('accept', 1),), inherits_to_subtypes=True), PublicChannel(self.e, channel['provider'], self.control, channel))
        self.state = None
        self.outcomes = []
        self.versions = set()
        self.processed = 0

    def current_id(self):
        return self.state.documents[self.state.root].blue_id

    def current(self):
        raw = self.p.blue.literal(self.state.documents[self.state.root].body)
        self.e.put(raw)
        return raw

    def permissions(self):
        return {name: self.p.read(self.state, '/' + name) for name in ('allowedTimelines', 'allowedKeys')}

    def apply(self, entry):
        event = self.e.get(entry)
        check(self.e.is_contract_call(event.get('operation')), 'MISSING_ACCESS_OPERATION')
        check(self.e.identity(event['operation']) == self.e.identity(event['message']), 'OPERATION_MESSAGE_MISMATCH')
        call = self.e.get(event['operation'])
        check(call.get('channel') == 'provider' and call.get('operation') == 'update', 'INVALID_ACCESS_OPERATION')
        check('document' in call and self.e.identity(call['document']) in self.versions, 'WRONG_ACCESS_DOCUMENT')
        self.e.require_kind(event['actor'], 'Agent Actor')
        attempt = self.p.prepare_invocation(self.state, event, event['timestamp'], evidence={self.binding:
            {'checkpoint': self.checkpoint, 'entries': self.entries}})
        while (token := self.p.next_chunk(attempt)) is not None:
            self.p.accept_chunk(attempt, token, self.p.execute_chunk(token))
        outcome = self.p.finish(attempt)
        self.outcomes.append(outcome)
        check(outcome.status == 'APPLIED', 'ACCESS_EXECUTION_FAILED:' + str(outcome.diagnostic))
        self.state = outcome.snapshot
        self.versions.add(self.current_id())
        return outcome

    def replay(self):
        aid = self.e.identity(self.access)
        published = self.state is not None
        for entry in self.entries[self.processed:]:
            message = self.e.get(entry['message'])
            if self.e.identity(message) == aid:
                check(not published, 'DUPLICATE_ACCESS_PUBLICATION')
                self.e.require_kind(entry['actor'], 'Agent Actor')
                self.state = self.p.create(self.access)
                self.versions = {aid, self.current_id()}
                published = True
                self.current()
                continue
            if not self.e.is_contract_call(message):
                continue
            if message.get('channel') == 'provider' and message.get('operation') == 'update':
                check('document' in message, 'INVALID_ACCESS_OPERATION')
            target = self.e.identity(message['document']) if 'document' in message else None
            if target not in self.versions:
                continue
            check(published, 'ACCESS_UPDATE_BEFORE_PUBLICATION')
            self.apply(entry)
            self.current()
        check(published, 'ACCESS_UNCONFIRMED')
        self.processed = len(self.entries)
        return self.current()
