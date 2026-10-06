"""Explicit execution profile for a verified subset of the pinned catalogue.

This adapter does NOT assert complete Java parity. Runtime roles are installed
against exact IDs from a separately bound profile; descriptive names never
select a runtime for an arbitrary external document.
"""
from __future__ import annotations
import json
from pathlib import Path
from blue_language import Language
from blue_contracts.catalogue import Catalogue, COORDINATION, CONTRACTS
from blue_runtime.support.language import BlueAccess
from blue_runtime.support.registry import RuntimeRegistry, RuntimeBinding
from . import bundled
from .api import Repository, RepositoryError, digest

# These are deliberately limited to runtimes implemented by this Python host.
SUPPORTED = {
    'Coordination/Timeline': 'timeline', 'MyOS/MyOS Timeline': 'timeline',
    'Coordination/Actor': 'actor', 'MyOS/Principal Actor': 'actor',
    'Coordination/Source': 'source', 'Coordination/Timeline Entry': 'timeline_entry',
    'Coordination/Timeline Channel': 'timeline_channel',
    'Coordination/Composite Timeline Channel': 'composite_channel',
    'Coordination/All Timelines Channel': 'all_timelines_channel',
    'Coordination/Operation Request': 'operation_request',
    'Coordination/Operation': 'operation',
    'Coordination/Sequential Workflow Operation': 'operation',
    'Coordination/Sequential Workflow': 'workflow',
    'Coordination/Compute': 'compute', 'Coordination/Trigger Event': 'trigger_event',
    'Coordination/Update Document': 'update_document', 'Coordination/Event': 'event',
    'Coordination/Actor Policy': 'actor_policy', 'Coordination/Authority': 'authority',
    **CONTRACTS,
    'Embedded Collection Event Channel': 'embedded_collection_channel',
}
# Catalogue expects this convenience name although it is not a Java type.
LOCAL_ONLY = {
    'Reference/Completeness Evidence': 'completeness_evidence',
    'Reference/Mandate Resolution Evidence': 'mandate_evidence',
    'Document Processing Fatal Error': 'fatal_event',
    'Coordination/Terminate Processing': 'terminate_step',
}


class ProfileRegistry(RuntimeRegistry):
    """A closed exact-ID allowlist, bound to the imported repository profile."""
    def __init__(self, blue, specification_blue_id, expected):
        super().__init__(blue, specification_blue_id)
        self._expected = dict(expected)
        self.profile_identity = digest({'format': 'blue-python-runtime-profile/1',
                                       'specification': specification_blue_id,
                                       'bindings': self._expected})

    def install_profile(self, definition, role):
        self.blue.verify(definition)
        if self._expected.get(definition.blue_id) != role:
            raise RepositoryError('type is not in the closed execution profile')
        if definition.blue_id in self._bindings:
            raise RepositoryError('duplicate execution-profile binding')
        self._bindings[definition.blue_id] = RuntimeBinding(
            definition.blue_id, self.specification_blue_id, role,
            {'adapterProfile': self.profile_identity}, True)


class RepositoryCatalogue(Catalogue):
    def __init__(self, language: Language | None = None, *, repository: Repository | None = None):
        self.repository = bundled() if repository is None else repository
        self.language = Language(core_contracts=False) if language is None else language
        self.language.enable_repository(self.repository)
        self.blue = BlueAccess(self.language)
        self.types, self.specs, self._contract_cache = {}, {}, {}
        base = Path(__file__).resolve().parents[1] / 'blue_contracts/resources/specifications'
        for layer in ('bex', 'contracts', 'coordination'):
            self.specs[layer] = self.blue.admit_value(((Path(__file__).resolve().parents[1]/'blue_contracts/LEGACY_SPECIFICATION.md') if layer=='contracts' else base/layer/'SPECIFICATION.md').read_text(encoding='utf-8'))
        aliases = self.repository.aliases
        expected = {aliases[name]: role for name,role in SUPPORTED.items() if name in aliases}
        self.registry = ProfileRegistry(self.blue, self.specs['coordination'].blue_id, expected)
        for name, role in SUPPORTED.items():
            if name not in aliases: continue
            definition = self.blue.get(aliases[name], goal='definition')
            self.registry.install_profile(definition, role)
            self.types[name] = definition
        for name,role in LOCAL_ONLY.items():
            if name in self.types: continue
            definition = self.blue.admit({'name': name,
                'specification': {'blueId': self.specs['coordination'].blue_id}}, goal='definition')
            self.registry.install(definition,role)
            self.types[name] = definition
            self.language.aliases[name] = definition.blue_id

    def initialization_value(self, name, before):
        # Preserve the exact pre-initialization document, not its ID as Text.
        return self.typed(name, document={'blueId':before})

    def checkpoint_value(self, entry_blue_id):
        # Reference checkpoint-domain profile, not a claim of Java domain parity.
        return {'domain': self.registry.profile_identity, 'subject': {'blueId':entry_blue_id}}
