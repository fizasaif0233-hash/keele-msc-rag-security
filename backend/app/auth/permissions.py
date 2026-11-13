"""Role and document access decisions.

These functions are the authorisation rules used by the API. They take server-side
identity data. They never read a role supplied by the browser.
"""

from uuid import UUID

from app.constants import ACCESS_LEVELS, CONFIGURATIONS


def can_read_document(
    *,
    role: str,
    user_id: UUID,
    document_owner_id: UUID,
    access_level: str,
    explicit_user_ids: set[UUID],
) -> bool:
    if role == "admin":
        return True
    if user_id == document_owner_id:
        return True
    if user_id in explicit_user_ids:
        return True
    if access_level == "public":
        return True
    if access_level == "employee" and role in {"employee", "researcher", "admin"}:
        return True
    return False


def can_upload(role: str, allow_employee_upload: bool) -> bool:
    if role in {"admin", "researcher"}:
        return True
    return role == "employee" and allow_employee_upload


def can_set_access_level(role: str, access_level: str) -> bool:
    if access_level not in ACCESS_LEVELS:
        return False
    if role == "admin":
        return True
    return access_level in {"public", "employee"}


def can_manage_permissions(role: str) -> bool:
    return role == "admin"


def can_delete_document(role: str, user_id: UUID, owner_id: UUID) -> bool:
    return role == "admin" or user_id == owner_id


def can_view_research(role: str) -> bool:
    return role in {"admin", "researcher"}


def can_run_experiments(role: str) -> bool:
    return role in {"admin", "researcher"}


def can_use_baseline_chat(role: str) -> bool:
    return role in {"admin", "researcher"}


def can_view_logs(role: str) -> bool:
    return role in {"admin", "researcher"}


def can_edit_settings(role: str) -> bool:
    return role == "admin"


def assert_configuration_allowed(role: str, configuration: str, *, experiment_execution: bool) -> None:
    """Employees cannot select the baseline chat path.

    The experiment runner may still execute the baseline as an employee actor.
    That path is only available to the server-side runner, which researchers start.
    """

    from app.exceptions import InputRejected, PermissionDenied

    if configuration not in CONFIGURATIONS:
        raise InputRejected("Unknown configuration.")
    if configuration == "baseline" and role == "employee" and not experiment_execution:
        raise PermissionDenied(
            "Baseline chat is limited to researcher and administrator accounts."
        )
