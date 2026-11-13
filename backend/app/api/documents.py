from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serialize import iso
from app.auth.permissions import (
    can_delete_document,
    can_manage_permissions,
    can_read_document,
    can_set_access_level,
    can_upload,
)
from app.database import get_db
from app.deps import get_current_user
from app.exceptions import ConflictError, InputRejected, NotFoundError, PermissionDenied
from app.models import Document, DocumentChunk, DocumentPermission, Profile
from app.rag.documents import (
    duplicate_document,
    extract_text,
    file_sha256,
    process_document_text,
    remove_stored_file,
    reprocess_document,
    store_upload,
)
from app.security.input_validation import validate_upload
from app.security.logging import write_security_log
from app.services.runtime import get_runtime_settings

router = APIRouter(prefix="/documents", tags=["documents"])


class AccessUpdate(BaseModel):
    access_level: str = Field(pattern="^(public|employee|hr|confidential|admin)$")


class PermissionCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    permission: str = Field(default="read", pattern="^read$")


def _grants(db: Session) -> dict[UUID, set[UUID]]:
    mapping: dict[UUID, set[UUID]] = {}
    for row in db.scalars(select(DocumentPermission)).all():
        mapping.setdefault(row.document_id, set()).add(row.user_id)
    return mapping


def _emails(db: Session) -> dict[UUID, str]:
    return {profile.id: profile.email for profile in db.scalars(select(Profile)).all()}


def _readable(document: Document, user: Profile, grants: dict[UUID, set[UUID]]) -> bool:
    return can_read_document(
        role=user.role,
        user_id=user.id,
        document_owner_id=document.owner_id,
        access_level=document.access_level,
        explicit_user_ids=grants.get(document.id, set()),
    )


def _document_payload(document: Document, emails: dict[UUID, str], *, include_text: bool) -> dict:
    payload = {
        "id": str(document.id),
        "owner_id": str(document.owner_id),
        "owner_email": emails.get(document.owner_id),
        "title": document.title,
        "document_type": document.document_type,
        "access_level": document.access_level,
        "processing_status": document.processing_status,
        "error_message": document.error_message,
        "chunk_count": document.chunk_count,
        "protected_markers": list(document.protected_markers or []),
        "created_at": iso(document.created_at),
    }
    if include_text:
        payload["extracted_text"] = document.extracted_text or ""
    return payload


def _get_visible(db: Session, document_id: UUID, user: Profile) -> Document:
    document = db.get(Document, document_id)
    if document is None or not _readable(document, user, _grants(db)):
        if document is not None:
            write_security_log(
                user_id=user.id,
                event_type="blocked_document_access",
                severity="medium",
                outcome="denied",
                metadata={"document_id": str(document.id), "surface": "document_api"},
            )
        raise NotFoundError()
    return document


