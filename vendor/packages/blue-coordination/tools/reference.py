"""Executable protocol model. Real Blue identity/Ed25519; in-memory storage only.

This is not the AWS provider or a Contracts execution engine. Established lists
passed to a verifier represent prefixes already checked and durably retained by
its caller. All deterministic signing seeds below are PUBLIC TEST FIXTURES.
"""
from dataclasses import dataclass
import copy
import hashlib
import json
import struct
import threading
from urllib.parse import urlsplit
from algorithms import blue as B
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from app import protocol_packages as publisher

MAX_TIME = 9007199254740990
MAX_BOUND = MAX_TIME + 1

def check(condition, code):
    if not condition:
        raise ValueError(code)

def ref(bid):
    return {'blueId': bid}

def hexbytes(value, size):
    check(isinstance(value, str) and len(value) == size * 2 and value == value.lower(), 'INVALID_HEX')
    try:
        result = bytes.fromhex(value)
    except ValueError:
        raise ValueError('INVALID_HEX') from None
    check(len(result) == size and result.hex() == value, 'INVALID_HEX')
    return result

def verify_sig(key, signature, data):
    try:
        Ed25519PublicKey.from_public_bytes(hexbytes(key, 32)).verify(hexbytes(signature, 64), data)
    except Exception as exc:
        raise ValueError('INVALID_SIGNATURE') from exc

class Exact:
    def __init__(self):
        self.language, self.aliases, self.rules = publisher.context()
        self.objects = {}
        self._identified = {}
        self._ancestors = {}

    def put(self, obj):
        source = json.dumps(obj, sort_keys=True, separators=(',', ':'))
        if source in self._identified:
            return self._identified[source]
        document = self.language.create(source, format='json')
        self.language.publish_document(document)
        self.objects[document.blue_id] = copy.deepcopy(obj)
        self._identified[source] = document.blue_id
        return document.blue_id

    def get(self, value):
        if isinstance(value, dict) and set(value) == {'blueId'}:
            bid = value['blueId']
            check(bid in self.objects, 'MISSING_CONTENT')
            obj = copy.deepcopy(self.objects[bid])
            check(self.put(obj) == bid, 'CONTENT_MISMATCH')
            return obj
        return copy.deepcopy(value)

    def text_field(self, value, field):
        """Read a possibly inherited Text value without changing the exact identity."""
        result = self.language.query(json.dumps(ref(self.identity(value))), '/' + field)
        if result['outcome'] == 'Absent':
            return None
        check(result['outcome'] == 'Established' and result['value'].get('kind') == 'Text', 'INVALID_TEXT_FIELD:' + field)
        return result['value']['value']

    def identity(self, value):
        obj = self.get(value)
        return self.put(obj)

    def typed(self, name, **fields):
        obj = {'type': 'Coordination/' + name, **fields}
        self.put(obj)
        return obj

    def define(self, alias, raw):
        document = self.language.admit_definition(json.dumps(raw), format='json')
        self.language.publish_document(document)
        self.language.aliases[alias] = document.blue_id
        self.aliases[alias] = document.blue_id
        return document.blue_id

    def kind(self, value, name):
        obj = self.get(value)
        if not isinstance(obj, dict):
            return False
        actual = obj.get('type')
        tid = self.language.aliases.get(actual) if isinstance(actual, str) else actual.get('blueId') if isinstance(actual, dict) else None
        if tid is None:
            return False
        if tid not in self._ancestors:
            self._ancestors[tid] = self.language._run(lambda c: frozenset(B.ancestry(tid, c)))
        return self.aliases['Coordination/' + name] in self._ancestors[tid]

    def is_contract_call(self, value):
        obj = self.get(value)
        if not isinstance(obj, dict):
            return False
        actual = obj.get('type')
        tid = self.language.aliases.get(actual) if isinstance(actual, str) else actual.get('blueId') if isinstance(actual, dict) else None
        return tid is not None and self.language.aliases['Contracts/Operation Request'] in self.language._run(lambda c: B.ancestry(tid, c))

    def require_kind(self, value, name):
        check(self.kind(value, name), 'WRONG_TYPE:' + name)
        return self.get(value)

@dataclass
class Coverage:
    timeline: str
    entries: list
    complete_before: int

    @property
    def head(self):
        return self.entries[-1] if self.entries else None

