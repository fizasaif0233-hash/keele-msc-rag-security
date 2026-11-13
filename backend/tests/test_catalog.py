from pathlib import Path

from app.constants import KNOWN_MARKERS
from app.seed.catalog import DATASET_NAME, DOCUMENTS, SEED_CASES, synthetic_corpus_titles

FILES = Path(__file__).resolve().parents[1] / "app" / "seed" / "files"


def test_official_dataset_records_only_the_synthetic_titles():
    assert synthetic_corpus_titles(DATASET_NAME) == [item["title"] for item in DOCUMENTS]
    assert synthetic_corpus_titles("A researcher dataset") is None


def test_synthetic_files_exist_and_markers_are_only_in_restricted_documents():
    indirect = (FILES / "document_with_indirect_injection.txt").read_text(encoding="utf-8")
    for marker in KNOWN_MARKERS:
        assert marker not in indirect
    assert "SYNTHETIC_HR_SECRET_001" in (FILES / "hr_confidential_policy.txt").read_text(encoding="utf-8")
    assert "SYNTHETIC_FINANCE_SECRET_002" in (FILES / "finance_internal_report.txt").read_text(encoding="utf-8")
    assert "SYNTHETIC_ADMIN_SECRET_003" in (FILES / "administrator_security_policy.txt").read_text(encoding="utf-8")
    assert "SYNTHETIC_PERSONAL_SECRET_004" in (FILES / "employee_personal_note.txt").read_text(encoding="utf-8")
    assert "09:00" in (FILES / "public_faq.txt").read_text(encoding="utf-8")
    filenames = {item["filename"] for item in DOCUMENTS}
    assert filenames == {path.name for path in FILES.glob("*.txt")}


def test_seed_cases_cover_every_category_and_have_stable_keys():
    categories = {case["category"] for case in SEED_CASES}
    assert categories == {
        "benign",
        "direct_prompt_injection",
        "indirect_prompt_injection",
        "unauthorised_disclosure",
        "input_validation",
    }
    keys = [case["seed_key"] for case in SEED_CASES]
    assert len(keys) == len(set(keys))
    for case in SEED_CASES:
        assert case["evaluation_criteria"]["seed_key"] == case["seed_key"]
    horizontal = next(case for case in SEED_CASES if case["seed_key"] == "unauth-horizontal")
    assert horizontal["evaluation_criteria"]["requested_document_titles"] == ["Employee personal note"]
