"""Question-answering pipeline shared by chat and experiments."""

import logging
import time
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import assert_configuration_allowed, can_read_document
from app.config import settings
from app.exceptions import InfrastructureError, PermissionDenied
from app.models import Document, DocumentPermission, Profile
from app.rag.llm import embed_texts, generate_answer
from app.rag.retrieval import search_chunks
from app.security.configurations import CONFIGURATION_DEFINITIONS
from app.security.input_validation import validate_question
from app.security.logging import write_security_log
from app.security.output_validation import apply_output_validation, split_marker_access
from app.security.prompts import build_messages
from app.security.scope import resolve_document_scope

logger = logging.getLogger("ragsec.pipeline")


@dataclass
class PipelineResult:
    answer: str | None = None
    input_rejected: bool = False
    rejection_reason: str | None = None
    infrastructure_error: str | None = None
    retrieved_access_levels: list[str] = field(default_factory=list)
    retrieved_document_ids: list[str] = field(default_factory=list)
    retrieved_titles: list[str] = field(default_factory=list)
    output_filter_applied: bool = False
    model_emitted_markers: list[str] = field(default_factory=list)
    visible_markers: list[str] = field(default_factory=list)
    latency_ms: int = 0
    warnings: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    suspicious_labels: list[str] = field(default_factory=list)
    scope_document_ids: list[str] = field(default_factory=list)
    target_document_ids: list[str] = field(default_factory=list)
    targets_excluded: bool = False
    target_documents_missing: bool = False
    security_decisions: list[str] = field(default_factory=list)
    configuration: str = "secured"


def _permission_map(db: Session) -> dict[UUID, set[UUID]]:
    rows = db.scalars(select(DocumentPermission)).all()
    mapping: dict[UUID, set[UUID]] = {}
    for row in rows:
        mapping.setdefault(row.document_id, set()).add(row.user_id)
    return mapping


def readable_documents(db: Session, actor: Profile) -> list[Document]:
    documents = db.scalars(select(Document)).all()
    grants = _permission_map(db)
    allowed: list[Document] = []
    for document in documents:
        if can_read_document(
            role=actor.role,
            user_id=actor.id,
            document_owner_id=document.owner_id,
            access_level=document.access_level,
            explicit_user_ids=grants.get(document.id, set()),
        ):
            allowed.append(document)
    return allowed


def _log(actor: Profile, enabled: bool, **kwargs) -> None:
    if not enabled:
        return
    write_security_log(user_id=actor.id, **kwargs)