class Verifier:
    def __init__(self, exact, provider):
        self.e = exact
        self.provider = self.e.identity(provider)
        self.key = self.e.text_field(provider, 'publicKey')

    def timeline(self, value):
        t = self.e.require_kind(value, 'Signed Timeline')
        check(self.e.identity(t['provider']) == self.provider, 'WRONG_PROVIDER')
        return self.e.identity(t)

    def attestation(self, att):
        a = self.e.require_kind(att, 'Provider Attestation')
        check(self.e.identity(a['provider']) == self.provider, 'WRONG_PROVIDER')
        bid = self.e.identity(a['object'])
        verify_sig(self.key, a['signature'], ('blue.coordination.object\n' + self.provider + '\n' + bid).encode())
        obj = self.e.get(a['object'])
        if 'timeline' in obj:
            self.timeline(obj['timeline'])
        if 'provider' in obj:
            check(self.e.identity(obj['provider']) == self.provider, 'WRONG_PROVIDER')
        return obj

    def checkpoint(self, checkpoint):
        a = self.e.require_kind(checkpoint, 'Timeline Attestation')
        g = self.e.require_kind(a['guarantee'], 'Timeline Completeness Guarantee')
        tid = self.timeline(g['timeline'])
        check(self.timeline(a['timeline']) == tid, 'WRONG_TIMELINE')
        check(type(g['completeBefore']) is int and 0 <= g['completeBefore'] <= MAX_BOUND, 'INVALID_BOUND')
        bid = self.e.identity(g)
        verify_sig(self.key, a['signature'], ('blue.coordination.guarantee\n' + bid).encode())
        return tid, g

    def chain(self, tid, entries, after=None, established=()):
        current = after
        if after is not None:
            check(after in established, 'UNKNOWN_ANCHOR')
            index = established.index(after) + 1
            last_time = self.e.get(ref(after))['timestamp']
        else:
            index, last_time = 0, -1
        result = list(established[:index])
        for item in entries:
            entry = self.e.require_kind(item, 'Timeline Entry')
            check(self.timeline(entry['timeline']) == tid, 'WRONG_TIMELINE')
            predecessor = self.e.identity(entry['prevEntry']) if 'prevEntry' in entry else None
            check(predecessor == current, 'CHAIN_GAP')
            timestamp = entry['timestamp']
            check(type(timestamp) is int and last_time < timestamp <= MAX_TIME, 'NONMONOTONIC_TIME')
            bid = self.e.identity(entry)
            if index < len(established):
                check(bid == established[index], 'HISTORY_CONFLICT')
            result.append(bid)
            current, last_time = bid, timestamp
            index += 1
        return result

    def range(self, checkpoint, entries, after=None, established=()):
        tid, guarantee = self.checkpoint(checkpoint)
        result = self.chain(tid, entries, after, established)
        head = self.e.identity(guarantee['lastEntry']) if 'lastEntry' in guarantee else None
        check((result[-1] if result else None) == head, 'HEAD_MISMATCH')
        if result:
            check(self.e.get(ref(result[-1]))['timestamp'] < guarantee['completeBefore'], 'ENTRY_OUTSIDE_PREFIX')
        return Coverage(tid, result, guarantee['completeBefore'])

    def successor(self, attestation, entries, after=None, established=()):
        successor = self.e.require_kind(self.attestation(attestation), 'Timeline Entry')
        tid = self.timeline(successor['timeline'])
        result = self.chain(tid, entries, after, established)
        check(bool(result) and result[-1] == self.e.identity(successor), 'SUCCESSOR_MISSING')
        return Coverage(tid, result[:-1], successor['timestamp'])

    def read_response(self, request, response):
        q = self.e.require_kind(request, 'Read Timeline Request')
        validate_read_request(q)
        response = self.e.require_kind(self.attestation(response), 'Timeline Read Response')
        check(self.e.identity(response['request']) == self.e.identity(q), 'WRONG_REQUEST')
        tid, guarantee = self.checkpoint(response['checkpoint'])
        check(tid == self.timeline(q['timeline']), 'WRONG_TIMELINE')
        check(guarantee['completeBefore'] >= q.get('minimumCompleteBefore', 0), 'BOUND_UNAVAILABLE')
        check(('page' in response) == (q['limit'] > 0), 'UNEXPECTED_PAGE_PRESENCE')
        return response


    def page(self, request, response):
        q = self.e.get(request)
        response = self.read_response(request, response)
        check(q['limit'] > 0, 'CHECKPOINT_ONLY')
        page = self.e.require_kind(response['page'], 'Timeline Entries Page')
        tid, guarantee = self.checkpoint(page['checkpoint'])
        check(self.e.identity(page['checkpoint']) == self.e.identity(response['checkpoint']), 'CHECKPOINT_CHANGED')
        check(tid == self.timeline(q['timeline']) == self.timeline(page['timeline']), 'WRONG_TIMELINE')
        selectors = [x for x in ('afterEntry', 'afterTimestamp', 'cursor') if x in q]
        check(len(selectors) <= 1, 'INVALID_SELECTORS')
        pred = self.e.identity(page['predecessor']) if 'predecessor' in page else None
        after = q.get('afterEntry')
        timestamp = q.get('afterTimestamp')
        if 'cursor' in q:
            cursor = self.e.require_kind(q['cursor'], 'Timeline Read Cursor')
            check(self.timeline(cursor['timeline']) == tid, 'WRONG_TIMELINE')
            check(self.e.identity(cursor['checkpoint']) == self.e.identity(page['checkpoint']), 'CHECKPOINT_CHANGED')
            after, timestamp = cursor.get('afterEntry'), cursor.get('afterTimestamp')
        if after is not None:
            check(pred == self.e.identity(after), 'WRONG_ANCHOR')
        elif timestamp is not None:
            check(type(timestamp) is int and -1 <= timestamp <= MAX_TIME, 'INVALID_TIMESTAMP')
            if pred:
                check(self.e.get(ref(pred))['timestamp'] <= timestamp, 'WRONG_SEEK_PREDECESSOR')
        else:
            check(pred is None, 'WRONG_GENESIS')
        last, previous_time = pred, self.e.get(ref(pred))['timestamp'] if pred else -1
        ids = []
        check(type(q['limit']) is int and 0 < q['limit'] and len(page['entries']) <= q['limit'], 'PAGE_LIMIT')
        for value in page['entries']:
            entry = self.e.require_kind(value, 'Timeline Entry')
            check(self.timeline(entry['timeline']) == tid, 'WRONG_TIMELINE')
            prev = self.e.identity(entry['prevEntry']) if 'prevEntry' in entry else None
            check(prev == last, 'CHAIN_GAP')
            check(previous_time < entry['timestamp'] < guarantee['completeBefore'], 'ENTRY_OUTSIDE_PREFIX')
            if timestamp is not None:
                check(entry['timestamp'] > timestamp, 'WRONG_SEEK')
            last = self.e.identity(entry)
            ids.append(last)
            previous_time = entry['timestamp']
        check(type(page['hasMore']) is bool, 'INVALID_HAS_MORE')
        head = self.e.identity(guarantee['lastEntry']) if 'lastEntry' in guarantee else None
        if page['hasMore']:
            check(bool(ids) and 'nextCursor' in page and last != head, 'NO_CURSOR_PROGRESS')
            cursor = self.e.require_kind(page['nextCursor'], 'Timeline Read Cursor')
            check(self.timeline(cursor['timeline']) == tid, 'WRONG_TIMELINE')
            check('afterTimestamp' not in cursor and self.e.identity(cursor['afterEntry']) == last, 'WRONG_CURSOR')
            check(self.e.identity(cursor['checkpoint']) == self.e.identity(page['checkpoint']), 'CHECKPOINT_CHANGED')
        else:
            check('nextCursor' not in page, 'UNEXPECTED_CURSOR')
            check(last == head, 'TRUNCATED_PAGE')
        return page, ids

    def access(self, access, checkpoint, entries, descriptor):
        from access_runtime import AccessExecution
        run = AccessExecution(self.e, access, descriptor, checkpoint, entries)
        return run.replay()

    def stream(self, binding, binding_attestation, batches, after=None, established=()):
        check(self.e.identity(self.attestation(binding_attestation)) == self.e.identity(binding), 'WRONG_BINDING')
        binding = self.e.require_kind(binding, 'Timeline Stream Binding')
        tid = self.timeline(binding['timeline'])
        stream = self.e.require_kind(binding['stream'], 'Timeline Update Stream')
        check(self.e.identity(stream['provider']) == self.provider, 'WRONG_PROVIDER')
        check(self.e.get(stream['timeline'])['publicRead'] is True, 'PRIVATE_STREAM')
        check(binding['fromInclusive'] < binding['untilExclusive'], 'INVALID_BINDING_INTERVAL')
        hexbytes(binding['timelineTag'], 32)
        entries = [self.e.require_kind(self.attestation(x), 'Timeline Entry') for x in batches]
        ids = self.chain(self.timeline(stream['timeline']), entries, after, established)
        if after:
            prev = self.e.get(self.e.get(ref(after))['message'])
            sequence, boundary = prev['sequence'] + 1, prev['completeBefore']
        else:
            sequence, boundary = 0, None
        found, start = [], None
        for entry in entries:
            actor = self.e.require_kind(entry['actor'], 'Agent Actor')
            batch = self.e.require_kind(entry['message'], 'Timeline Stream Batch')
            check(self.e.identity(batch['stream']) == self.e.identity(stream), 'WRONG_STREAM')
            check(batch['sequence'] == sequence, 'STREAM_SEQUENCE_GAP')
            check(0 <= batch['fromInclusive'] < batch['completeBefore'] <= MAX_BOUND, 'INVALID_BATCH_INTERVAL')
            if boundary is not None:
                check(batch['fromInclusive'] == boundary, 'STREAM_WINDOW_GAP')
            if start is None:
                start = batch['fromInclusive']
            order, per_tag = [], set()
            for row in batch['announcements']:
                hexbytes(row['timelineTag'], 32)
                hexbytes(row['entryCommitment'], 32)
                check(batch['fromInclusive'] <= row['timestamp'] < batch['completeBefore'], 'ANNOUNCEMENT_OUTSIDE_WINDOW')
                key = (row['timestamp'], row['timelineTag'])
                check(key not in per_tag, 'DUPLICATE_ANNOUNCEMENT')
                per_tag.add(key)
                order.append((row['timestamp'], row['timelineTag'], row['entryCommitment']))
                if row['timelineTag'] == binding['timelineTag'] and binding['fromInclusive'] <= row['timestamp'] < binding['untilExclusive']:
                    found.append(row)
            check(order == sorted(order), 'UNSORTED_ANNOUNCEMENTS')
            sequence, boundary = sequence + 1, batch['completeBefore']
        check(start is not None, 'NO_STREAM_COVERAGE')
        lo, hi = max(start, binding['fromInclusive']), min(boundary, binding['untilExclusive'])
        check(lo < hi, 'NO_STREAM_COVERAGE')
        return {'timeline': tid, 'fromInclusive': lo, 'completeBefore': hi, 'announcements': found, 'feedEntries': ids}


