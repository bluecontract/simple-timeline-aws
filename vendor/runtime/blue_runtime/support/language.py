"""Narrow adapter to the supplied Blue Language 1.0; no second Blue hasher.

ExactValue is a transport record, not a validation capability. Every external
record enters through BlueAccess.verify/admit. View is a transient observation,
never an exact serialization. Contracts documents explicitly use definition
admission because their request/event declarations contain patterns.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import json
from blue_language import Language, AdmittedDocument
from algorithms import blue as L
from .errors import CoordinationError, Code, require

class _Missing:
    def __repr__(self) -> str:
        return 'MISSING'
MISSING = _Missing()

@dataclass(frozen=True)
class ExactValue:
    blue_id: str
    exact_text: str
    goal: str = 'value'

class View:
    def __init__(self, access: 'BlueAccess', recipe: L.Recipe, context: L.Context):
        self.access, self.recipe, self.context = access, recipe, context

    @property
    def head(self) -> L.Head:
        return L.head(self.recipe, self.context)

    @property
    def type_id(self) -> str | None:
        return self.head.type_id

    @property
    def blue_id(self) -> str:
        return L.recipe_exact_id(self.recipe, self.context)

    def field(self, key: str) -> 'View | _Missing':
        h = self.head
        r = h.contracts if key == 'contracts' else h.fields.get(key)
        return MISSING if r is None else View(self.access, r, self.context)

    def optional(self, key: str) -> 'View | _Missing':
        """Return a configured value, not an absent inherited declaration."""
        value=self.field(key)
        if value is MISSING or not L.present_recipe(value.recipe,value.context): return MISSING
        return value

    def need(self, key: str) -> 'View':
        found = self.field(key)
        require(found is not MISSING, Code.REJECTED, f'missing field {key}')
        return found

    def fields(self) -> dict[str, 'View']:
        return {k: View(self.access, r, self.context) for k, r in self.head.fields.items()}

    def items(self) -> tuple['View', ...]:
        h = self.head
        require(h.items is not None, Code.REJECTED, 'expected list')
        requirements = (h.item_type,) if h.item_type else ()
        return tuple(View(self.access, L.recipe(n, requirements=requirements), self.context)
                     for n in h.items)

    def scalar(self) -> Any:
        v = self.head.value
        require(v is not L.ABSENT, Code.REJECTED, 'expected a present scalar')
        return v

    def text(self) -> str:
        v = self.scalar()
        require(type(v) is str, Code.REJECTED, 'expected Text')
        return v

    def integer(self) -> int:
        v = self.scalar()
        require(type(v) is int, Code.REJECTED, 'expected Integer, not Boolean')
        return v

    def exact(self, goal: str = 'definition') -> ExactValue:
        exact = L.recipe_exact_value(self.recipe, self.context)
        # A cyclic member is addressed by its owning set, not a detached body.
        # Keep that reference and its provider proof when handing it to admission.
        node = exact if isinstance(exact, L.Ref) and '#' in exact.id else L.open_exact(exact, self.context)
        text = L.export_exact(node, self.context)
        return self.access.admit(text, mode='exact', goal=goal)

    def source(self) -> Any:
        """Language's exact-to-Source renderer, not a flattened effective view."""
        return L.source_for_exact(L.recipe_exact_value(self.recipe, self.context), self.context)

    def literal_exact(self, goal='definition', *, identity_operand=False) -> ExactValue:
        """Extract a configured operand without labels from its container declaration.

        A repository may describe an Operation's request field. That description
        documents the field; it is not an authored label constraint on payloads.
        All labels actually authored on the operand are retained.
        """
        value=self.source()
        if isinstance(value,dict) and self.recipe.parts:
            latest=L.open_exact(self.recipe.parts[-1],self.context)
            for key in L.LABELS:
                if not latest.has(key):value.pop(key,None)
            if identity_operand:
                # The enclosing field's required/schema rules have already
                # been checked by Language. They are not part of a referenced
                # Timeline/Actor identity. Preserve any authored operand schema.
                if latest.has('schema'):value['schema']=L.source_for_exact(latest.get('schema'),self.context)
                else:value.pop('schema',None)
        return self.access.admit_value(value,goal=goal)

    def plain(self, *, types: bool = False, _active: frozenset = frozenset()) -> Any:
        """Business observation for adapters; never used for content identity."""
        key = self.recipe.key()
        require(key not in _active, Code.UNSUPPORTED_CONTRACTS_FEATURE,
                'recursive view needs graph-aware processor; cannot flatten it')
        h = self.head
        if h.value is not L.ABSENT:
            return h.value
        if h.items is not None:
            return [x.plain(types=types, _active=_active | {key}) for x in self.items()]
        out = {k: v.plain(types=types, _active=_active | {key}) for k, v in self.fields().items()}
        if types and h.type_id:
            out['type'] = {'blueId': h.type_id}
        if h.contracts is not None:
            out['contracts'] = View(self.access, h.contracts, self.context).plain(
                types=types, _active=_active | {key})
        return out

