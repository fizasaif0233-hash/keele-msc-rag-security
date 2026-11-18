"""Permission changes apply on the next read. Nothing is committed."""

import pytest
from app.config import settings
from app.database import get_session_factory
from app.models import Document, DocumentPermission, Profile
from app.rag.pipeline import readable_documents
from sqlalchemy import select

pytestmark = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL is not configured.")


def _ids(documents: list[Document]) -> set:
    return {document.id for document in documents}


def test_grant_label_and_role_changes_apply_before_commit():
    db = get_session_factory()()
    try:
        employee = db.scalar(select(Profile).where(Profile.email == "employee.synthetic@keele-rag.example"))
        hidden = db.scalar(select(Document).where(Document.title == "Finance internal report"))
        assert employee is not None and hidden is not None
        assert hidden.id not in _ids(readable_documents(db, employee))

        grant = DocumentPermission(document_id=hidden.id, user_id=employee.id, permission="read")
        db.add(grant)
        db.flush()
        assert hidden.id in _ids(readable_documents(db, employee))
        db.delete(grant)
        db.flush()
        assert hidden.id not in _ids(readable_documents(db, employee))

        original_label = hidden.access_level
        hidden.access_level = "public"
        db.flush()
        assert hidden.id in _ids(readable_documents(db, employee))
        hidden.access_level = original_label
        db.flush()
        assert hidden.id not in _ids(readable_documents(db, employee))

        original_role = employee.role
        employee.role = "admin"
        db.flush()
        assert hidden.id in _ids(readable_documents(db, employee))
        employee.role = original_role
        db.flush()
        assert hidden.id not in _ids(readable_documents(db, employee))
    finally:
        db.rollback()
        db.close()
