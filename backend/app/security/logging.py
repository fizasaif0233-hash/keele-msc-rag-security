"""Security event log.

Records are written on a separate database session so a later request failure
does not erase them. Metadata is scrubbed before storage.
"""

import logging
import re
from typing import Any
from uuid import UUID

from app.database import get_session_factory
from app.models import SecurityLog

logger = logging.getLogger("ragsec.security")

SENSITIVE_KEY = re.compile(r"password|token|secret|authorization|api_key|apikey|credential", re.I)


def scrub_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if SENSITIVE_KEY.search(str(key)):
                cleaned[str(key)] = "[removed]"
            else:
                cleaned[str(key)] = scrub_metadata(item, depth=depth + 1)
        return cleaned
    if isinstance(value, list):
        return [scrub_metadata(item, depth=depth + 1) for item in value[:30]]
    if isinstance(value, str):
        return value[:300]
    if isinstance(value, UUID):
        return str(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:300]


def write_security_log(
    *,
    user_id: UUID | None,
    event_type: str,
    severity: str,
    outcome: str,
    configuration: str | None = None,
    experiment_id: UUID | None = None,
    test_case_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    try:
        session = get_session_factory()()
    except Exception:
        logger.exception("Security log skipped because the database is not available.")
        return
    try:
        session.add(
            SecurityLog(
                user_id=user_id,
                event_type=event_type,
                severity=severity,
                outcome=outcome,
                configuration=configuration,
                experiment_id=experiment_id,
                test_case_id=test_case_id,
                log_metadata=scrub_metadata(metadata or {}),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to persist a security log.")
    finally:
        session.close()