def validate_access_sets(e, provider, timelines, keys):
    check(isinstance(timelines, list) and isinstance(keys, list), 'INVALID_ACCESS_SETS')
    tids = [e.identity(t) for t in timelines]
    check(len(set(tids)) == len(tids) and len(set(keys)) == len(keys), 'DUPLICATE_ACCESS_VALUE')
    verifier = Verifier(e, provider)
    for t in timelines:
        verifier.timeline(t)
    for key in keys:
        hexbytes(key, 32)


def commitment(stream_id, tag, timestamp, entry_id, salt):
    check(type(timestamp) is int and 0 <= timestamp <= MAX_TIME, 'INVALID_TIMESTAMP')
    salt = hexbytes(salt, 32)
    hexbytes(tag, 32)
    def lp(s):
        data = s.encode('utf-8')
        check(len(data) <= 0xffffffff, 'INVALID_LENGTH')
        return struct.pack('>I', len(data)) + data
    encoded = b'blue.coordination.stream-entry\n' + lp(stream_id) + lp(tag) + struct.pack('>Q', timestamp) + lp(entry_id) + salt
    return hashlib.sha256(encoded).hexdigest()


def verify_opening(e, binding, row, entry, salt):
    b = e.get(binding)
    x = e.require_kind(entry, 'Timeline Entry')
    check(e.identity(x['timeline']) == e.identity(b['timeline']), 'WRONG_TIMELINE')
    check(row['timelineTag'] == b['timelineTag'] and x['timestamp'] == row['timestamp'], 'WRONG_OPENING')
    check(b['fromInclusive'] <= x['timestamp'] < b['untilExclusive'], 'OPENING_OUTSIDE_BINDING')
    check(commitment(e.identity(b['stream']), row['timelineTag'], x['timestamp'], e.identity(x), salt) == row['entryCommitment'], 'COMMITMENT_MISMATCH')