class BlueAccess:
    def __init__(self, language: Language):
        self.language = language
        self._verified: dict[tuple[str, str, str], AdmittedDocument] = {}
        self._admitted_inputs: dict[tuple, ExactValue] = {}
        self._values: dict[tuple[str, str], ExactValue] = {}

    @staticmethod
    def _failure(error: L.Failure) -> CoordinationError:
        code = Code.NEEDS_RESOURCES if error.category in (
            'ProviderUnavailable', 'OperationLimitExceeded') else Code.INVALID_EVIDENCE
        return CoordinationError(code, f'Language {error.category}: {error.detail}')

    def admit(self, value: str | bytes | Any, *, format: str = 'json',
              mode: str = 'source', goal: str = 'value') -> ExactValue:
        text = value if isinstance(value, (str, bytes)) else json.dumps(value, ensure_ascii=False)
        # Reuse an already verified immutable admission, including its bound
        # type/dependency evidence. Source aliases are part of this cache key.
        # This cache never stores provider completeness or authority decisions.
        aliases = tuple(sorted(self.language.aliases.items())) if mode == 'source' else ()
        directives = tuple(sorted(self.language.directive_aliases.items())) if mode == 'source' else ()
        key = (text, format, mode, goal, aliases, directives, repr(getattr(self.language, 'limits', None)))
        if key in self._admitted_inputs:
            return self.verify(self._admitted_inputs[key])
        try:
            doc = self.language.create(text, format=format, mode=mode, goal=goal)
            self.language.publish_document(doc)
        except L.Failure as error:
            raise self._failure(error) from error
        result = ExactValue(doc.blue_id, doc.exact_text, goal)
        self._verified[(result.blue_id, result.exact_text, goal)] = doc
        self._admitted_inputs[key] = result
        self._values.setdefault((result.blue_id, goal), result)
        return result

    def admit_value(self, value: Any, *, mode: str = 'source', goal: str = 'value') -> ExactValue:
        """Admit an in-memory JSON value; a Python string here means Blue Text."""
        return self.admit(json.dumps(value, ensure_ascii=False), mode=mode, goal=goal)

    def verify(self, value: ExactValue) -> ExactValue:
        require(isinstance(value, ExactValue), Code.INVALID_EVIDENCE, 'expected exact content record')
        key = value.blue_id, value.exact_text, value.goal
        if key in self._verified:
            try:
                self.language.create(self._verified[key], goal=value.goal)
            except L.Failure as error:
                raise self._failure(error) from error
        else:
            established = self.admit(value.exact_text, mode='exact', goal=value.goal)
            require(established.blue_id == value.blue_id, Code.INVALID_EVIDENCE,
                    'exact content does not match claimed BlueId')
        return value

    def get(self, blue_id: str, *, goal: str = 'value') -> ExactValue:
        retained = self._values.get((blue_id, goal))
        return self.verify(retained) if retained is not None else self.admit({'blueId': blue_id}, mode='exact', goal=goal)

    def view(self, value: ExactValue) -> View:
        self.verify(value)
        try:
            c = self.language._context()
            n = self.language._input(value.exact_text, c, 'exact', 'json')
            return View(self, L.recipe(n), c)
        except L.Failure as error:
            raise self._failure(error) from error

    def tree(self, value: ExactValue) -> dict[str, Any]:
        """Exact root materialization; nested references remain references."""
        v = self.view(value)
        node = L.open_exact(L.recipe_exact_value(v.recipe, v.context), v.context)
        return L.export_tree(node)

    def at(self, value: ExactValue, pointer: str) -> View:
        current = self.view(value)
        for part in L.path_parts(pointer):
            h = current.head
            if h.items is not None:
                require(part.isdigit() and str(int(part)) == part, Code.REJECTED, 'list pointer')
                values = current.items()
                require(int(part) < len(values), Code.REJECTED, 'list index')
                current = values[int(part)]
            else:
                current = current.need(part)
        return current

    def matches(self, pattern: ExactValue, candidate: ExactValue | _Missing) -> bool:
        """Exact Language specialization predicate for an installed pattern adapter.

        Absence never becomes {} and never receives values inherited from a
        matching pattern. This predicate does not itself select an Operation
        runtime's policy for optional request declarations.
        """
        if candidate is MISSING:
            return False
        self.verify(pattern)
        self.verify(candidate)
        try:
            c = self.language._context()
            p = self.language._input(pattern.exact_text, c, 'exact', 'json')
            v = self.language._input(candidate.exact_text, c, 'exact', 'json')
            L.strict_certify(v, c, 'value')
            return L.preserves_heads(L.head(L.recipe(v), c), L.head(L.recipe(p), c), c)
        except L.Failure as error:
            if error.category in ('SchemaViolation', 'TypeCompatibilityViolation'):
                return False
            raise self._failure(error) from error
