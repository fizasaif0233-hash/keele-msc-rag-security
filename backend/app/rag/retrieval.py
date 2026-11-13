from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.security.prompts import RetrievedChunk
from app.security.scope import require_explicit_scope


def search_chunks(
    db: Session,
    *,
    embedding: list[float],
    match_count: int,
    similarity_threshold: float,
    allowed_document_ids: list[UUID] | None,
) -> list[RetrievedChunk]:
    """Vector search limited to an explicit document list.

    `None` is rejected so a caller cannot accidentally search the whole corpus.
    An empty list returns no rows and does not call the database function.
    """

    allowed = require_explicit_scope(allowed_document_ids)
    if not allowed or match_count <= 0:
        return []

    literal = "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"
    allowed_literal = "{" + ",".join(str(item) for item in allowed) + "}"
    rows = db.execute(
        text(
            """
            select *
            from public.match_document_chunks(
                cast(:embedding as vector),
                :match_count,
                :similarity_threshold,
                cast(:allowed_ids as uuid[])
            )
            """
        ),
        {
            "embedding": literal,
            "match_count": int(match_count),
            "similarity_threshold": float(similarity_threshold),
            "allowed_ids": allowed_literal,
        },
    ).mappings()

    chunks: list[RetrievedChunk] = []
    for row in rows:
        chunks.append(
            RetrievedChunk(
                document_id=str(row["document_id"]),
                title=row["title"],
                content=row["content"],
                access_level=str(row["access_level"]),
                chunk_index=int(row["chunk_index"]),
                similarity=float(row["similarity"]),
            )
        )
    return chunks
