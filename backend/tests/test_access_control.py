from uuid import uuid4

import pytest
from app.auth.jwt import identity_from_claims, profile_defaults_from_identity
from app.auth.permissions import (
    assert_configuration_allowed,
    can_manage_permissions,
    can_read_document,
    can_upload,
)
from app.exceptions import PermissionDenied
from app.security.scope import require_explicit_scope, resolve_document_scope


def test_token_role_is_not_part_of_identity():
    identity = identity_from_claims({"sub": "6b1f3c2e-1b2a-4c3d-9e8f-112233445566", "email": "a@example.com", "role": "admin"})
    assert identity == {"id": "6b1f3c2e-1b2a-4c3d-9e8f-112233445566", "email": "a@example.com"}
    assert profile_defaults_from_identity(identity)["role"] == "employee"


def test_document_access_matrix():
    owner = uuid4()
    other = uuid4()
    stranger = uuid4()
    assert can_read_document(
        role="employee", user_id=other, document_owner_id=owner, access_level="admin", explicit_user_ids=set()
    ) is False
    assert can_read_document(
        role="admin", user_id=other, document_owner_id=owner, access_level="admin", explicit_user_ids=set()
    ) is True
    assert can_read_document(
        role="employee", user_id=other, document_owner_id=owner, access_level="public", explicit_user_ids=set()
    ) is True
    assert can_read_document(
        role="employee",
        user_id=other,
        document_owner_id=owner,
        access_level="confidential",
        explicit_user_ids={other},
    ) is True
    assert can_read_document(
        role="employee",
        user_id=stranger,
        document_owner_id=owner,
        access_level="confidential",
        explicit_user_ids={other},
    ) is False
    assert can_read_document(
        role="researcher", user_id=other, document_owner_id=owner, access_level="employee", explicit_user_ids=set()
    ) is True
    assert can_read_document(
        role="employee", user_id=other, document_owner_id=owner, access_level="hr", explicit_user_ids=set()
    ) is False
    assert can_read_document(
        role="admin", user_id=other, document_owner_id=owner, access_level="hr", explicit_user_ids=set()
    ) is True
    assert can_manage_permissions("researcher") is False
    assert can_manage_permissions("admin") is True
    assert can_upload("employee", False) is False
    assert can_upload("employee", True) is True


def test_employee_cannot_select_baseline_chat():
    with pytest.raises(PermissionDenied):
        assert_configuration_allowed("employee", "baseline", experiment_execution=False)
    assert_configuration_allowed("employee", "baseline", experiment_execution=True)
    assert_configuration_allowed("researcher", "baseline", experiment_execution=False)


def test_secured_scope_never_falls_back_to_full_corpus():
    allowed = {uuid4()}
    ready = allowed | {uuid4(), uuid4()}
    foreign = uuid4()
    ready.add(foreign)
    scope, decisions = resolve_document_scope(
        configuration="secured",
        requested_ids={foreign},
        authorised_ids=allowed,
        all_ready_ids=ready,
    )
    assert scope == set()
    assert "denied_unauthorised_document_ids" in decisions

    empty, _ = resolve_document_scope(
        configuration="secured",
        requested_ids=None,
        authorised_ids=set(),
        all_ready_ids=ready,
    )
    assert empty == set()
    assert empty != ready


def test_baseline_scope_can_include_unauthorised_documents():
    allowed = {uuid4()}
    foreign = uuid4()
    ready = allowed | {foreign}
    scope, decisions = resolve_document_scope(
        configuration="baseline",
        requested_ids={foreign},
        authorised_ids=allowed,
        all_ready_ids=ready,
    )
    assert scope == {foreign}
    assert "baseline_included_unauthorised_ids" in decisions
    full, full_decisions = resolve_document_scope(
        configuration="baseline",
        requested_ids=None,
        authorised_ids=allowed,
        all_ready_ids=ready,
    )
    assert full == ready
    assert "baseline_full_corpus" in full_decisions


def test_retrieval_rejects_an_implicit_full_scan():
    with pytest.raises(ValueError):
        require_explicit_scope(None)
    assert require_explicit_scope([]) == []
