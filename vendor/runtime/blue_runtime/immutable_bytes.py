"""Bounded physical sharing of immutable serialized bytes, with no semantic cache."""
from collections import OrderedDict
from threading import RLock


class BytePool:
    def __init__(self, capacity=8192, byte_limit=16*1024*1024):
        if type(capacity) is not int or type(byte_limit) is not int or min(capacity,byte_limit)<0:
            raise ValueError('nonnegative byte-pool bounds required')
        self.capacity,self.byte_limit=capacity,byte_limit
        self.rows=OrderedDict();self.bytes=0;self.hits=0;self.lock=RLock()

    def intern(self, value):
        if type(value) is not bytes:raise TypeError('immutable bytes required')
        if not self.capacity or len(value)<256 or len(value)>self.byte_limit:return value
        with self.lock:
            existing=self.rows.get(value)
            if existing is not None:
                self.rows.move_to_end(existing);self.hits+=1;return existing
            self.rows[value]=value;self.bytes+=len(value)
            while len(self.rows)>self.capacity or self.bytes>self.byte_limit:
                _,old=self.rows.popitem(last=False);self.bytes-=len(old)
            return value
