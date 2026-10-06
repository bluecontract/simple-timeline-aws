"""Opt-in physical acceleration; no normative source or gas schedule changes.

A context-local bounded weak memo caches ordinary immutable node identities.
Cyclic token-context identity always uses the reference. Unicode checking uses
Python's strict encoder for plain strings, with identical diagnostics. Neither
operation consumes Language steps or Contracts gas in the selected reference.
"""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from dataclasses import replace, fields
from fractions import Fraction
import copy
import weakref
import sys
from threading import RLock
from algorithms import blue as L

_REFERENCE_IDENTITY=L.identity
_REFERENCE_UNICODE=L.checked_unicode
_REFERENCE_COPY_HEAD=L.copy_head
_REFERENCE_EXPORT=L.export_exact
_ACTIVE=ContextVar('blue_physical_optimization',default=None)
_DEPTH=ContextVar('blue_identity_memo_depth',default=0)

def immutable(node):
    # Admission/parser paths use tuples, but low-level callers can supply
    # a mutable list inside a frozen Node. Prove eligibility on a miss;
    # warm lookups remain O(1), without hashing or traversing the subtree.
    pending=[node];seen=set()
    while pending:
        value=pending.pop();kind=type(value)
        if kind in (str,int,float,bool,type(None)):continue
        if kind is L.Ref:
            if type(value.id) is not str:return False
            continue  # The optional body does not participate in identity.
        if kind not in (L.Node,tuple):return False
        key=id(value)
        if key in seen:continue
        seen.add(key)
        if kind is L.Node:
            if type(value.fields) is not tuple:return False
            pending.append(value.fields)
        else:pending.extend(value)
    return True

class PhysicalCache:
    def __init__(self,capacity=8192):
        if type(capacity) is not int or capacity<0:raise ValueError('nonnegative capacity required')
        self.capacity=capacity;self.entries=OrderedDict();self.shared=OrderedDict();self.hits=0;self.misses=0
        self.exports=OrderedDict();self.export_bytes=0;self.export_hits=0
        # Cache only the pure exact-wire decode/identity check, never admission.
        self.roundtrips=OrderedDict();self.roundtrip_bytes=0
        self.roundtrip_hits=0;self.roundtrip_misses=0
        self.roundtrip_byte_limit=16*1024*1024
        self._roundtrip_lock=RLock()
    def clear(self):
        self.entries.clear();self.shared.clear();self.exports.clear();self.export_bytes=0
        with self._roundtrip_lock:
            self.roundtrips.clear();self.roundtrip_bytes=0
    def shareable(self, node):
        pending=[node];seen=set();proven=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind in (str,int,float,bool,type(None)):continue
            if kind is tuple:pending.extend(value);continue
            if kind not in (L.Node,L.Ref,L.Local):return False
            key=id(value)
            if key in seen:continue
            seen.add(key)
            old=self.shared.get(key)
            if old is not None and old() is value:continue
            proven.append(value)
            if kind is L.Node:
                if type(value.fields) is not tuple:return False
                pending.append(value.fields)
            elif kind is L.Ref:
                if type(value.id) is not str:return False
                pending.append(value.body)
            elif type(value.index) is not int:return False
        for value in proven:self.shared[id(value)]=weakref.ref(value)
        while len(self.shared)>self.capacity:self.shared.popitem(last=False)
        return True
    def identity(self,node):
        if not self.capacity:return _REFERENCE_IDENTITY(node)
        key=id(node);old=self.entries.get(key)
        if old is not None and old[0]() is node:
            self.entries.move_to_end(key);self.hits+=1;return old[1]
        depth=_DEPTH.get()
        if depth>=32:
            # Do not spend Python's recursion budget on cache wrappers. Deep
            # subtrees use the reference's original stack depth unchanged.
            token=_ACTIVE.set(None)
            try:result=_REFERENCE_IDENTITY(node)
            finally:_ACTIVE.reset(token)
        else:
            token=_DEPTH.set(depth+1)
            try:result=_REFERENCE_IDENTITY(node)
            finally:_DEPTH.reset(token)
        self.misses+=1
        if not immutable(node):return result
        owner=weakref.ref(self)
        def remove(ref):
            cache=owner()
            if cache is not None and key in cache.entries and cache.entries[key][0] is ref:cache.entries.pop(key)
        self.entries[key]=(weakref.ref(node,remove),result)
        while len(self.entries)>self.capacity:self.entries.popitem(last=False)
        return result
    @contextmanager
    def scope(self):
        token=_ACTIVE.set(self)
        try:yield self
        finally:_ACTIVE.reset(token)
    def stats(self):return dict(capacity=self.capacity,retained=len(self.entries),hits=self.hits,misses=self.misses)

