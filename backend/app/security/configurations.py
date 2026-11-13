"""Documented differences between the two experimental configurations.

Interactive chat and the experiment runner both read these flags. Changing a
control means changing the code that consumes the flag, then updating this record
and the research documentation together.
"""

from typing import Any

CONFIGURATION_DEFINITIONS: dict[str, dict[str, Any]] = {
    "baseline": {
        "name": "Baseline RAG",
        "summary": (
            "Authenticated RAG over the same synthetic corpus, with permission "
            "filtering, prompt separation, strict input limits, output validation, "
            "and RAG security-decision logging turned off."
        ),
        "authentication_required": True,
        "permission_filtered_retrieval": False,
        "trusted_untrusted_separation": False,
        "input_validation": "infrastructure_limits_only",
        "output_validation": False,
        "security_decision_logging": False,
        "document_management_authorisation": True,
    },
    "secured": {
        "name": "Secured RAG",
        "summary": (
            "The same model, embeddings, corpus, and retrieval depth, with "
            "permission-filtered retrieval, trusted/untrusted prompt separation, "
            "stricter input handling, synthetic-marker output checks, and "
            "security-decision logging."
        ),
        "authentication_required": True,
        "permission_filtered_retrieval": True,
        "trusted_untrusted_separation": True,
        "input_validation": "strict",
        "output_validation": True,
        "security_decision_logging": True,
        "document_management_authorisation": True,
    },
}

ALWAYS_ON_CONTROLS = [
    "A valid Supabase access token is required for every application request.",
    "Roles are read from the profiles table, never from the browser or token metadata.",
    "Document list, download, preview, and delete operations enforce ownership and access level.",
    "Uploads are restricted to PDF and TXT and are size-limited.",
    "An absolute input-length ceiling is enforced in both configurations.",
    "API secrets are read from server environment variables.",
    "Row Level Security denies direct Data API access to application tables.",
    "Infrastructure failures are recorded separately and are not treated as successful defences.",
]


def describe_configurations() -> dict[str, Any]:
    return {
        "configurations": CONFIGURATION_DEFINITIONS,
        "always_on": ALWAYS_ON_CONTROLS,
        "shared_experimental_factors": [
            "LLM model",
            "Embedding model",
            "Synthetic dataset",
            "Test cases",
            "Top-k and similarity threshold, unless the researcher overrides them for a run",
            "Evaluation criteria",
        ],
    }
