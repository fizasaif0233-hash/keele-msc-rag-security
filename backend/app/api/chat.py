from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serialize import iso
from app.database import get_db
from app.deps import get_current_user
from app.exceptions import InfrastructureError, NotFoundError, RateLimitError
from app.models import ChatMessage, ChatSession, Profile
from app.rag.pipeline import answer_question
from app.security.logging import write_security_log
from app.security.rate_limit import rate_limiter
from app.services.runtime import get_runtime_settings

router = APIRouter(prefix="/chat", tags=["chat"])


class SessionCreate(BaseModel):
    title: str = Field(default="New chat", max_length=120)
    configuration: str = Field(default="secured", pattern="^(baseline|secured)$")


class MessageCreate(BaseModel):
    content: str
    configuration: str | None = Field(default=None, pattern="^(baseline|secured)$")
    document_ids: list[UUID] | None = None


def _own_session(db: Session, session_id: UUID, user: Profile) -> ChatSession:
    chat = db.get(ChatSession, session_id)
    if chat is None or chat.user_id != user.id:
        raise NotFoundError()
    return chat


@router.get("/sessions")
def list_sessions(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(
        select(ChatSession).where(ChatSession.user_id == user.id).order_by(ChatSession.created_at.desc())
    ).all()
    return {
        "sessions": [
            {
                "id": str(row.id),
                "title": row.title,
                "configuration": row.configuration,
                "created_at": iso(row.created_at),
            }
            for row in rows
        ]
    }


@router.post("/sessions")
def create_session(
    body: SessionCreate,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    configuration = body.configuration
    if user.role == "employee":
        configuration = "secured"
    chat = ChatSession(user_id=user.id, title=body.title.strip() or "New chat", configuration=configuration)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return {
        "id": str(chat.id),
        "title": chat.title,
        "configuration": chat.configuration,
        "created_at": iso(chat.created_at),
    }


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: UUID,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    chat = _own_session(db, session_id, user)
    db.delete(chat)
    db.commit()
    return {"deleted": True}


@router.get("/sessions/{session_id}/messages")
def list_messages(
    session_id: UUID,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    chat = _own_session(db, session_id, user)
    rows = db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == chat.id).order_by(ChatMessage.created_at)
    ).all()
    return {
        "session": {
            "id": str(chat.id),
            "title": chat.title,
            "configuration": chat.configuration,
        },
        "messages": [
            {
                "id": str(row.id),
                "role": row.role,
                "content": row.content,
                "latency_ms": row.latency_ms,
                "metadata": row.message_metadata or {},
                "created_at": iso(row.created_at),
            }
            for row in rows
        ],
    }


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: UUID,
    body: MessageCreate,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    chat = _own_session(db, session_id, user)
    runtime = get_runtime_settings(db)
    limit = int(runtime.get("rate_limit_per_minute", 30))
    configuration = body.configuration or chat.configuration
    if user.role == "employee":
        configuration = "secured"
    if not rate_limiter.allow(f"chat:{user.id}", limit):
        write_security_log(
            user_id=user.id,
            event_type="rate_limited",
            severity="medium",
            outcome="blocked",
            configuration=configuration,
            metadata={"surface": "chat"},
        )
        raise RateLimitError()
    chat.configuration = configuration
    db.add(ChatMessage(session_id=chat.id, role="user", content=body.content, message_metadata={}))
    if chat.title == "New chat" and body.content.strip():
        chat.title = body.content.strip()[:80]
    db.commit()

    result = answer_question(
        db,
        actor=user,
        question=body.content,
        configuration=configuration,
        document_ids=body.document_ids,
        runtime=runtime,
        experiment_execution=False,
    )
    if result.infrastructure_error:
        db.add(
            ChatMessage(
                session_id=chat.id,
                role="assistant",
                content="The model service could not complete this request.",
                latency_ms=result.latency_ms,
                message_metadata={"infrastructure_error": True, "configuration": configuration},
            )
        )
        db.commit()
        raise InfrastructureError(result.infrastructure_error)

    answer = result.answer or result.rejection_reason or "No answer was produced."
    db.add(
        ChatMessage(
            session_id=chat.id,
            role="assistant",
            content=answer,
            latency_ms=result.latency_ms,
            message_metadata={
                "configuration": configuration,
                "sources": result.sources,
                "warnings": result.warnings,
                "accepted": not result.input_rejected,
                "suspicious_labels": result.suspicious_labels,
                "security_decisions": result.security_decisions,
                "output_filter_applied": result.output_filter_applied,
            },
        )
    )
    db.commit()
    return {
        "accepted": not result.input_rejected,
        "answer": answer,
        "configuration": configuration,
        "latency_ms": result.latency_ms,
        "sources": result.sources,
        "warnings": result.warnings,
        "suspicious_labels": result.suspicious_labels,
        "output_filter_applied": result.output_filter_applied,
    }
