from sqlalchemy import select

from app.config import settings
from app.models import AppSetting

DEFAULT_RUNTIME: dict = {
    "chunk_size": 800,
    "chunk_overlap": 120,
    "top_k": 8,
    "similarity_threshold": -1.0,
    "temperature": 0.0,
    "max_input_chars_secured": 4000,
    "max_input_chars_baseline": 12000,
    "max_upload_bytes": 10_485_760,
    "rate_limit_per_minute": 30,
    "allow_employee_upload": False,
}

EDITABLE_SETTINGS = set(DEFAULT_RUNTIME) | {"llm_model", "embedding_model"}


def get_runtime_settings(db) -> dict:
    values = dict(DEFAULT_RUNTIME)
    values["llm_model"] = settings.llm_model
    values["embedding_model"] = settings.embedding_model
    for row in db.scalars(select(AppSetting)).all():
        raw = row.value
        if isinstance(raw, dict) and "value" in raw:
            values[row.key] = raw["value"]
    if not values.get("llm_model"):
        values["llm_model"] = settings.llm_model
    if not values.get("embedding_model"):
        values["embedding_model"] = settings.embedding_model
    return values


def validate_runtime_update(key: str, value) -> object:
    if key not in EDITABLE_SETTINGS:
        raise ValueError("That setting cannot be changed from the application.")
    if key in {"llm_model", "embedding_model"}:
        text = str(value).strip()
        if not 2 <= len(text) <= 120:
            raise ValueError(f"{key} must be between 2 and 120 characters.")
        return text
    if key in {"chunk_size", "chunk_overlap", "top_k", "max_input_chars_secured", "max_input_chars_baseline", "max_upload_bytes", "rate_limit_per_minute"}:
        number = int(value)
        bounds = {
            "chunk_size": (200, 4000),
            "chunk_overlap": (0, 1000),
            "top_k": (1, 20),
            "max_input_chars_secured": (200, 20000),
            "max_input_chars_baseline": (200, 20000),
            "max_upload_bytes": (1024, 20 * 1024 * 1024),
            "rate_limit_per_minute": (1, 300),
        }
        low, high = bounds[key]
        if not low <= number <= high:
            raise ValueError(f"{key} must be between {low} and {high}.")
        return number
    if key == "similarity_threshold":
        threshold = float(value)
        if not -1 <= threshold <= 1:
            raise ValueError("similarity_threshold must be between -1 and 1.")
        return threshold
    if key == "temperature":
        temperature = float(value)
        if not 0 <= temperature <= 1:
            raise ValueError("temperature must be between 0 and 1.")
        return temperature
    if key == "allow_employee_upload":
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "false"}:
            return str(value).lower() == "true"
        raise ValueError("allow_employee_upload must be true or false.")
    raise ValueError("Unsupported setting.")
