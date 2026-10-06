"""Whole-event recognition, deterministic channel acceptance and local checkpoints.

There is no transport, permission, source-order or external-delivery protocol in
this module. Seeds are private frozen work records, never processor arguments.
"""
from dataclasses import dataclass
from algorithms import blue as L
from .model import ChannelLife, ContractError, require, token, digest, integer
from .registry import EXTERNAL

PRIMITIVE = {'external', 'extension_external'}
REQUEST_FIELDS = {'operation', 'channel', 'document', 'requireExactDocumentVersion', 'request'}

@dataclass(frozen=True)
class Seed:
    document: str
    channel: str
    generation: int
    operation: str | None = None


def leaves(cs, key, active=()):
    require(key in cs and cs[key]['_role'] in EXTERNAL, 'INVALID_COMPOSITE_MEMBER', key=key)
    require(key not in active, 'CYCLIC_CHANNEL_COMPOSITION')
    role = cs[key]['_role']
    if role in PRIMITIVE:
        return (key,)
    members = (sorted(k for k, c in cs.items() if c['_role'] in PRIMITIVE)
               if role == 'all' else cs[key].get('channels', []))
    require(type(members) is list and all(type(k) is str for k in members), 'INVALID_COMPOSITE_MEMBERS')
    require(len(members) == len(set(members)), 'DUPLICATE_COMPOSITE_MEMBER')
    return tuple(sorted({leaf for member in members for leaf in leaves(cs, member, active + (key,))}))


def signature(cs, key):
    declaration = cs[key]
    role = declaration['_role']
    record = {'type': declaration['type']['blueId'], 'leaves': list(leaves(cs, key))}
    if role == 'external':
        if 'event' in declaration:
            record['event'] = declaration['event']
    elif role == 'extension_external':
        runtime = declaration['_extension']
        record['runtime'] = runtime.binding.wire()
        record['header'] = {k: declaration[k] for k in runtime.binding.header_fields if k in declaration}
    else:
        # Membership AND the leaf acceptance semantics define a union lifetime.
        record['members'] = {k: signature(cs, k) for k in leaves(cs, key)}
    return digest('contracts.channel/completion-1', record)


def refresh_lifetimes(graph, birth=None, *, members=None):
    for member in sorted(graph.reachable(active=True) if members is None else members):
        doc = graph.state.documents[member]
        cs = graph.registry.contracts(doc.body)
        headers = {k: signature(cs, k) for k, c in cs.items() if c['_role'] in EXTERNAL}
        for key in sorted(set(doc.channel_lives) - set(headers)):
            del doc.channel_lives[key]
            graph.resets.add((member, key))
        for key, sig in sorted(headers.items()):
            old = doc.channel_lives.get(key)
            if old is None or old.signature != sig:
                generation = integer(doc.channel_serials.get(key, 0) + 1)
                doc.channel_serials[key] = generation
                doc.channel_lives[key] = ChannelLife(generation, sig)
                graph.resets.add((member, key))


def checkpoint(registry, doc, key):
    marker = registry.marker(doc.body, 'checkpoint')
    if marker is None:
        return None
    raw = registry.blue.literal(marker)
    require(type(raw) is dict and set(raw) <= {'type', 'entries'}, 'INVALID_CHECKPOINT')
    entries = raw.get('entries', {})
    require(type(entries) is dict, 'INVALID_CHECKPOINT')
    row = entries.get(key)
    if row is None:
        return None
    require(type(row) is dict and set(row) == {'timestamp', 'event'}, 'INVALID_CHECKPOINT')
    integer(row['timestamp'])
    require(type(row['event']) is dict and set(row['event']) == {'blueId'}, 'INVALID_CHECKPOINT')
    registry.blue.open(L.Ref(row['event']['blueId']))
    return row


def is_new(registry, doc, key, event_id, timestamp):
    """Only exact last-occurrence suppression; no invented external ordering."""
    previous = checkpoint(registry, doc, key)
    if previous is None or previous['event']['blueId'] != event_id:
        return True
    require(previous['timestamp'] == timestamp, 'EVENT_TIMESTAMP_CONFLICT')
    return False


