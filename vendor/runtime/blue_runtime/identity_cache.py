"""Bounded, weak identity memo for immutable ordinary Language nodes.

Host optimization only: the normative identity algorithm is unchanged. No
resolver/admission evidence is cached here, and cyclic token contexts never
enter this API. Keys do not recursively hash a subtree or retain its graph.
"""
from collections import OrderedDict
import weakref
from algorithms import blue as L


class IdentityCache:
    def __init__(self,capacity=1024):
        if type(capacity) is not int or capacity<0:raise ValueError('nonnegative capacity required')
        self.capacity=capacity;self.entries=OrderedDict();self.hits=0;self.misses=0

    def clear(self):self.entries.clear()

    @staticmethod
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

    def identity(self,node):
        if not self.capacity or type(node) is not L.Node:return L.identity(node)
        key=id(node);row=self.entries.get(key)
        if row is not None and row[0]() is node:
            self.entries.move_to_end(key);self.hits+=1;return row[1]
        # Failed calculations, including a Local outside token context, are not
        # cached. The original algorithm performs exactly the same validation.
        result=L.identity(node);self.misses+=1
        if not self.immutable(node):return result
        owner=weakref.ref(self)
        def remove(ref):
            cache=owner()
            if cache is not None and key in cache.entries and cache.entries[key][0] is ref:
                cache.entries.pop(key)
        self.entries[key]=(weakref.ref(node,remove),result);self.entries.move_to_end(key)
        while len(self.entries)>self.capacity:self.entries.popitem(last=False)
        return result
