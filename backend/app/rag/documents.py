import hashlib
import io
import logging
from pathlib import Path
from uuid import UUID

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import KNOWN_MARKERS
from app.exceptions import InfrastructureError, InputRejected
from app.models import Document, DocumentChunk
from app.rag.chunking import chunk_text
from app.rag.llm import embed_texts
from app.security.input_validation import clean_text

logger = logging.getLogger("ragsec.documents")


def file_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_text(content: bytes, extension: str) -> str:
    if extension == ".txt":
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return clean_text(content.decode(encoding))
            except UnicodeDecodeError:
                continue
        raise InputRejected("The text file could not be decoded.")
    if extension == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
        except PdfReadError as exc:
            raise InputRejected("The PDF could not be read.") from exc
        except Exception as exc:
            raise InputRejected("The PDF could not be read.") from exc
        if getattr(reader, "is_encrypted", False):
            raise InputRejected("Encrypted PDFs are not supported.")
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return clean_text("\n".join(pages))
    raise InputRejected("Only PDF and TXT files are accepted.")


def detect_markers(text: str) -> list[str]:
    return [marker for marker in KNOWN_MARKERS if marker in text]


def store_upload(document_id: UUID, extension: str, content: bytes) -> str:
    directory = settings.storage_path
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{document_id}{extension}"
    path.write_bytes(content)
    return str(path)


def remove_stored_file(file_path: str | None) -> None:
    if not file_path:
        return
    path = Path(file_path)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        logger.warning("Could not delete stored file %s", path.name)


def process_document_text(db: Session, document: Document, raw_text: str, runtime: dict) -> None:
    """Chunk and embed a document. Missing credentials leave it pending rather than ready."""

    extracted = clean_text(raw_text)
    document.extracted_text = extracted
    document.protected_markers = detect_markers(extracted)
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

    pieces = chunk_text(
        extracted,
        int(runtime.get("chunk_size", 800)),
        int(runtime.get("chunk_overlap", 120)),
    )
    if not pieces:
        document.processing_status = "failed"
        document.chunk_count = 0
        document.error_message = "No extractable text was found."
        return

    vectors: list[list[float]] | None = None
    if not settings.llm_api_key:
        document.processing_status = "pending"
        document.error_message = "The embedding API key is not configured. Reprocess the document after configuring it."
    else:
        try:
            vectors = embed_texts(model=str(runtime.get("embedding_model") or settings.embedding_model), texts=pieces)
        except InfrastructureError as exc:
            document.processing_status = "failed"
            document.error_message = exc.message
            document.chunk_count = 0
            logger.warning("Embedding failed for document %s: %s", document.id, exc.internal or exc.message)
            return

    for index, piece in enumerate(pieces):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=piece,
                embedding=None if vectors is None else vectors[index],
                chunk_metadata={
                    "title": document.title,
                    "access_level": document.access_level,
                },
            )
        )
    document.chunk_count = len(pieces)
    if vectors is not None:
        document.processing_status = "ready"
        document.error_message = None


def reprocess_document(db: Session, document: Document, runtime: dict) -> None:
    if not document.extracted_text:
        document.processing_status = "failed"
        document.error_message = "There is no extracted text to reprocess."
        return
    process_document_text(db, document, document.extracted_text, runtime)


def duplicate_document(db: Session, owner_id: UUID, content_hash: str) -> Document | None:
    return db.scalar(
        select(Document).where(Document.owner_id == owner_id, Document.content_hash == content_hash)
    )
