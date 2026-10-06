"""Storage-independent operation compositions for Blue Language 1.0.

These procedures compose the unchanged normative algorithms. Results are ordinary
semantic records, not authentication receipts or library-issued trust tickets.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from algorithms import blue as B


@dataclass(frozen=True)
class AdmissionResult:
    blue_id: str
    original_blue_id: str
    goal: str
    exact_text: str
    canonical_text: str
    removed_fields: tuple[str, ...]
    dependency_records_json: str

    def dependency_responses(self) -> dict:
        """Return a defensive copy of the reference evidence carrier."""
        return json.loads(self.dependency_records_json)


def read_input(text, context, *, mode="source", format="json"):
    """Decode an explicitly selected input role; never guess a fallback role."""
    with B.error_scope(context, phase="parsing"):
        parsed = B.parse(text, format, context.limits)
    if mode == "source":
        return B.prepare_source(parsed, context)
    if mode == "canonical":
        return B.decode_canonical(parsed, context)
    B.require(mode in ("exact", "direct"), "InvalidOperation", "input role")
    return B.normalize(parsed, context, mode)


def admit_document(text, context, *, goal="value", mode="source", format="json"):
    """Construct or decode, validate, normalize permitted duplicates, and export.

    The context is an operation-local fixed environment. No persistent provider
    write occurs here. Authentication or reuse of this result is a host boundary.
    """
    try:
        with B.error_scope(context, "", "operation"):
            context.diagnostic_goal = goal
            exact = read_input(text, context, mode=mode, format=format)
            context.diagnostic_root = exact
            original_id = B.identity(exact)
            B.strict_certify(exact, context, goal)
            if mode == "source":
                exact, removed = B.omit_root_duplicates(exact, context)
            else:
                removed = ()
            if removed:
                B.strict_certify(exact, context, goal)
            exact_text = B.export_exact(exact, context)
            compact_text = B.canonical_export(exact, context)
            records = B.admitted_records(exact, context)
            return AdmissionResult(
                B.identity(exact), original_id, goal, exact_text, compact_text,
                tuple(removed),
                json.dumps(records, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False),
            )
    except RecursionError as error:
        raise B.Failure("OperationLimitExceeded", "recursion") from error


def admit_source(text, context, *, goal="value", format="json"):
    return admit_document(text, context, goal=goal, mode="source", format=format)


def admit_exact(text, context, *, goal="value", format="json"):
    return admit_document(text, context, goal=goal, mode="exact", format=format)


def admit_canonical(text, context, *, goal="value", format="json"):
    return admit_document(text, context, goal=goal, mode="canonical", format=format)


def admit_direct(text, context, *, goal="value", format="json"):
    return admit_document(text, context, goal=goal, mode="direct", format=format)