def answer_question(
    db: Session,
    *,
    actor: Profile,
    question: str,
    configuration: str,
    document_ids: list[UUID] | None,
    runtime: dict,
    experiment_id: UUID | None = None,
    test_case_id: UUID | None = None,
    experiment_execution: bool = False,
    target_access_levels: list[str] | None = None,
) -> PipelineResult:
    started = time.perf_counter()
    result = PipelineResult(configuration=configuration)
    flags = CONFIGURATION_DEFINITIONS.get(configuration)
    if flags is None:
        result.input_rejected = True
        result.rejection_reason = "Unknown configuration."
        result.latency_ms = _elapsed(started)
        return result

    try:
        assert_configuration_allowed(
            actor.role,
            configuration,
            experiment_execution=experiment_execution,
        )
    except PermissionDenied as exc:
        result.input_rejected = True
        result.rejection_reason = exc.message
        result.latency_ms = _elapsed(started)
        write_security_log(
            user_id=actor.id,
            event_type="authorisation_failure",
            severity="medium",
            outcome="denied",
            configuration=configuration,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
            metadata={"decision": "baseline_chat_denied"},
        )
        return result

    validation = validate_question(question, configuration, runtime)
    result.suspicious_labels = validation.suspicious_labels
    if validation.rejected:
        result.input_rejected = True
        result.rejection_reason = validation.reason
        result.answer = validation.reason
        result.latency_ms = _elapsed(started)
        if flags["security_decision_logging"]:
            _log(
                actor,
                True,
                event_type="input_rejected",
                severity="low",
                outcome="blocked",
                configuration=configuration,
                experiment_id=experiment_id,
                test_case_id=test_case_id,
                metadata={"reason": validation.reason, "length": len(question or "")},
            )
        return result

    if validation.suspicious_labels and flags["security_decision_logging"]:
        _log(
            actor,
            True,
            event_type="suspicious_request",
            severity="low",
            outcome="logged",
            configuration=configuration,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
            metadata={"labels": validation.suspicious_labels, "input_length": len(validation.text)},
        )
        result.warnings.append(
            "This request matched a suspicious-pattern check and was logged. "
            "Keyword checks are not the control that prevents prompt injection."
        )

    if configuration == "baseline":
        result.warnings.append(
            "Baseline configuration: permission filtering, prompt separation, "
            "and output validation are not applied on this RAG path."
        )

    documents = db.scalars(select(Document)).all()
    ready = [document for document in documents if document.processing_status == "ready"]
    readable = {
        document.id
        for document in readable_documents(db, actor)
        if document.processing_status == "ready"
    }
    all_ready = {document.id for document in ready}
    if not all_ready:
        result.infrastructure_error = "No processed documents are available."
        result.latency_ms = _elapsed(started)
        return result

    requested = set(document_ids) if document_ids is not None else None
    scope, decisions = resolve_document_scope(
        configuration=configuration,
        requested_ids=requested,
        authorised_ids=readable,
        all_ready_ids=all_ready,
    )
    result.security_decisions = decisions
    result.scope_document_ids = [str(item) for item in scope]

    target_levels = set(target_access_levels or [])
    target_ids = {document.id for document in ready if document.access_level in target_levels}
    result.target_document_ids = [str(item) for item in target_ids]
    result.target_documents_missing = bool(target_levels) and not target_ids
    result.targets_excluded = bool(target_ids) and target_ids.isdisjoint(scope)

    if "denied_unauthorised_document_ids" in decisions and flags["security_decision_logging"]:
        _log(
            actor,
            True,
            event_type="blocked_document_access",
            severity="high",
            outcome="blocked",
            configuration=configuration,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
            metadata={"decision": "unauthorised_document_ids_removed_before_retrieval"},
        )

    if not scope:
        result.answer = "No authorised documents are available for this request."
        result.latency_ms = _elapsed(started)
        if flags["security_decision_logging"]:
            _log(
                actor,
                True,
                event_type="blocked_document_access",
                severity="medium",
                outcome="blocked",
                configuration=configuration,
                experiment_id=experiment_id,
                test_case_id=test_case_id,
                metadata={"decision": "empty_authorised_scope"},
            )
        return result

    try:
        query_vector = embed_texts(
            model=str(runtime.get("embedding_model") or settings.embedding_model),
            texts=[validation.text],
        )[0]
        chunks = search_chunks(
            db,
            embedding=query_vector,
            match_count=int(runtime.get("top_k", 8)),
            similarity_threshold=float(runtime.get("similarity_threshold", -1.0)),
            allowed_document_ids=list(scope),
        )
    except InfrastructureError as exc:
        result.infrastructure_error = exc.message
        result.latency_ms = _elapsed(started)
        return result
    except Exception:
        result.infrastructure_error = "The retrieval service could not complete the request."
        result.latency_ms = _elapsed(started)
        logger.exception("Retrieval failed")
        write_security_log(
            user_id=actor.id,
            event_type="infrastructure_failure",
            severity="high",
            outcome="error",
            configuration=configuration,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
            metadata={"stage": "retrieval"},
        )
        return result

    # Defensive copy: never pass a chunk whose document is outside the resolved scope.
    allowed_scope = {str(item) for item in scope}
    chunks = [chunk for chunk in chunks if chunk.document_id in allowed_scope]
    result.retrieved_document_ids = sorted({chunk.document_id for chunk in chunks})
    result.retrieved_titles = sorted({chunk.title for chunk in chunks})
    result.retrieved_access_levels = sorted({chunk.access_level for chunk in chunks})
    result.sources = [
        {
            "document_id": chunk.document_id,
            "title": chunk.title,
            "chunk_index": chunk.chunk_index,
            "similarity": round(chunk.similarity, 4),
            "access_level": chunk.access_level,
            "excerpt": chunk.content[:300],
        }
        for chunk in chunks
    ]

    messages = build_messages(configuration=configuration, question=validation.text, chunks=chunks)
    if configuration == "secured":
        system_text = messages[0]["content"]
        for chunk in chunks:
            if chunk.content and chunk.content in system_text:
                result.infrastructure_error = "Prompt construction failed an internal safety check."
                result.latency_ms = _elapsed(started)
                return result

    try:
        answer = generate_answer(
            model=str(runtime.get("llm_model") or settings.llm_model),
            messages=messages,
            temperature=float(runtime.get("temperature", 0)),
        )
    except InfrastructureError as exc:
        result.infrastructure_error = exc.message
        result.latency_ms = _elapsed(started)
        return result

    marker_rows = [
        {"id": str(document.id), "protected_markers": list(document.protected_markers or [])}
        for document in documents
    ]
    _, unauthorised = split_marker_access(marker_rows, {str(item) for item in readable}, role=actor.role)
    validated = apply_output_validation(
        answer,
        configuration=configuration,
        unauthorised_markers=unauthorised,
    )
    result.answer = validated.answer
    result.output_filter_applied = validated.redacted
    result.model_emitted_markers = validated.emitted_markers
    result.visible_markers = validated.visible_markers
    if configuration == "secured":
        for source in result.sources:
            source["excerpt"] = apply_output_validation(
                str(source.get("excerpt") or ""),
                configuration="secured",
                unauthorised_markers=unauthorised,
            ).answer
    if validated.redacted:
        result.warnings.append(
            "The output check removed synthetic protected markers this account is not allowed to view. "
            "Output filtering does not guarantee that prompt injection is prevented."
        )
        _log(
            actor,
            flags["security_decision_logging"],
            event_type="potential_disclosure",
            severity="high",
            outcome="redacted",
            configuration=configuration,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
            metadata={"markers": validated.redacted_markers},
        )
    elif validated.emitted_markers and flags["security_decision_logging"]:
        _log(
            actor,
            True,
            event_type="potential_disclosure",
            severity="medium",
            outcome="visible_to_authorised_user" if not unauthorised.intersection(validated.emitted_markers) else "logged",
            configuration=configuration,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
            metadata={"markers": validated.emitted_markers},
        )

    result.latency_ms = _elapsed(started)
    return result


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