def next_input(e, candidates, coverage):
    if not candidates:
        return None
    def key(entry):
        x = e.get(entry)
        return x['timestamp'], e.identity(x['timeline']), e.identity(x)
    chosen = min(candidates, key=key)
    check(bool(coverage) and all(c.complete_before > key(chosen)[0] for c in coverage), 'WAITING_FOR_COVERAGE')
    tid = e.identity(e.get(chosen)['timeline'])
    check(any(c.timeline == tid and e.identity(chosen) in c.entries for c in coverage), 'UNESTABLISHED_INPUT')
    return chosen


def validate_endpoint(endpoint):
    check(isinstance(endpoint, str) and bool(endpoint) and not any(c.isspace() for c in endpoint), 'INVALID_ENDPOINT')
    try:
        url = urlsplit(endpoint)
        check(url.scheme == 'https' and bool(url.hostname) and url.username is None and url.password is None,
              'INVALID_ENDPOINT')
        check(not url.query and not url.fragment and '?' not in endpoint and '#' not in endpoint,
              'INVALID_ENDPOINT')
        check(not endpoint.endswith('/') and not any(x in ('.', '..') for x in url.path.split('/')),
              'INVALID_ENDPOINT')
        check(url.port is None or 0 < url.port <= 65535, 'INVALID_ENDPOINT')
    except (ValueError, TypeError):
        raise ValueError('INVALID_ENDPOINT') from None
    return endpoint


