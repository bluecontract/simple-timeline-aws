"""Opt-in processor acceleration using the independent Language memo.
"""
from functools import wraps
from blue_contracts import Processor
from .record_bridge import install_record_bridge
from .core_reuse import CoreReuse
from blue_language.physical import PhysicalCache, reference_scope, _REFERENCE_IDENTITY, _REFERENCE_UNICODE

def accelerated(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        with self.physical_cache.scope(), self.core_reuse.scope():return method(self,*args,**kwargs)
    return call

class OptimizedProcessor(Processor):
    def __init__(self,language=None,*,gas_limit=100000,local_limits=None,cache_capacity=8192):
        self.physical_cache=PhysicalCache(cache_capacity)
        self.core_reuse=CoreReuse(cache_capacity)
        with self.physical_cache.scope():
            super().__init__(language,gas_limit=gas_limit,local_limits=local_limits)
            install_record_bridge(self)
    admit=accelerated(Processor.admit)
    initialize=accelerated(Processor.initialize)
    create=accelerated(Processor.create)
    validate=accelerated(Processor.validate)
    process=accelerated(Processor.process)
    read=accelerated(Processor.read)
    emitted=accelerated(Processor.emitted)
