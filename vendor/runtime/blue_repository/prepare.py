"""Standalone preparation: repository data in, Language-compatible data out.

No Contracts, BEX, Coordination, Workbench or runtime-role dependency.
"""
from __future__ import annotations
import hashlib
import json
from algorithms import blue as B
from blue_language.prepared import binding
from blue_language.physical import PhysicalCache


def prepare(repository):
    """Compile a structurally verified Repository; never certify all its types.

    Invalid semantic definitions remain available but fail normal admission.
    All exact exports below are independently checked by the reference code.
    """
    from .api import Repository
    if not isinstance(repository, Repository): raise TypeError('expected verified Repository')
    records = repository.records
    rows, shapes, opens = [], {}, {}
    objects = {}

    def encode(value):
        if type(value) is B.Node: return ('node', intern(value))
        if type(value) is B.Ref: return ('ref', value.id)
        if type(value) is tuple: return ('tuple', tuple(encode(v) for v in value))
        if type(value) is int: return ('int', str(value))
        if type(value) is float: return ('float', repr(value))
        if type(value) in (str, bool, type(None)): return ('literal', value)
        raise TypeError('not immutable exact data: ' + type(value).__name__)

    def intern(node):
        previous = objects.get(id(node))
        if previous is not None and previous[0] is node: return previous[1]
        fields = tuple((k, encode(v)) for k, v in node.fields)
        index = shapes.get(fields)
        if index is None:
            context = B.Context()
            exact = B.export_exact(node, context)
            verification = B.Context()
            restored = B.normalize(B.parse(exact), verification)
            B.require(B.identity(restored) == B.identity(node), 'InternalError', 'prepared export changed identity')
            remembered = [intern(v) for v in context.bodies.values()]
            index = len(rows)
            rows.append({'fields': fields, 'blueId': B.identity(node), 'exact': exact,
                         'exportSteps': verification.work, 'remember': remembered})
            shapes[fields] = index
        objects[id(node)] = (node, index)
        # List payloads are exported separately by admitted_records.
        for key, value in node.fields:
            if key == 'items' and len(node.fields) != 1: intern(B.list_node(value))
        return index

    with PhysicalCache(65536).scope():
        for tid, response in sorted(records.items()):
            context = B.Context(provider=records)
            body = B.open_exact(B.Ref(tid), context)
            index = intern(body)
            # Cyclic proof verification remains on the reference path. Its
            # publication bytes are prepared, but not its contextual proof work.
            if '#' in tid: continue
            if response.get('mode', 'exact') != 'exact' or 'environment' in response: continue
            variants = [response, {'text': rows[index]['exact'], 'mode': 'exact'}]
            for variant in variants:
                if any(v['response'] == variant for v in opens.get(tid, ())): continue
                c = B.Context(provider={tid: variant})
                n = B.open_exact(B.Ref(tid), c)
                row = {'response': variant, 'body': intern(n), 'steps': c.work,
                       'remember': [(key, intern(value)) for key, value in sorted(c.bodies.items())]}
                opens.setdefault(tid, []).append(row)
    payload = {'binding': binding(), 'repository': json.loads(repository._json),
               'nodes': rows, 'opens': opens}
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    return data, hashlib.sha256(data).hexdigest()
