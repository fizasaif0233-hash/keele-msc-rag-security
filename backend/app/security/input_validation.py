import re
from dataclasses import dataclass

from app.constants import ABSOLUTE_MAX_INPUT_CHARS, ABSOLUTE_MAX_UPLOAD_BYTES
from app.exceptions import InputRejected

SUSPICIOUS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(r"ignore (all |any |the )?(previous|prior|above) instructions", re.IGNORECASE),
    ),
    ("role_override", re.compile(r"you are now", re.IGNORECASE)),
    (
        "system_prompt_exfiltration",
        re.compile(r"(system prompt|developer message)", re.IGNORECASE),
    ),
    (
        "privilege_escalation",
        re.compile(r"\b(make me an? admin|set my role to admin)\b", re.IGNORECASE),
    ),
)

ALLOWED_UPLOADS = {
    ".txt": {"text/plain", "application/octet-stream", "text/utf-8", ""},
    ".pdf": {"application/pdf", "application/octet-stream", ""},
}


@dataclass
class InputValidationResult:
    text: str
    rejected: bool
    reason: str | None
    suspicious_labels: list[str]


def _limit_for(configuration: str, runtime: dict) -> int:
    if configuration == "secured":
        configured = int(runtime.get("max_input_chars_secured", 4000))
    else:
        configured = int(runtime.get("max_input_chars_baseline", 12000))
    return max(1, min(configured, ABSOLUTE_MAX_INPUT_CHARS))


def validate_question(text: str | None, configuration: str, runtime: dict) -> InputValidationResult:
    if text is None or not str(text).strip():
        return InputValidationResult("", True, "The question must not be empty.", [])
    if "\x00" in text:
        return InputValidationResult("", True, "The question contains invalid characters.", [])

    cleaned = "".join(character for character in text if character in "\n\t\r" or ord(character) >= 32)
    cleaned = cleaned.strip()
    if not cleaned:
        return InputValidationResult("", True, "The question must not be empty.", [])

    limit = _limit_for(configuration, runtime)
    if len(cleaned) > limit:
        return InputValidationResult(
            cleaned,
            True,
            f"The question exceeds the {limit} character limit for the {configuration} configuration.",
            [],
        )

    labels = [name for name, pattern in SUSPICIOUS_PATTERNS if pattern.search(cleaned)]
    return InputValidationResult(cleaned, False, None, labels)


def validate_upload(filename: str | None, content_type: str | None, size: int, max_bytes: int) -> str:
    """Validate an upload before it is stored. Returns the accepted extension."""

    ceiling = min(max(1, int(max_bytes)), ABSOLUTE_MAX_UPLOAD_BYTES)
    if size <= 0:
        raise InputRejected("The file is empty.")
    if size > ceiling:
        raise InputRejected("The file exceeds the configured size limit.")

    extension = ""
    if filename and "." in filename:
        extension = "." + filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_UPLOADS:
        raise InputRejected("Only PDF and TXT files are accepted.")

    media_type = (content_type or "").split(";")[0].strip().lower()
    if media_type not in ALLOWED_UPLOADS[extension]:
        raise InputRejected("The file type does not match an accepted PDF or TXT type.")
    return extension


def clean_text(text: str) -> str:
    without_nulls = text.replace("\x00", "")
    normalised = without_nulls.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalised.split("\n")]
    compact: list[str] = []
    blank = 0
    for line in lines:
        if not line:
            blank += 1
            if blank <= 2:
                compact.append("")
            continue
        blank = 0
        compact.append(line)
    return "\n".join(compact).strip()
