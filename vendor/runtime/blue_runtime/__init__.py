"""Current Runner facade and preserved legacy Stack compatibility."""
__all__ = ['Runner','LegacyStack','LegacyDurableStack','Stack','DurableStack']

def __getattr__(name):
    if name == 'Runner':
        from blue_coordination.runner import Runner
        return Runner
    if name in ('Stack', 'LegacyStack'):
        from .stack import Stack
        return Stack
    if name in ('DurableStack', 'LegacyDurableStack'):
        from .durable import DurableStack
        return DurableStack
    raise AttributeError(name)
