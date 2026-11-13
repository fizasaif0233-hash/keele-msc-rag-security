import logging
from typing import Any

import httpx

from app.config import settings
from app.constants import EMBEDDING_DIMENSIONS
from app.exceptions import InfrastructureError

logger = logging.getLogger("ragsec.llm")


def _root() -> str:
    return settings.llm_base_url.rstrip("/")


def _headers() -> dict[str, str]:
    if not settings.llm_api_key:
        raise InfrastructureError(
            "The model API key is not configured.",
            internal="LLM_API_KEY is empty.",
        )
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }


def _safe_provider_message(status_code: int, body: str) -> str:
    lowered = body.lower()
    if status_code == 401:
        return "The model provider rejected the API key."
    if "context" in lowered or "maximum" in lowered and "token" in lowered:
        return "The model rejected the request because the context was too large."
    if status_code == 429:
        return "The model provider rate limit was reached."
    if status_code >= 500:
        return "The model provider is unavailable."
    return "The model provider returned an error."


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = client.post(f"{_root()}{path}", headers=_headers(), json=payload)
    except httpx.TimeoutException as exc:
        raise InfrastructureError("The model provider timed out.", internal=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise InfrastructureError("The model provider could not be reached.", internal=str(exc)) from exc

    if response.status_code >= 400:
        body = response.text[:500]
        logger.warning("Model provider error status=%s body=%s", response.status_code, body)
        raise InfrastructureError(_safe_provider_message(response.status_code, body), internal=body)
    try:
        return response.json()
    except ValueError as exc:
        raise InfrastructureError("The model provider returned an unreadable response.") from exc


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return "".join(parts).strip()
    return str(content or "").strip()


def generate_answer(*, model: str, messages: list[dict[str, str]], temperature: float) -> str:
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }
    data = _post("/chat/completions", payload)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise InfrastructureError("The model provider returned an incomplete response.") from exc
    text = _message_text(content)
    if not text:
        raise InfrastructureError("The model provider returned an empty response.")
    return text


def embed_texts(*, model: str, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    ordered: list[list[float] | None] = [None] * len(texts)
    batch_size = 16
    for offset in range(0, len(texts), batch_size):
        batch = texts[offset : offset + batch_size]
        data = _post(
            "/embeddings",
            {"model": model, "input": batch, "dimensions": settings.embedding_dimensions},
        )
        rows = data.get("data")
        if not isinstance(rows, list) or len(rows) != len(batch):
            raise InfrastructureError("The embedding provider returned an incomplete batch.")
        for position, row in enumerate(rows):
            try:
                index = int(row["index"]) if "index" in row else position
                vector = [float(value) for value in row["embedding"]]
            except (KeyError, TypeError, ValueError) as exc:
                raise InfrastructureError("The embedding provider returned a malformed vector.") from exc
            if len(vector) != settings.embedding_dimensions or len(vector) != EMBEDDING_DIMENSIONS:
                raise InfrastructureError(
                    "The embedding dimensions do not match the database configuration.",
                    internal=f"received {len(vector)} expected {EMBEDDING_DIMENSIONS}",
                )
            ordered[offset + index] = vector
    if any(vector is None for vector in ordered):
        raise InfrastructureError("The embedding provider omitted a vector.")
    return [vector for vector in ordered if vector is not None]