def validate_reader_query(q):
    check(not set(q).intersection(('requestId', 'provider', 'createdAt', 'expiresAt', 'nonce', 'idempotencyKey')), 'UNEXPECTED_REQUEST_METADATA')


def validate_read_request(q):
    validate_reader_query(q)
    check(type(q.get('limit')) is int and q['limit'] >= 0, 'PAGE_LIMIT')
    selectors = [x for x in ('afterEntry', 'afterTimestamp', 'cursor') if x in q]
    check(len(selectors) <= 1, 'INVALID_SELECTORS')
    check(q['limit'] > 0 or not selectors, 'CHECKPOINT_ONLY_SELECTOR')
    if 'minimumCompleteBefore' in q:
        bound = q['minimumCompleteBefore']
        check(type(bound) is int and 0 <= bound <= MAX_BOUND, 'INVALID_BOUND')
        check('cursor' not in q, 'CURSOR_MINIMUM_BOUND')


def api_urls(e, timeline):
    """Standard routes for the one API serving this provider's public/private histories."""
    provider = e.get(timeline)['provider']
    base = validate_endpoint(e.text_field(provider, 'endpoint'))
    return {'endpoint': base, 'read': base + '/timelines/read', 'descriptor': base + '/provider'}


class ModelProvider:
    def __init__(self, exact, seed=b'\x11' * 32, endpoint='https://provider.example', snapshot=None, provider_type='Timeline Provider'):
        self.e = exact
        self.secret = Ed25519PrivateKey.from_private_bytes(seed)
        self.key = self.secret.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        self.provider = {'type': provider_type if '/' in provider_type else 'Coordination/' + provider_type, 'publicKey': self.key}
        if endpoint is not None:
            self.provider['endpoint'] = validate_endpoint(endpoint)
        self.e.put(self.provider)
        self.pid = self.e.identity(self.provider)
        self.verifier = Verifier(self.e, self.provider)
        self.lock = threading.RLock()
        self._runs = {}
        self.state = copy.deepcopy(snapshot) if snapshot else {'timelines': {}, 'requests': {}, 'checkpoints': {}, 'access': {}, 'actors': {}}

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def attest(self, obj):
        bid = self.e.identity(obj)
        data = ('blue.coordination.object\n' + self.pid + '\n' + bid).encode()
        return self.e.typed('Provider Attestation', provider=ref(self.pid), object=ref(bid), signature=self.secret.sign(data).hex())

    def create(self, owner, resource, public=False):
        base = self.e.text_field(self.provider, 'endpoint')
        url = resource if resource.startswith('https://') else base + '/timelines/' + resource
        validate_endpoint(url)
        timeline = self.e.typed('Signed Timeline', provider=ref(self.pid), url=url, publicRead=public)
        tid = self.e.identity(timeline)
        with self.lock:
            check(tid not in self.state['timelines'], 'TIMELINE_EXISTS')
            self.state['timelines'][tid] = {'owner': owner, 'entries': [], 'bound': 0}
        return timeline

    def append(self, owner, timeline, message, idempotency_key, now, expected=None):
        tid = self.e.identity(timeline)
        with self.lock:
            t = self.state['timelines'][tid]
            check(owner == t['owner'], 'ACCESS_DENIED')
            fingerprint = {'timeline': tid, 'message': self.e.identity(message), 'expected': expected}
            slot = owner + '/append/' + idempotency_key
            if slot in self.state['requests']:
                old = self.state['requests'][slot]
                check(old['fingerprint'] == fingerprint, 'IDEMPOTENCY_CONFLICT')
                return self.e.get(ref(old['entry']))
            head = t['entries'][-1] if t['entries'] else None
            if expected is not None:
                check(head == expected, 'HEAD_CONFLICT')
            previous_time = self.e.get(ref(head))['timestamp'] if head else -1
            timestamp = max(now, previous_time + 1, t['bound'])
            check(timestamp <= MAX_TIME, 'TIME_EXHAUSTED')
            actor = self.state.get('actors', {}).get(owner)
            if actor is None:
                actor = self.e.typed('Agent Actor', service='Timeline access service') if owner == '__provider__' else self.e.typed('Principal Actor', displayName=owner)
            check(self.e.kind(actor, 'Principal Actor') or self.e.kind(actor, 'Agent Actor'), 'INVALID_ACTOR')
            entry = self.e.typed('Timeline Entry', timeline=ref(tid), timestamp=timestamp, actor=ref(self.e.identity(actor)), message=ref(self.e.identity(message)), **({'prevEntry': ref(head)} if head else {}))
            if self.e.is_contract_call(message):
                entry['operation'] = ref(self.e.identity(message))
            bid = self.e.identity(entry)
            t['entries'].append(bid)
            self.state['requests'][slot] = {'fingerprint': fingerprint, 'entry': bid}
            return entry

    def seal(self, timeline, now, minimum=None):
        tid = self.e.identity(timeline)
        with self.lock:
            t = self.state['timelines'][tid]
            head = t['entries'][-1] if t['entries'] else None
            last = self.e.get(ref(head))['timestamp'] if head else -1
            bound = max(now, last + 1, t['bound'])
            check(bound <= MAX_BOUND, 'TIME_EXHAUSTED')
            check(minimum is None or minimum <= bound, 'BOUND_UNAVAILABLE')
            t['bound'] = bound
            g = self.e.typed('Timeline Completeness Guarantee', timeline=ref(tid), completeBefore=bound, **({'lastEntry': ref(head)} if head else {}))
            signature = self.secret.sign(('blue.coordination.guarantee\n' + self.e.identity(g)).encode()).hex()
            checkpoint = self.e.typed('Timeline Attestation', timeline=ref(tid), guarantee=ref(self.e.identity(g)), signature=signature)
            self.state['checkpoints'][self.e.identity(checkpoint)] = list(t['entries'])
            return checkpoint

    def can_read(self, timeline, key=None, owner=None):
        tid = self.e.identity(timeline)
        if self.e.get(timeline)['publicRead'] or owner == self.state['timelines'][tid]['owner']:
            return True
        return any(tid in saved['timelines'] and key in saved['keys'] for saved in self.state['access'].values())

    def set_actor(self, owner, actor):
        check(self.e.kind(actor, 'Principal Actor') or self.e.kind(actor, 'Agent Actor'), 'INVALID_ACTOR')
        self.state.setdefault('actors', {})[owner] = copy.deepcopy(actor)

    def request(self, name, **fields):
        return self.e.typed(name, **fields)

    def sign_reader(self, request, seed):
        private = Ed25519PrivateKey.from_private_bytes(seed)
        key = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        sig = private.sign(('blue.coordination.reader-request\n' + self.e.identity(request)).encode()).hex()
        return self.e.typed('Signed Reader Request', request=ref(self.e.identity(request)), publicKey=key, signature=sig)

    def authenticate_reader(self, envelope):
        a = self.e.require_kind(envelope, 'Signed Reader Request')
        q = self.e.get(a['request'])
        allowed = ('Get Timeline Access Request', 'Read Timeline Request', 'Fetch Timeline Entry Request', 'Resolve Timeline Content Request', 'Get Stream Binding Request', 'Fetch Stream Entry Request')
        check(any(self.e.kind(q, x) for x in allowed), 'OWNER_OPERATION')
        validate_reader_query(q)
        verify_sig(a['publicKey'], a['signature'], ('blue.coordination.reader-request\n' + self.e.identity(q)).encode())
        if self.e.kind(q, 'Get Timeline Access Request'):
            access = self.e.require_kind(q['access'], 'Timeline Access')
            check(self.e.identity(access['contracts']['provider']['provider']) == self.pid, 'WRONG_PROVIDER')
            return q, a['publicKey']
        timeline = q.get('timeline') or self.e.get(q['binding'])['timeline']
        self.verifier.timeline(timeline)
        check(self.e.kind(q, 'Get Timeline Access Request') or self.can_read(timeline, key=a['publicKey']), 'ACCESS_DENIED')
        return q, a['publicKey']

    def public_read(self, request, now):
        q = self.e.require_kind(request, 'Read Timeline Request')
        validate_reader_query(q)
        self.verifier.timeline(q['timeline'])
        check(self.e.get(q['timeline'])['publicRead'] is True, 'ACCESS_DENIED')
        return self.read(q, now)

    def discovery(self, control, endpoint):
        validate_endpoint(endpoint)
        control = dict(self.e.get(control), provider=self.provider)
        check(control['publicRead'] is True and self.state['timelines'][self.e.identity(control)]['owner'] == '__provider__', 'INVALID_CONTROL_TIMELINE')
        descriptor = self.e.typed('Provider Descriptor', provider=self.provider, endpoint=endpoint,
            controlTimeline=control, maxPageSize=1000, operations=[self.e.aliases['Coordination/'+name] for name in ('Create Timeline Request','Append Entry Request')])
        return dict(self.attest(descriptor), provider=self.provider, object=descriptor)

    def access_execution(self, access, now):
        from access_runtime import AccessExecution, control_timeline
        control = control_timeline(self.e, access)
        checkpoint = self.seal(control, now)
        entries = [ref(x) for x in self.state['timelines'][self.e.identity(control)]['entries']]
        aid = self.e.identity(access)
        run = self._runs.get(aid)
        if run is None:
            run = AccessExecution(self.e, access, self.discovery(control, api_urls(self.e, control)['endpoint']), checkpoint, entries)
            self._runs[aid] = run
        else:
            incoming = [self.e.get(x) for x in entries]
            check([self.e.identity(x) for x in incoming[:run.processed]] ==
                  [self.e.identity(x) for x in run.entries[:run.processed]], 'HISTORY_CONFLICT')
            run.checkpoint = checkpoint
            run.entries = incoming
            run.coverage = self.verifier.range(checkpoint, entries)
        run.replay()
        return run

    def get_access(self, request, now):
        q = self.e.require_kind(request, 'Get Timeline Access Request')
        validate_reader_query(q)
        aid = self.e.identity(q['access'])
        saved = self.state['access'].get(aid)
        check(saved is not None, 'NOT_FOUND')
        access = self.e.get(q['access'])
        run = self.access_execution(access, now)
        response = self.e.typed('Timeline Access Response', request=ref(self.e.identity(q)), access=access,
            current=run.current(), publication=self.attest(ref(saved['publication'])), lastEntry=self.attest(ref(saved['lastEntry'])))
        return self.attest(response)

    def read(self, request, now, key=None, owner=None):
        q = self.e.get(request)
        tid = self.verifier.timeline(q['timeline'])
        with self.lock:
            check(self.can_read(q['timeline'], key, owner), 'ACCESS_DENIED')
            self.e.require_kind(q, 'Read Timeline Request')
            validate_read_request(q)
            check(q['limit'] <= 1000, 'PAGE_LIMIT')
            after, timestamp = q.get('afterEntry'), q.get('afterTimestamp')
            if 'cursor' in q:
                c = self.e.get(q['cursor'])
                check(self.e.identity(c['timeline']) == tid, 'WRONG_TIMELINE')
                checkpoint = self.e.get(c['checkpoint'])
                after, timestamp = c.get('afterEntry'), c.get('afterTimestamp')
            else:
                checkpoint = self.seal(q['timeline'], now, minimum=q.get('minimumCompleteBefore'))
            check(self.verifier.checkpoint(checkpoint)[0] == tid, 'WRONG_TIMELINE')
            cid = self.e.identity(checkpoint)
            check(cid in self.state['checkpoints'], 'UNKNOWN_CHECKPOINT')
            all_ids = self.state['checkpoints'][cid]
            if q['limit'] == 0:
                result = self.e.typed('Timeline Read Response', request=ref(self.e.identity(q)), checkpoint=ref(cid))
                return self.attest(result)
            if after is not None:
                after = self.e.identity(after)
                check(after in all_ids, 'UNKNOWN_ANCHOR')
                start = all_ids.index(after) + 1
            elif timestamp is not None:
                check(type(timestamp) is int and -1 <= timestamp <= MAX_TIME, 'INVALID_TIMESTAMP')
                start = next((i for i, bid in enumerate(all_ids) if self.e.get(ref(bid))['timestamp'] > timestamp), len(all_ids))
            else:
                start = 0
            chosen = all_ids[start:start + q['limit']]
            more = start + len(chosen) < len(all_ids)
            page_fields = {'timeline': ref(tid), 'checkpoint': ref(cid), 'entries': [ref(x) for x in chosen], 'hasMore': more}
            if start:
                page_fields['predecessor'] = ref(all_ids[start - 1])
            if more:
                cursor = self.e.typed('Timeline Read Cursor', timeline=ref(tid), checkpoint=ref(cid), afterEntry=ref(chosen[-1]))
                page_fields['nextCursor'] = ref(self.e.identity(cursor))
            page = self.e.typed('Timeline Entries Page', **page_fields)
            result = self.e.typed('Timeline Read Response', request=ref(self.e.identity(q)), checkpoint=ref(cid), page=ref(self.e.identity(page)))
            return self.attest(result)

    def create_access(self, owner, timelines, keys, idempotency_key, control, now):
        from access_runtime import access_document
        validate_access_sets(self.e, self.provider, timelines, keys)
        control_id = self.verifier.timeline(control)
        check(self.e.get(control)['publicRead'] and self.state['timelines'][control_id]['owner'] == '__provider__', 'INVALID_CONTROL_TIMELINE')
        for t in timelines:
            check(self.state['timelines'][self.e.identity(t)]['owner'] == owner, 'ACCESS_DENIED')
        with self.lock:
            slot = owner + '/access-create/' + idempotency_key
            access = access_document(self.e, timelines, keys, self.provider, self.e.get(control)['url'])
            aid = self.e.identity(access)
            if slot in self.state['requests']:
                old = self.state['requests'][slot]
                check(old['document'] == aid, 'IDEMPOTENCY_CONFLICT')
                return access, self.e.get(ref(old['entry']))
            if aid in self.state['access']:
                old = self.state['access'][aid]
                check(old['owner'] == owner, 'ACCESS_DENIED')
                self.state['requests'][slot] = {'document': aid, 'entry': old['publication']}
                return access, self.e.get(ref(old['publication']))
            before = self.snapshot()
            try:
                publication = self.append('__provider__', control, access, aid + '/publish', now)
                self.access_execution(access, now + 1)
                entry = self.e.identity(publication)
                self.state['access'][aid] = {'owner': owner, 'document': aid, 'publication': entry, 'lastEntry': entry,
                    'timelines': [self.e.identity(t) for t in timelines], 'keys': list(keys)}
                self.state['requests'][slot] = {'document': aid, 'entry': entry}
                return access, publication
            except Exception:
                self.state = before
                self._runs.pop(aid, None)
                raise

    def update_access(self, owner, access, timelines, keys, idempotency_key, now):
        from access_runtime import control_timeline
        validate_access_sets(self.e, self.provider, timelines, keys)
        aid = self.e.identity(access)
        with self.lock:
            check(aid in self.state['access'], 'NOT_FOUND')
            saved = self.state['access'][aid]
            check(saved['owner'] == owner, 'ACCESS_DENIED')
            for tid in set(saved['timelines']) | {self.e.identity(t) for t in timelines}:
                check(self.state['timelines'][tid]['owner'] == owner, 'ACCESS_DENIED')
            slot = owner + '/access-update/' + idempotency_key
            fingerprint = {'access': aid, 'timelines': [self.e.identity(t) for t in timelines], 'keys': list(keys)}
            if slot in self.state['requests']:
                prior = self.state['requests'][slot]
                check(prior['fingerprint'] == fingerprint, 'IDEMPOTENCY_CONFLICT')
                return self.e.get(ref(prior['entry']))
            arguments = self.e.typed('Timeline Access Update', allowedTimelines=[ref(self.e.identity(t)) for t in timelines], allowedKeys=list(keys))
            call = {'type': 'Contracts/Operation Request', 'document': ref(aid),
                'channel': 'provider', 'operation': 'update', 'request': arguments}
            before = self.snapshot()
            try:
                entry = self.append('__provider__', control_timeline(self.e, access), call, aid + '/' + idempotency_key, now)
                run = self.access_execution(access, now + 1)
                check(run.permissions()['allowedKeys'] == keys, 'INTEGRITY_ERROR')
                saved = self.state['access'][aid]
                saved.update(timelines=fingerprint['timelines'], keys=list(keys), lastEntry=self.e.identity(entry))
                self.state['requests'][slot] = {'fingerprint': fingerprint, 'entry': self.e.identity(entry)}
                return entry
            except Exception:
                self.state = before
                self._runs.pop(aid, None)
                raise