def identity(node,token=None):
    cache=_ACTIVE.get()
    if cache is not None and token is None and type(node) is L.Node:return cache.identity(node)
    return _REFERENCE_IDENTITY(node,token)

def checked_unicode(value):
    if _ACTIVE.get() is None or type(value) is not str:return _REFERENCE_UNICODE(value)
    if not value.isascii():
        try:value.encode('utf-8','strict')
        except UnicodeEncodeError:L.require(False,'InvalidSyntax','unpaired surrogate')
    return value

def copy_head(head):
    """Copy mutable containers while sharing proven immutable scalar facets.

    The reference deep-copies Constraints on every effective-head lookup. Bounds,
    fractions and finite scalar alternatives are immutable; their dictionaries
    are the only mutable children in a normally constructed Constraint.
    Unusual low-level caller values retain the reference path.
    """
    if _ACTIVE.get() is None or type(head.constraints) is not L.Constraint:
        return _REFERENCE_COPY_HEAD(head)
    c = head.constraints
    def bound(value):
        return value is None or (type(value) is L.Bound and type(value.value) is Fraction and type(value.exclusive) is bool)
    if (not all(type(v) is int for v in c.counts.values()) or not bound(c.lower) or not bound(c.upper)
        or type(c.lower_facets) is not tuple or type(c.upper_facets) is not tuple
        or not all(bound(v) for v in c.lower_facets + c.upper_facets)
        or c.multiple is not None and type(c.multiple) is not Fraction
        or c.enum is not None and (type(c.enum) is not tuple or not all(type(g) is frozenset and all(type(k) is str for k in g) for g in c.enum))
        or not all(type(v) is tuple and all(type(x) in (str,int,float,bool,type(None)) for x in v) for v in c.enum_values.values())):
        return _REFERENCE_COPY_HEAD(head)
    constraints = L.Constraint(c.required, c.unique, dict(c.counts), c.lower, c.upper,
        c.lower_facets, c.upper_facets, c.multiple, c.enum, dict(c.enum_values))
    return replace(head, labels=dict(head.labels), fields=dict(head.fields), constraints=constraints)

def deepcopy_node(value, memo):
    cache = _ACTIVE.get()
    if cache is not None and cache.capacity and cache.shareable(value):
        memo[id(value)] = value
        return value
    # Exactly the standard deepcopy reconstruction path for these dataclasses.
    # Mutable low-level fields and inactive contexts retain ordinary copying.
    return copy._reconstruct(value, memo, *value.__reduce_ex__(4))

