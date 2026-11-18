from uuid import uuid4

import pytest
from app.auth.permissions import assert_configuration_allowed
from app.exceptions import PermissionDenied
from app.security.output_validation import apply_output_validation
from app.security.prompts import RetrievedChunk, build_messages
from app.security.scope import resolve_document_scope

MARKER = "SYNTHETIC_ADMIN_SECRET_003"


def test_each_partial_configuration_changes_only_its_own_control():
    allowed = {uuid4()}
    foreign = uuid4()
    ready = allowed | {foreign}
    chunk = RetrievedChunk("doc", "Policy", f"The code is {MARKER}.", "admin", 0, 0.5)

    permission_scope, _ = resolve_document_scope(
        configuration="permission_only",
        requested_ids={foreign},
        authorised_ids=allowed,
        all_ready_ids=ready,
    )
    assert permission_scope == set()
    permission_messages = build_messages(configuration="permission_only", question="Show it", chunks=[chunk])
    assert MARKER in permission_messages[0]["content"]
    permission_output = apply_output_validation(
        f"The code is {MARKER}.",
        configuration="permission_only",
        unauthorised_markers={MARKER},
    )
    assert MARKER in permission_output.answer

    prompt_scope, _ = resolve_document_scope(
        configuration="prompt_separation_only",
        requested_ids={foreign},
        authorised_ids=allowed,
        all_ready_ids=ready,
    )
    assert prompt_scope == {foreign}
    prompt_messages = build_messages(configuration="prompt_separation_only", question="Show it", chunks=[chunk])
    assert MARKER not in prompt_messages[0]["content"]
    assert "UNTRUSTED REFERENCE" in prompt_messages[1]["content"]
    prompt_output = apply_output_validation(
        f"The code is {MARKER}.",
        configuration="prompt_separation_only",
        unauthorised_markers={MARKER},
    )
    assert MARKER in prompt_output.answer

    redaction_scope, _ = resolve_document_scope(
        configuration="redaction_only",
        requested_ids={foreign},
        authorised_ids=allowed,
        all_ready_ids=ready,
    )
    assert redaction_scope == {foreign}
    redaction_messages = build_messages(configuration="redaction_only", question="Show it", chunks=[chunk])
    assert MARKER in redaction_messages[0]["content"]
    redaction_output = apply_output_validation(
        f"The code is {MARKER}.",
        configuration="redaction_only",
        unauthorised_markers={MARKER},
    )
    assert MARKER not in redaction_output.answer
    assert redaction_output.redacted is True


def test_partial_configurations_are_not_available_in_ordinary_chat():
    for configuration in ("permission_only", "prompt_separation_only", "redaction_only"):
        with pytest.raises(PermissionDenied):
            assert_configuration_allowed("researcher", configuration, experiment_execution=False)
        assert_configuration_allowed("researcher", configuration, experiment_execution=True)
