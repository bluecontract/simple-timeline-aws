"""Blue Language 1.0 Python reference implementation.

The public facade always starts an operation with fresh counters and semantic
state. Exact provider bodies persist; a previous validation is never silently
reused as proof of a different invocation.
"""
from .api import Language, MemoryProvider, AdmittedDocument
from algorithms.blue import Failure, Limits, CORE
__all__ = ['Language', 'MemoryProvider','AdmittedDocument', 'Failure', 'Limits', 'CORE']
__version__ = '1.0.0'