def _checked_export(cache, node, context):
    """Memoize the independent round-trip of identical exact output bytes.

    Canonicalization still runs on every miss in the existing handle cache,
    including its caller-context type retention. Only parse/normalize/identity
    of the output in a NEW, provider-independent Context is reusable. Its key
    includes every parser/normalizer limit. A successful round-trip is not
    semantic or contextual admission, nor authority for an unknown reference.

    The text itself, not just its BlueId, is the key: different legal storage
    projections of the same node can have different exact output bytes.
    """
    context = context or L.Context()
    normalized = L.canonicalize_node(node, context)
    text = L.wire_text(L.export_tree(normalized))
    limit_key = tuple(getattr(context.limits, f.name) for f in fields(context.limits))
    key = (limit_key, text)
    with cache._roundtrip_lock:
        record = cache.roundtrips.get(key)
        if record is not None:
            cache.roundtrips.move_to_end(key)
            cache.roundtrip_hits += 1
    if record is None:
        # Keep the same independent parser, normalizer and identity algorithm.
        # No rejected/partial computation is entered in the memo.
        rebuilt = L.normalize(L.parse(text, limits=context.limits),
                              L.Context(limits=context.limits))
        decoded_identity = L.identity(rebuilt)
        cache.roundtrip_misses += 1
    else:
        decoded_identity = record[0]
    L.require(decoded_identity == L.identity(normalized),
              'InternalError', 'export changed identity')
    if record is None:
        # Count retained strings, tuples and a conservative per-entry allowance;
        # entry count also caps dict/LRU overhead. No bodies or contexts retained.
        size = (sys.getsizeof(text) + sys.getsizeof(decoded_identity)
                + sys.getsizeof(limit_key) + sys.getsizeof(key) + 256)
        with cache._roundtrip_lock:
            old = cache.roundtrips.pop(key, None)
            if old is not None:
                cache.roundtrip_bytes -= old[1]
            if cache.capacity and size <= cache.roundtrip_byte_limit:
                cache.roundtrips[key] = (decoded_identity, size)
                cache.roundtrip_bytes += size
            while (len(cache.roundtrips) > cache.capacity
                   or cache.roundtrip_bytes > cache.roundtrip_byte_limit):
                _, old = cache.roundtrips.popitem(last=False)
                cache.roundtrip_bytes -= old[1]
    return text


def export_exact(node, context=None):
    """Bounded exact-text reuse for immutable, already normalized nodes.

    These nodes contain Ref values in every type slot. Thus canonicalize_node
    has no remember side effect on its caller's context. Export does not open
    provider content or spend that context's steps. Its independent round-trip
    validation is bound to every parse/normalization limit, including steps.
    Inline type Nodes and unusual mutable low-level values use the reference.
    """
    cache = _ACTIVE.get()
    if cache is None or not cache.capacity or type(node) is not L.Node:
        return _REFERENCE_EXPORT(node, context)
    limits = context.limits if context is not None else L.Limits()
    key = (id(node), tuple(getattr(limits, f.name) for f in fields(limits)))
    old = cache.exports.get(key)
    if old is not None and old[0]() is node:
        cache.exports.move_to_end(key);cache.export_hits += 1
        return old[1]
    text = _checked_export(cache, node, context)
    if not immutable(node): return text
    pending = [node];seen = set()
    while pending:
        current = pending.pop()
        if type(current) is L.Ref: continue
        if type(current) is not L.Node: return text
        if id(current) in seen: continue
        seen.add(id(current))
        for field, value in current.fields:
            if field in L.TYPES:
                if type(value) is not L.Ref: return text
            elif field == 'items': pending.extend(value)
            elif field not in L.LITERALS | {'mergePolicy'}: pending.append(value)
    size = len(text.encode('utf-8'))
    if size > 16 * 1024 * 1024: return text
    if old is not None: cache.export_bytes -= old[2]
    cache.exports[key] = (weakref.ref(node), text, size)
    cache.export_bytes += size
    while len(cache.exports) > cache.capacity or cache.export_bytes > 16 * 1024 * 1024:
        _, entry = cache.exports.popitem(last=False);cache.export_bytes -= entry[2]
    return text

# Inactive calls execute the original functions. ContextVar prevents enabling
# another thread/workspace merely because one processor opted into acceleration.
L.identity=identity
L.checked_unicode=checked_unicode
L.copy_head=copy_head
L.export_exact=export_exact
L.Node.__deepcopy__=deepcopy_node
L.Ref.__deepcopy__=deepcopy_node
L.Local.__deepcopy__=deepcopy_node

@contextmanager
def reference_scope():
    """Run an independent reference comparison even inside an optimized host."""
    token=_ACTIVE.set(None)
    try:yield
    finally:_ACTIVE.reset(token)
