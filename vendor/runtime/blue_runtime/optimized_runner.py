"""Experimental Coordination host with context-local physical acceleration."""
from functools import wraps
from blue_coordination import Runner
from .optimization import PhysicalCache,reference_scope

def scoped(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        with self.physical_cache.scope():return method(self,*args,**kwargs)
    return call

class OptimizedRunner(Runner):
    def __init__(self,language=None,*,cache_capacity=8192):
        self.physical_cache=PhysicalCache(cache_capacity)
        with self.physical_cache.scope():super().__init__(language)
    def replay(self,invocation):
        with reference_scope():return super().replay(invocation)

for _name in ('sync_sources','prepare_source','prepare_graph','decision','plan','advance','admit','export','restore'):
    setattr(OptimizedRunner,_name,scoped(getattr(Runner,_name)))
