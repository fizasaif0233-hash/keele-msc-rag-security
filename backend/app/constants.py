"""Shared constants. The embedding dimension must match the SQL migration."""

EMBEDDING_DIMENSIONS = 1536

# Infrastructure ceiling. Configuration-specific limits cannot exceed this.
ABSOLUTE_MAX_INPUT_CHARS = 20000
ABSOLUTE_MAX_UPLOAD_BYTES = 20 * 1024 * 1024

KNOWN_MARKERS = (
    "SYNTHETIC_HR_SECRET_001",
    "SYNTHETIC_FINANCE_SECRET_002",
    "SYNTHETIC_ADMIN_SECRET_003",
    "SYNTHETIC_PERSONAL_SECRET_004",
)

ROLES = ("admin", "employee", "researcher")
CONFIGURATIONS = ("baseline", "secured")
ACCESS_LEVELS = ("public", "employee", "hr", "confidential", "admin")
ATTACK_CATEGORIES = (
    "direct_prompt_injection",
    "indirect_prompt_injection",
    "unauthorised_disclosure",
    "input_validation",
)
TEST_CATEGORIES = ("benign",) + ATTACK_CATEGORIES

SYNTHETIC_USERS = {
    "admin": "admin.synthetic@keele-rag.example",
    "employee": "employee.synthetic@keele-rag.example",
    "employee_two": "employee2.synthetic@keele-rag.example",
    "researcher": "researcher.synthetic@keele-rag.example",
}
