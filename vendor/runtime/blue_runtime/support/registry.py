"""Exact type dispatch and explicit specification compatibility."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .language import BlueAccess, ExactValue, View, MISSING
from .errors import Code, require

@dataclass(frozen=True)
class RuntimeBinding:
    type_blue_id: str
    specification_blue_id: str
    role: str
    implementation: Any = None
    coordination: bool = True

class RuntimeRegistry:
    def __init__(self, blue: BlueAccess, specification_blue_id: str):
        self.blue = blue
        self.specification_blue_id = specification_blue_id
        self._bindings: dict[str, RuntimeBinding] = {}

    def install(self, definition: ExactValue, role: str, implementation: Any = None,
                *, specification: str | None = None) -> None:
        self.blue.verify(definition)
        view = self.blue.view(definition)
        spec = view.need('specification').blue_id
        expected = specification or self.specification_blue_id
        require(spec == expected, Code.INCOMPATIBLE_COORDINATION_TYPES, 'type specification mismatch')
        require(definition.blue_id not in self._bindings, Code.INVALID_EVIDENCE, 'duplicate exact runtime binding')
        self._bindings[definition.blue_id] = RuntimeBinding(definition.blue_id, spec, role, implementation)

    def install_extension(self, definition: ExactValue, role: str, implementation: Any,
                          *, specification: str) -> None:
        """Install an explicit different-spec runtime, never another Core version.

        The Contracts inspector must invoke this adapter to prove its source,
        ordering, evidence and checkpoint projections. This is not permission
        to interpret an unknown contract by its descriptive fields.
        """
        require(specification != self.specification_blue_id and implementation is not None,
                Code.INVALID_EVIDENCE, 'extension needs a distinct exact specification and adapter')
        self.blue.verify(definition)
        require(self.blue.view(definition).need('specification').blue_id == specification,
                Code.INCOMPATIBLE_COORDINATION_TYPES, 'extension specification mismatch')
        require(definition.blue_id not in self._bindings, Code.INVALID_EVIDENCE, 'duplicate exact runtime binding')
        self._bindings[definition.blue_id] = RuntimeBinding(
            definition.blue_id, specification, role, implementation, False)

    def lookup(self, type_blue_id: str | None, *, required: bool = True) -> RuntimeBinding | None:
        binding = self._bindings.get(type_blue_id)
        if binding is None:
            require(not required, Code.UNSUPPORTED_COORDINATION_TYPE, f'no exact runtime for {type_blue_id}')
            return None
        require(not binding.coordination or binding.specification_blue_id == self.specification_blue_id,
                Code.INCOMPATIBLE_COORDINATION_TYPES, 'participating runtimes select different specifications')
        return binding

    def role(self, value: View | ExactValue, *, required: bool = True) -> str | None:
        view = value if isinstance(value, View) else self.blue.view(value)
        found = self.lookup(view.type_id, required=required)
        return None if found is None else found.role

    def expect(self, value: View | ExactValue, role: str) -> RuntimeBinding:
        view = value if isinstance(value, View) else self.blue.view(value)
        binding = self.lookup(view.type_id)
        require(binding.role == role, Code.UNSUPPORTED_COORDINATION_TYPE,
                f'exact type is {binding.role}, not {role}')
        return binding

    def unknown_contract_is_inert(self, value: View) -> bool:
        """Only truly unrelated, unused contracts can remain inert."""
        if value.type_id is None:
            return True
        if self.lookup(value.type_id, required=False) is not None:
            return False
        definition = self.blue.view(self.blue.get(value.type_id, goal='definition'))
        spec = definition.field('specification')
        require(spec is MISSING or spec.blue_id != self.specification_blue_id,
                Code.UNSUPPORTED_COORDINATION_TYPE, 'uninstalled Coordination contract type')
        return True
