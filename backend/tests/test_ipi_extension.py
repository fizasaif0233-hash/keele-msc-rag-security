from pathlib import Path

from app.constants import KNOWN_MARKERS
from app.seed.ipi_extension import IPI_CASES, IPI_DOCUMENTS

FILES = Path(__file__).resolve().parents[1] / "app" / "seed" / "files"


def test_ten_indirect_cases_do_not_contain_markers():
    assert len(IPI_CASES) == 10
    assert len({case["seed_key"] for case in IPI_CASES}) == 10
    for case in IPI_CASES:
        assert case["category"] == "indirect_prompt_injection"
        assert case["evaluation_criteria"]["actor_role"] == "employee"
        for marker in KNOWN_MARKERS:
            assert marker not in case["input"]


def test_indirect_documents_do_not_contain_markers():
    assert len(IPI_DOCUMENTS) == 12
    for spec in IPI_DOCUMENTS:
        text = (FILES / spec["filename"]).read_text(encoding="utf-8")
        assert spec["access_level"] == "public"
        for marker in KNOWN_MARKERS:
            assert marker not in text
