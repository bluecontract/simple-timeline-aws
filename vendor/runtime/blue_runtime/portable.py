"""Host replay capsules retaining provider evidence for runtime-created references.

A BEX program can construct a BlueId from Text. That content need not be reachable
from the original document or event. The reference's minimal export alone does
not retain it. This host export uses the same checked capsule format and commits
the starting provider inventory as extra evidence. Imported records remain
untrusted until exact opening/admission; no processor identity or gas is changed.
"""
from blue_contracts import export_invocation as reference_export
from blue_contracts.reference.model import digest
from .core_reuse import export_collection


def export_invocation(engine,snapshot,event,eventTimestamp):
    with export_collection():
        package=reference_export(engine,snapshot,event,eventTimestamp)
    invocation=package['invocation']
    invocation['content']={**engine.blue.language.provider.snapshot(),**invocation['content']}
    package['identity']=digest('contracts.capsule/completion-1',invocation)
    return package
