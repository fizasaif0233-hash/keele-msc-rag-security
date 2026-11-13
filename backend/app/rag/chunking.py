from app.security.input_validation import clean_text


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split cleaned text into overlapping character windows."""

    cleaned = clean_text(text)
    if not cleaned:
        return []
    window = max(200, int(size))
    step_overlap = max(0, int(overlap))
    if step_overlap >= window:
        step_overlap = window // 5
    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + window, length)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(0, end - step_overlap)
        if start >= length:
            break
    return chunks
