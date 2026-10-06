"""Bounded syntax-only BlueId memoization; never content or authority evidence."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from algorithms import blue as L

_PLAIN=L.plain_id
_FINAL=L.final_id
_ACTIVE=ContextVar('blue_id_syntax_cache',default=None)


class SyntaxCache:
    def __init__(self, capacity=8192):
        if type(capacity) is not int or capacity<0: raise ValueError('nonnegative capacity required')
        self.capacity=capacity;self.rows=OrderedDict();self.hits=0;self.misses=0

    def read(self, kind, value, reference):
        # Accepted plain IDs are small; unusually long cyclic ordinal strings
        # remain legal but cannot turn bounded entry retention into unbounded bytes.
        if not self.capacity or type(value) is not str or len(value)>128: return reference(value)
        key=(kind,value)
        if key in self.rows:
            self.rows.move_to_end(key);self.hits+=1;return value
        result=reference(value);self.misses+=1;self.rows[key]=None
        while len(self.rows)>self.capacity:self.rows.popitem(last=False)
        return result


@contextmanager
def syntax_scope(cache=None, *, enabled=True):
    token=_ACTIVE.set((cache or SyntaxCache()) if enabled else None)
    try: yield _ACTIVE.get()
    finally:_ACTIVE.reset(token)


def plain_id(value):
    cache=_ACTIVE.get()
    return _PLAIN(value) if cache is None else cache.read('plain',value,_PLAIN)


def final_id(value):
    cache=_ACTIVE.get()
    return _FINAL(value) if cache is None else cache.read('final',value,_FINAL)


L.plain_id=plain_id
L.final_id=final_id
