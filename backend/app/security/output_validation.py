import re
from dataclasses import dataclass

from app.constants import KNOWN_MARKERS

# Characters that can be inserted into a marker without changing how it reads.
_INVISIBLE = re.compile(r"[\u200b\u200c\u200d\ufeff]")


@dataclass
class OutputValidation:
    answer: str
    redacted: bool
    emitted_markers: list[str]
    visible_markers: list[str]
    redacted_markers: list[str]


def markers_in_text(text: str | None, markers: list[str] | tuple[str, ...]) -> list[str]:
    if not text:
        return []
    return [marker for marker in markers if marker and marker in text]


def split_marker_access(
    documents: list[dict],
    readable_ids: set[str],
    *,
    role: str,
) -> tuple[set[str], set[str]]:
    """Return authorised and unauthorised markers.

    `documents` contains mappings with `id` and `protected_markers`.
    A marker is unauthorised when it belongs to a document the caller cannot read,
    or when it is a known marker that the caller is not allowed to see.
    """

    authorised: set[str] = set()
    unauthorised: set[str] = set()
    for document in documents:
        markers = set(document.get("protected_markers") or [])
        if str(document.get("id")) in readable_ids:
            authorised.update(markers)
        else:
            unauthorised.update(markers)
    unauthorised -= authorised
    if role != "admin":
        for marker in KNOWN_MARKERS:
            if marker not in authorised:
                unauthorised.add(marker)
    return authorised, unauthorised


def apply_output_validation(
    answer: str,
    *,
    configuration: str,
    unauthorised_markers: set[str],
) -> OutputValidation:
    catalogue = list(dict.fromkeys([*KNOWN_MARKERS, *sorted(unauthorised_markers)]))
    if configuration != "secured":
        emitted = markers_in_text(answer, catalogue)
        return OutputValidation(
            answer=answer,
            redacted=False,
            emitted_markers=emitted,
            visible_markers=emitted,
            redacted_markers=[],
        )

    # Baseline keeps the original text. Secured removes invisible characters and
    # then redacts unauthorised markers without requiring the model's exact case.
    working = _INVISIBLE.sub("", answer)
    comparable = _INVISIBLE.sub("", answer)
    redacted_markers: list[str] = []
    for marker in sorted(unauthorised_markers, key=len, reverse=True):
        if not marker:
            continue
        pattern = re.compile(re.escape(marker), re.IGNORECASE)
        if pattern.search(working):
            redacted_markers.append(marker)
            working = pattern.sub("[REDACTED_PROTECTED_MARKER]", working)
    folded = comparable.casefold()
    emitted = markers_in_text(comparable, catalogue)
    for marker in catalogue:
        if marker not in emitted and marker.casefold() in folded:
            emitted.append(marker)
    visible = markers_in_text(working, catalogue)
    return OutputValidation(
        answer=working,
        redacted=bool(redacted_markers),
        emitted_markers=emitted,
        visible_markers=visible,
        redacted_markers=redacted_markers,
    )
