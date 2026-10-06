"""Closed Coordination outcomes; diagnostic text is informative."""
from __future__ import annotations
from enum import StrEnum
from dataclasses import dataclass

class Code(StrEnum):
    NEEDS_RESOURCES = 'NEEDS_RESOURCES'
    INVALID_EVIDENCE = 'INVALID_EVIDENCE'
    INVALID_CHECKPOINT_EVIDENCE = 'INVALID_CHECKPOINT_EVIDENCE'
    UNSUPPORTED_COORDINATION_TYPE = 'UNSUPPORTED_COORDINATION_TYPE'
    INCOMPATIBLE_COORDINATION_TYPES = 'INCOMPATIBLE_COORDINATION_TYPES'
    INCOMPATIBLE_FRONTIER = 'INCOMPATIBLE_FRONTIER'
    REJECTED = 'REJECTED'
    WITHHELD = 'WITHHELD'
    CONFLICT = 'CONFLICT'
    GAS_LIMIT_EXCEEDED = 'GAS_LIMIT_EXCEEDED'
    PORTABLE_LIMIT_EXCEEDED = 'PORTABLE_LIMIT_EXCEEDED'
    UNSUPPORTED_CONTRACTS_FEATURE = 'UNSUPPORTED_CONTRACTS_FEATURE'
    FAILED = 'FAILED'

class CoordinationError(Exception):
    def __init__(self, code: Code | str, detail: str = ''):
        self.code = Code(code)
        self.detail = detail
        super().__init__(f'{self.code}: {detail}')

class Acquisition(StrEnum):
    COMPLETE = 'COMPLETE'
    COMPLETE_EMPTY = 'COMPLETE_EMPTY'
    DEFERRED_UNAVAILABLE = 'DEFERRED_UNAVAILABLE'
    NOT_FOUND = 'NOT_FOUND'
    INVALID_EVIDENCE = 'INVALID_EVIDENCE'
    INCOMPATIBLE_FRONTIER = 'INCOMPATIBLE_FRONTIER'

class Eligibility(StrEnum):
    ELIGIBLE_DIRECT = 'ELIGIBLE_DIRECT'
    ELIGIBLE_MANDATE = 'ELIGIBLE_MANDATE'
    NO_MATCH = 'NO_MATCH'
    STALE = 'STALE'
    REJECTED = 'REJECTED'
    WITHHELD = 'WITHHELD'
    DEFERRED_UNAVAILABLE = 'DEFERRED_UNAVAILABLE'
    INVALID_EVIDENCE = 'INVALID_EVIDENCE'
    UNSUPPORTED = 'UNSUPPORTED'

TERMINAL = frozenset({Eligibility.NO_MATCH, Eligibility.STALE,
                      Eligibility.REJECTED, Eligibility.WITHHELD})
ADMITTED = frozenset({Eligibility.ELIGIBLE_DIRECT, Eligibility.ELIGIBLE_MANDATE})

class Newness(StrEnum):
    NEW = 'NEW'
    STALE = 'STALE'
    NEW_WITH_CHECKPOINT_RESET = 'NEW_WITH_CHECKPOINT_RESET'

class MandateOutcome(StrEnum):
    ELIGIBLE = 'ELIGIBLE'
    INELIGIBLE = 'INELIGIBLE'
    DEFERRED_UNAVAILABLE = 'DEFERRED_UNAVAILABLE'
    INVALID_EVIDENCE = 'INVALID_EVIDENCE'
    AMBIGUOUS = 'AMBIGUOUS'

def require(condition: bool, code: Code | str, detail: str) -> None:
    if not condition:
        raise CoordinationError(code, detail)
