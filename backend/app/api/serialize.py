from datetime import datetime
from uuid import UUID


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def uuid_str(value: UUID | None) -> str | None:
    if value is None:
        return None
    return str(value)