def operation_request(registry, node):
    """Read a complete typed Operation Request; never synthesize missing fields."""
    if registry.role(node) != 'request':
        return None
    blue = registry.blue
    head = blue.head(node)
    require(head.items is None and head.value is L.ABSENT and head.contracts is None,
            'INVALID_OPERATION_REQUEST')
    require(set(head.fields) <= REQUEST_FIELDS | {'specification'}, 'INVALID_OPERATION_REQUEST')
    result = {'type': {'blueId': head.type_id}}
    for name in ('operation', 'channel', 'requireExactDocumentVersion'):
        child = blue.child(node, name)
        if child is not None and L.present_recipe(child, blue.context):
            result[name] = blue.project(child)
    result['operation'] = token(result.get('operation'))
    result['channel'] = token(result.get('channel'))
    exact = result.get('requireExactDocumentVersion', False)
    require(type(exact) is bool, 'INVALID_OPERATION_REQUEST')
    for name in ('document', 'request'):
        child = blue.child(node, name)
        if child is not None and L.present_recipe(child, blue.context):
            value = blue.exact(child)
            blue.certify(value)
            blue.remember(value)
            result[name] = {'blueId': blue.identity(value)}
    require(not exact or 'document' in result, 'INVALID_OPERATION_REQUEST')
    return result


def recognize_call(registry, event):
    """The only two recognition sites: event, otherwise event.operation."""
    if registry.role(event) == 'request':
        return event, operation_request(registry, event)
    candidate = registry.blue.child(event, 'operation')
    if candidate is not None and registry.role(candidate) == 'request':
        selected = registry.blue.exact(candidate)
        return selected, operation_request(registry, selected)
    return None, None


def event_observation(registry, event, *, logical=None):
    """Read the actual event, including outer and inherited fields."""
    return registry.blue.view(event, logical=logical)


def select_seeds(run):
    """Freeze dependency-first recipients and validate all named calls first."""
    graph, reg, blue = run.graph, run.reg, run.blue
    from .graph import components
    result = []
    for member in [k for group in components(graph.reachable(active=True), graph.state.edges.values()) for k in group]:
        doc = run.input.documents[member]
        cs = reg.contracts(doc.body)
        primitive = set()
        run.meter.owner = member
        ordered = run.ordered(cs)
        for key, channel in ordered:
            if channel['_role'] not in PRIMITIVE:
                continue
            run.meter.contracts('channelCandidateTested')
            if channel['_role'] == 'external':
                accepted = 'event' not in channel or blue.matches(run.event, channel['event'])
            else:
                accepted = channel['_extension'].accept_external(
                    channel, cs, reg, run.event, run.timestamp, checkpoint(reg, doc, key), run.meter, member,
                    document=doc.blue_id, channel=key, generation=doc.channel_lives[key].generation,
                    evidence=run.external_admissions.get(channel['_extension'].binding.type_id))
            if accepted:
                primitive.add(key)
        accepted = set(primitive)
        for key, channel in ordered:
            if channel['_role'] not in {'composite', 'all'}:
                continue
            run.meter.contracts('channelCandidateTested')
            if primitive.intersection(leaves(cs, key)):
                accepted.add(key)
        fresh = set()
        for key, channel in ordered:
            if key not in accepted:
                continue
            run.meter.contracts('channelAccepted')
            run.meter.contracts('checkpointCompared')
            if is_new(reg, doc, key, run.event_id, run.timestamp):
                fresh.add(key)
        if not fresh:
            continue
        target, operation = None, None
        if run.call_record is not None and primitive:
            request = run.call_record
            selected = request['channel']
            audience = [e['operationAudience'][member] for e in run.external_admissions.values()
                        if member in e.get('operationAudience', {})]
            addressed = 'document' in request
            # A trusted runtime can establish lineage membership. In generic
            # Contracts an explicit exact target names the selected member.
            in_audience = all(audience) if audience else (not addressed or
                request['document']['blueId'] == doc.blue_id or len(run.input.documents) == 1)
            candidate = in_audience and (addressed or selected in accepted and cs[selected]['_role'] in EXTERNAL)
            if candidate:
                target, operation = selected, request['operation']
                require(target in cs and target in accepted and cs[target]['_role'] in EXTERNAL,
                        'INVALID_TARGET_CHANNEL', document=member, channel=target)
            # A union that is newly observing an already-consumed call does not
            # repeat the operation, its precondition or its request validation.
            if candidate and target in fresh:
                require(operation in cs and cs[operation]['_role'] == 'operation'
                        and cs[operation]['channel'] == target,
                        'INVALID_TARGET_OPERATION', document=member, operation=operation)
                if request.get('requireExactDocumentVersion', False):
                    require(request['document']['blueId'] == doc.blue_id,
                            'STALE_DOCUMENT_PRECONDITION', document=member)
                if 'request' in cs[operation]:
                    require('request' in request and blue.matches(request['request'], cs[operation]['request']),
                            'INVALID_REQUEST', document=member, operation=operation)
        for key, channel in ordered:
            if key in fresh:
                result.append(Seed(member, key, doc.channel_lives[key].generation,
                                   operation if key == target else None))
                run.meter.contracts('deliverySnapshotEntry')
    run.meter.owner = ''
    return tuple(result)