@router.get("")
def list_documents(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    grants = _grants(db)
    emails = _emails(db)
    documents = [
        _document_payload(document, emails, include_text=False)
        for document in db.scalars(select(Document).order_by(Document.created_at.desc())).all()
        if _readable(document, user, grants)
    ]
    return {"documents": documents}


@router.get("/{document_id}")
def get_document(
    document_id: UUID,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = _get_visible(db, document_id, user)
    return _document_payload(document, _emails(db), include_text=True)


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    access_level: str = Form(...),
    title: str = Form(""),
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    runtime = get_runtime_settings(db)
    if not can_upload(user.role, bool(runtime.get("allow_employee_upload"))):
        write_security_log(
            user_id=user.id,
            event_type="authorisation_failure",
            severity="medium",
            outcome="denied",
            metadata={"action": "upload"},
        )
        raise PermissionDenied("Your account cannot upload documents.")
    if not can_set_access_level(user.role, access_level):
        raise PermissionDenied("Your account cannot assign that access level.")

    content = await file.read()
    extension = validate_upload(
        file.filename,
        file.content_type,
        len(content),
        int(runtime.get("max_upload_bytes", 10_485_760)),
    )
    digest = file_sha256(content)
    if duplicate_document(db, user.id, digest) is not None:
        raise ConflictError("This file has already been uploaded by your account.")

    document = Document(
        owner_id=user.id,
        title=(title or file.filename or "Untitled").strip()[:200],
        file_path="",
        document_type=extension.lstrip("."),
        access_level=access_level,
        processing_status="processing",
        content_hash=digest,
        protected_markers=[],
    )
    db.add(document)
    db.flush()
    document.file_path = store_upload(document.id, extension, content)
    try:
        extracted = extract_text(content, extension)
    except InputRejected as exc:
        document.processing_status = "failed"
        document.error_message = exc.message
        db.commit()
        return _document_payload(document, _emails(db), include_text=True)

    process_document_text(db, document, extracted, runtime)
    db.commit()
    db.refresh(document)
    return _document_payload(document, _emails(db), include_text=True)


@router.post("/{document_id}/reprocess")
def reprocess(
    document_id: UUID,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = _get_visible(db, document_id, user)
    if not can_delete_document(user.role, user.id, document.owner_id) and user.role != "researcher":
        raise PermissionDenied("You cannot reprocess this document.")
    reprocess_document(db, document, get_runtime_settings(db))
    db.commit()
    db.refresh(document)
    return _document_payload(document, _emails(db), include_text=True)


@router.put("/{document_id}/access")
def update_access(
    document_id: UUID,
    body: AccessUpdate,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not can_manage_permissions(user.role):
        write_security_log(
            user_id=user.id,
            event_type="authorisation_failure",
            severity="high",
            outcome="denied",
            metadata={"action": "change_access_level"},
        )
        raise PermissionDenied("Only an administrator can change document access.")
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError()
    document.access_level = body.access_level
    for chunk in db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id)).all():
        metadata = dict(chunk.chunk_metadata or {})
        metadata["access_level"] = body.access_level
        chunk.chunk_metadata = metadata
    db.commit()
    return _document_payload(document, _emails(db), include_text=False)


@router.post("/{document_id}/permissions")
def grant_permission(
    document_id: UUID,
    body: PermissionCreate,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not can_manage_permissions(user.role):
        write_security_log(
            user_id=user.id,
            event_type="authorisation_failure",
            severity="high",
            outcome="denied",
            metadata={"action": "grant_permission"},
        )
        raise PermissionDenied("Only an administrator can assign document permissions.")
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError()
    target = db.scalar(select(Profile).where(func.lower(Profile.email) == body.email.strip().lower()))
    if target is None:
        raise NotFoundError("No account exists with that email.")
    existing = db.scalar(
        select(DocumentPermission).where(
            DocumentPermission.document_id == document.id,
            DocumentPermission.user_id == target.id,
        )
    )
    if existing is None:
        db.add(DocumentPermission(document_id=document.id, user_id=target.id, permission="read"))
        db.commit()
    return {"document_id": str(document.id), "user_id": str(target.id), "email": target.email, "permission": "read"}


@router.delete("/{document_id}/permissions/{permission_id}")
def revoke_permission(
    document_id: UUID,
    permission_id: UUID,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not can_manage_permissions(user.role):
        raise PermissionDenied("Only an administrator can revoke document permissions.")
    permission = db.get(DocumentPermission, permission_id)
    if permission is None or permission.document_id != document_id:
        raise NotFoundError()
    db.delete(permission)
    db.commit()
    return {"deleted": True}


@router.get("/{document_id}/permissions")
def list_permissions(
    document_id: UUID,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not can_manage_permissions(user.role):
        raise PermissionDenied()
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError()
    emails = _emails(db)
    rows = db.scalars(select(DocumentPermission).where(DocumentPermission.document_id == document.id)).all()
    return {
        "permissions": [
            {
                "id": str(row.id),
                "user_id": str(row.user_id),
                "email": emails.get(row.user_id),
                "permission": row.permission,
                "created_at": iso(row.created_at),
            }
            for row in rows
        ]
    }


@router.delete("/{document_id}")
def delete_document(
    document_id: UUID,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError()
    if not _readable(document, user, _grants(db)):
        raise NotFoundError()
    if not can_delete_document(user.role, user.id, document.owner_id):
        raise PermissionDenied("You cannot delete this document.")
    remove_stored_file(document.file_path)
    db.delete(document)
    db.commit()
    return {"deleted": True}
