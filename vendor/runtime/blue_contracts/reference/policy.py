"""Exact selection rule; node validity and subtype relation belong to Language."""
from dataclasses import dataclass
from typing import Callable, Optional, Any
import unicodedata

class GeneralizationError(ValueError):
    """A policy or a permitted ancestor search cannot establish a valid result."""


def pointer_segments(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or unicodedata.normalize('NFC',path)!=path:
        raise GeneralizationError('INVALID_POINTER')
    if path == '':
        return ()
    if not path.startswith('/'):
        raise GeneralizationError('INVALID_POINTER')
    result = []
    for raw in path[1:].split('/'):
        if raw == '':
            raise GeneralizationError('INVALID_POINTER')
        i = 0
        while i < len(raw):
            if raw[i] == '~':
                if i + 1 >= len(raw) or raw[i + 1] not in '01':
                    raise GeneralizationError('INVALID_POINTER')
                i += 2
            else:
                i += 1
        result.append(raw.replace('~1', '/').replace('~0', '~'))
    return tuple(result)


@dataclass(frozen=True)
class GeneralizationRule:
    path: str
    mode: str
    must_remain_subtype_of: Optional[str] = None

    def __post_init__(self) -> None:
        pointer_segments(self.path)
        if self.mode not in ('reject', 'nearest-valid-ancestor'):
            raise GeneralizationError('INVALID_MODE')
        if self.must_remain_subtype_of is not None and not isinstance(self.must_remain_subtype_of, str):
            raise GeneralizationError('INVALID_FLOOR')


@dataclass(frozen=True)
class GeneralizationPolicy:
    rules: tuple[GeneralizationRule, ...] = ()
    default_mode: str = 'reject'

    def __post_init__(self) -> None:
        if self.default_mode not in ('reject', 'nearest-valid-ancestor'):
            raise GeneralizationError('INVALID_MODE')
        if not isinstance(self.rules, tuple):
            raise GeneralizationError('RULES_MUST_BE_IMMUTABLE')
        if any(not isinstance(rule, GeneralizationRule) for rule in self.rules):
            raise GeneralizationError('INVALID_RULE')

    def select(self, path: str) -> GeneralizationRule:
        segments = pointer_segments(path)
        selected = GeneralizationRule('', self.default_mode)
        depth = -1
        for rule in self.rules:
            candidate = pointer_segments(rule.path)
            if len(candidate) > depth and segments[:len(candidate)] == candidate:
                selected, depth = rule, len(candidate)
        return selected


def choose_type(
    current_type: str,
    changed_node: Any,
    path: str,
    policy: GeneralizationPolicy,
    *,
    immediate_ancestor: Callable[[str], Optional[str]],
    valid_with_type: Callable[[Any, str], bool],
    is_subtype: Callable[[str, str], bool],
    charge_candidate: Callable[[str], None] = lambda _: None,
) -> str:
    """Return the unchanged type or the nearest policy-permitted valid ancestor.

    valid_with_type MUST include unchanged local requirements and the exact
    containing context. Missing evidence must raise, not return False. This
    function does not rewrite a node, weaken a schema or issue a checkpoint.
    The owning transaction applies and validates the generated type write.
    """
    rule = policy.select(path)
    seen: set[str] = set()
    candidate: Optional[str] = current_type
    while candidate is not None:
        if candidate in seen:
            raise GeneralizationError('CYCLIC_TYPE_ANCESTRY')
        seen.add(candidate)
        charge_candidate(candidate)
        floor_ok = rule.must_remain_subtype_of is None or is_subtype(candidate, rule.must_remain_subtype_of)
        if floor_ok and valid_with_type(changed_node, candidate):
            return candidate
        if rule.mode == 'reject':
            raise GeneralizationError('TYPE_COMPATIBILITY_VIOLATION')
        if not floor_ok:
            raise GeneralizationError('TYPE_GENERALIZATION_FLOOR')
        candidate = immediate_ancestor(candidate)
    raise GeneralizationError('TYPE_GENERALIZATION_FAILURE')
