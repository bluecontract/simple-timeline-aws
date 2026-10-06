"""Operational control flow shared by the stack; never a semantic rejection.

Hosts may retry the same input with the same gas after fixing capacity or
cancellation. This module has no dependency on any Blue semantic layer.
"""
from concurrent.futures import CancelledError
from asyncio import CancelledError as AsyncCancelledError
from functools import wraps


class HostIncomplete(Exception):
    code = 'HOST_INCOMPLETE'

    def __init__(self, reason, **context):
        self.reason = reason
        self.context = {'reason': reason, **context}
        super().__init__(reason)


HOST_FAILURES = (HostIncomplete, MemoryError, RecursionError, CancelledError, AsyncCancelledError)


def incomplete(error):
    if isinstance(error, HostIncomplete):
        return error
    return HostIncomplete(type(error).__name__)


def host_boundary(fn):
    """Convert incidental host failures without manufacturing an Outcome."""
    @wraps(fn)
    def run(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HOST_FAILURES as error:
            raise incomplete(error) from error
    return run
