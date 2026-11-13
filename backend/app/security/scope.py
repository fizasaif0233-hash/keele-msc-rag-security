"""Resolve which document identifiers a retrieval call is allowed to search.

The secured configuration intersects the request with the caller's authorised set.
The baseline configuration does not. An empty secured scope must stay empty: it
must never fall through to the full corpus.
"""

from uuid import UUID


def resolve_document_scope(
    *,
    configuration: str,
    requested_ids: set[UUID] | None,
    authorised_ids: set[UUID],
    all_ready_ids: set[UUID],
) -> tuple[set[UUID], list[str]]:
    decisions: list[str] = []
    ready = set(all_ready_ids)
    authorised = set(authorised_ids) & ready

    if configuration == "baseline":
        if requested_ids is not None:
            scope = set(requested_ids) & ready
            denied = scope - authorised
            if denied:
                decisions.append("baseline_included_unauthorised_ids")
            decisions.append("baseline_requested_scope")
            return scope, decisions
        decisions.append("baseline_full_corpus")
        return ready, decisions

    if requested_ids is not None:
        requested = set(requested_ids)
        denied = (requested & ready) - authorised
        if denied:
            decisions.append("denied_unauthorised_document_ids")
        scope = requested & authorised
        decisions.append("secured_requested_scope")
        return scope, decisions

    decisions.append("secured_authorised_only")
    return authorised, decisions


def require_explicit_scope(document_ids: list[UUID] | None) -> list[UUID]:
    """Refuse an unfiltered database search. Callers must pass the resolved list."""

    if document_ids is None:
        raise ValueError("Retrieval scope must be an explicit document list.")
    return list(document_ids)
