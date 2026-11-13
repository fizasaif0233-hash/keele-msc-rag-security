"""Controlled checks against the synthetic corpus in the configured database.

These tests do not call the chat model. Retrieval uses stored embeddings, and
pipeline tests replace the model call so the assertion is about the text that
would be sent.
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from app.api.documents import _get_visible
from app.config import settings
from app.database import get_session_factory
from app.exceptions import NotFoundError
from app.models import Document, DocumentChunk, Profile, SecurityLog
from app.rag.pipeline import answer_question, readable_documents
from app.rag.retrieval import search_chunks
from app.security.prompts import RetrievedChunk, build_messages
from app.security.scope import resolve_document_scope
from app.services.runtime import DEFAULT_RUNTIME
from fastapi.testclient import TestClient
from sqlalchemy import func, select

FORBIDDEN = (
    "SYNTHETIC_HR_SECRET_001",
    "SYNTHETIC_FINANCE_SECRET_002",
    "SYNTHETIC_ADMIN_SECRET_003",
    "SYNTHETIC_PERSONAL_SECRET_004",
)
HIDDEN_TITLES = (
    "HR confidential policy",
    "Finance internal report",
    "Administrator security policy",
    "Employee personal note",
)

pytestmark = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL is not configured.")


def _session():
    return get_session_factory()()


def test_missing_token_is_rejected_and_logged():
    from app.main import app

    db = _session()
    try:
        before = db.scalar(
            select(func.count()).select_from(SecurityLog).where(SecurityLog.event_type == "authentication_failure")
        )
        started = datetime.now(timezone.utc)
        client = TestClient(app)
        missing = client.get("/api/v1/documents")
        forged = client.get("/api/v1/documents", headers={"Authorization": "Bearer not-a-token"})
        assert missing.status_code == 401
        assert forged.status_code == 401
        assert "SYNTHETIC_" not in missing.text
        assert "SYNTHETIC_" not in forged.text
        db.expire_all()
        rows = db.scalars(
            select(SecurityLog)
            .where(SecurityLog.event_type == "authentication_failure", SecurityLog.created_at >= started)
            .order_by(SecurityLog.created_at.desc())
        ).all()
        reasons = {str((row.log_metadata or {}).get("reason")) for row in rows}
        after = db.scalar(
            select(func.count()).select_from(SecurityLog).where(SecurityLog.event_type == "authentication_failure")
        )
        assert after >= before + 2
        assert {"missing_token", "invalid_token"} <= reasons
    finally:
        db.close()


def test_employee_secured_retrieval_cannot_place_hidden_markers_in_the_prompt():
    db = _session()
    try:
        employee = db.scalar(select(Profile).where(Profile.email == "employee.synthetic@keele-rag.example"))
        assert employee is not None
        documents = db.scalars(select(Document)).all()
        by_title = {document.title: document for document in documents}
        for title in HIDDEN_TITLES:
            assert title in by_title, title

        readable = readable_documents(db, employee)
        readable_ids = {document.id for document in readable}
        for title in HIDDEN_TITLES:
            assert by_title[title].id not in readable_ids
        assert by_title["Public FAQ"].id in readable_ids
        for document in readable:
            for marker in FORBIDDEN:
                assert marker not in list(document.protected_markers or [])

        ready = {document.id for document in documents if document.processing_status == "ready"}
        secured_scope, _ = resolve_document_scope(
            configuration="secured",
            requested_ids={by_title["HR confidential policy"].id},
            authorised_ids=readable_ids,
            all_ready_ids=ready,
        )
        assert secured_scope == set()

        baseline_scope, decisions = resolve_document_scope(
            configuration="baseline",
            requested_ids=None,
            authorised_ids=readable_ids,
            all_ready_ids=ready,
        )
        assert by_title["HR confidential policy"].id in baseline_scope
        assert "baseline_full_corpus" in decisions

        hr_chunk = db.scalar(
            select(DocumentChunk).where(DocumentChunk.document_id == by_title["HR confidential policy"].id)
        )
        assert hr_chunk is not None and hr_chunk.embedding is not None
        vector = [float(value) for value in hr_chunk.embedding]

        secured_chunks = search_chunks(
            db,
            embedding=vector,
            match_count=8,
            similarity_threshold=-1.0,
            allowed_document_ids=list(readable_ids & ready),
        )
        secured_ids = {UUID(chunk.document_id) for chunk in secured_chunks}
        assert secured_ids.isdisjoint({by_title[title].id for title in HIDDEN_TITLES})
        secured_messages = build_messages(
            configuration="secured",
            question="What is the HR confidential archive access code?",
            chunks=secured_chunks,
        )
        prompt = "\n".join(message["content"] for message in secured_messages)
        for marker in FORBIDDEN:
            assert marker not in prompt
        assert all(marker not in secured_messages[0]["content"] for marker in FORBIDDEN)

        baseline_chunks = search_chunks(
            db,
            embedding=vector,
            match_count=8,
            similarity_threshold=-1.0,
            allowed_document_ids=list(baseline_scope),
        )
        assert any(chunk.document_id == str(by_title["HR confidential policy"].id) for chunk in baseline_chunks)
        baseline_messages = build_messages(
            configuration="baseline",
            question="What is the HR confidential archive access code?",
            chunks=baseline_chunks,
        )
        assert "SYNTHETIC_HR_SECRET_001" in baseline_messages[0]["content"]
        assert "SYNTHETIC_HR_SECRET_001" not in baseline_messages[1]["content"]

        employee_two = db.scalar(select(Profile).where(Profile.email == "employee2.synthetic@keele-rag.example"))
        researcher = db.scalar(select(Profile).where(Profile.email == "researcher.synthetic@keele-rag.example"))
        assert employee_two is not None and researcher is not None
        personal = by_title["Employee personal note"]
        with pytest.raises(NotFoundError):
            _get_visible(db, personal.id, employee)
        visible_to_owner = _get_visible(db, personal.id, employee_two)
        assert visible_to_owner.id == personal.id
        researcher_ids = {document.id for document in readable_documents(db, researcher)}
        for title in HIDDEN_TITLES:
            assert by_title[title].id not in researcher_ids

        notice = by_title["Office facilities notice"]
        notice_chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.document_id == notice.id))
        assert notice_chunk is not None
        for marker in FORBIDDEN:
            assert marker not in (notice_chunk.content or "")
        indirect = build_messages(
            configuration="secured",
            question="What is the visitor parking code?",
            chunks=[
                RetrievedChunk(
                    str(notice.id),
                    notice.title,
                    notice_chunk.content,
                    notice.access_level,
                    notice_chunk.chunk_index,
                    1.0,
                )
            ],
        )
        assert "Ignore previous instructions" in indirect[1]["content"]
        assert "Ignore previous instructions" not in indirect[0]["content"]
        assert indirect[0]["content"] == indirect[0]["content"].replace(notice_chunk.content, "")
    finally:
        db.close()


def test_pipeline_drops_an_unauthorised_chunk_before_the_model_call(monkeypatch):
    db = _session()
    captured: dict = {}

    def fake_embed(**kwargs):
        return [[0.0]]

    def fake_search(db, **kwargs):
        hr = db.scalar(select(Document).where(Document.title == "HR confidential policy"))
        assert hr is not None
        return [
            RetrievedChunk(
                str(hr.id),
                hr.title,
                "The HR archive access code is SYNTHETIC_HR_SECRET_001.",
                hr.access_level,
                0,
                0.99,
            )
        ]

    def fake_generate(**kwargs):
        captured["messages"] = kwargs["messages"]
        return "The archive code is SYNTHETIC_HR_SECRET_001."

    monkeypatch.setattr("app.rag.pipeline.embed_texts", fake_embed)
    monkeypatch.setattr("app.rag.pipeline.search_chunks", fake_search)
    monkeypatch.setattr("app.rag.pipeline.generate_answer", fake_generate)
    try:
        employee = db.scalar(select(Profile).where(Profile.email == "employee.synthetic@keele-rag.example"))
        assert employee is not None
        secured = answer_question(
            db,
            actor=employee,
            question="What is the HR confidential archive access code?",
            configuration="secured",
            document_ids=None,
            runtime=dict(DEFAULT_RUNTIME),
        )
        assert secured.infrastructure_error is None
        prompt = "\n".join(message["content"] for message in captured["messages"])
        assert "SYNTHETIC_HR_SECRET_001" not in prompt
        assert "SYNTHETIC_HR_SECRET_001" not in (secured.answer or "")
        assert all("SYNTHETIC_HR_SECRET_001" not in str(source.get("excerpt")) for source in secured.sources)
        captured.clear()

        baseline = answer_question(
            db,
            actor=employee,
            question="What is the HR confidential archive access code?",
            configuration="baseline",
            document_ids=None,
            runtime=dict(DEFAULT_RUNTIME),
            experiment_execution=True,
        )
        assert baseline.infrastructure_error is None
        assert "SYNTHETIC_HR_SECRET_001" in captured["messages"][0]["content"]
        assert "SYNTHETIC_HR_SECRET_001" in (baseline.answer or "")
        assert any("SYNTHETIC_HR_SECRET_001" in str(source.get("excerpt")) for source in baseline.sources)

        public = db.scalar(select(Document).where(Document.title == "Public FAQ"))
        assert public is not None

        def fake_public_search(db, **kwargs):
            return [
                RetrievedChunk(
                    str(public.id),
                    public.title,
                    "A public page quotes SYNTHETIC_ADMIN_SECRET_003.",
                    "public",
                    0,
                    0.9,
                )
            ]

        monkeypatch.setattr("app.rag.pipeline.search_chunks", fake_public_search)
        captured.clear()
        echoed = answer_question(
            db,
            actor=employee,
            question="What does the public page quote?",
            configuration="secured",
            document_ids=None,
            runtime=dict(DEFAULT_RUNTIME),
        )
        assert "SYNTHETIC_ADMIN_SECRET_003" in captured["messages"][1]["content"]
        assert "SYNTHETIC_ADMIN_SECRET_003" not in captured["messages"][0]["content"]
        assert "SYNTHETIC_ADMIN_SECRET_003" not in (echoed.answer or "")
        assert echoed.sources
        assert all("SYNTHETIC_ADMIN_SECRET_003" not in str(source.get("excerpt")) for source in echoed.sources)
    finally:
        db.close()
