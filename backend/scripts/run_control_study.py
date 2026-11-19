"""Run the separate five-configuration study.

The 13 November paired run is not read or updated. Partial configurations use the
baseline input limit. Results are written only after the runs finish.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.constants import KNOWN_MARKERS
from app.database import get_session_factory
from app.evaluation.runner import ensure_idle, execute_experiments
from app.models import Experiment, Profile, TestCase, TestDataset
from app.seed.catalog import (
    DATASET_NAME,
    FOLLOWUP_CASES,
    FOLLOWUP_DATASET_NAME,
    SEED_CASES,
    synthetic_corpus_titles,
)
from app.services.reporting import build_report, csv_safe, load_trials
from app.services.runtime import get_runtime_settings
from sqlalchemy import func, select

STUDY_NAME = "Control study 2026-11-19"
CONFIGURATIONS = (
    "baseline",
    "permission_only",
    "prompt_separation_only",
    "redaction_only",
    "secured",
)
REPETITIONS = 5
OUT = ROOT.parent / "dissertation" / "EVIDENCE"
ACTOR_EMAIL = "researcher.synthetic@keele-rag.example"


def _cases() -> list[dict]:
    cases = [*SEED_CASES, *FOLLOWUP_CASES]
    keys = [case["seed_key"] for case in cases]
    if len(keys) != len(set(keys)):
        raise SystemExit("The follow-up case keys are not unique.")
    for case in FOLLOWUP_CASES:
        for marker in KNOWN_MARKERS:
            if marker in case["input"]:
                raise SystemExit("A follow-up question contains a catalogue marker.")
    return cases


def _ensure_dataset(session, actor: Profile) -> TestDataset:
    dataset = session.scalar(select(TestDataset).where(TestDataset.name == FOLLOWUP_DATASET_NAME))
    cases = _cases()
    if dataset is None:
        dataset = TestDataset(
            name=FOLLOWUP_DATASET_NAME,
            description=(
                "Copy of the v1 synthetic cases plus six indirect questions. "
                "This dataset is the 19 November control study. It does not replace dataset v1."
            ),
            created_by=actor.id,
        )
        session.add(dataset)
        session.flush()
    existing = session.scalar(
        select(func.count()).select_from(TestCase).where(TestCase.dataset_id == dataset.id)
    )
    if existing == 0:
        for case in cases:
            session.add(
                TestCase(
                    dataset_id=dataset.id,
                    category=case["category"],
                    title=case["title"],
                    description=case["description"],
                    input=case["input"],
                    expected_outcome=case["expected_outcome"],
                    evaluation_criteria=dict(case["evaluation_criteria"]),
                )
            )
        session.flush()
    elif int(existing) != len(cases):
        raise SystemExit(f"Dataset v2 has {existing} cases; expected {len(cases)}.")
    return dataset


def _export(session, experiments: list[Experiment]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ids = [item.id for item in experiments]
    group = experiments[0].comparison_group
    trials = load_trials(session, ids)
    report = build_report(session, ids)
    payload = {
        "comparison_group": str(group),
        "run_name": STUDY_NAME,
        "dataset": FOLLOWUP_DATASET_NAME,
        "repetitions": REPETITIONS,
        "configurations": list(CONFIGURATIONS),
        "source_dataset": DATASET_NAME,
        "exported_on": datetime.now(timezone.utc).date().isoformat(),
        "experiment_ids": [str(item) for item in ids],
        "report": report,
        "results": trials,
    }
    (OUT / "control-study-2026-11-19.json").write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    fieldnames = [
        "test_title",
        "test_category",
        "configuration",
        "actual_outcome",
        "attack_success",
        "information_disclosed",
        "legitimate_task_success",
        "response_latency_ms",
        "repetition_number",
        "experiment_id",
    ]
    with (OUT / "control-study-2026-11-19.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for trial in trials:
            writer.writerow(
                {
                    "test_title": csv_safe(trial["test_title"]),
                    "test_category": csv_safe(trial["category"]),
                    "configuration": csv_safe(trial["configuration"]),
                    "actual_outcome": csv_safe(trial["actual_outcome"]),
                    "attack_success": trial["attack_success"],
                    "information_disclosed": trial["information_disclosed"],
                    "legitimate_task_success": trial["legitimate_task_success"],
                    "response_latency_ms": trial["response_latency_ms"],
                    "repetition_number": trial["repetition_number"],
                    "experiment_id": trial["experiment_id"],
                }
            )
    print(f"experiments {len(ids)}")
    print(f"trials {len(trials)}")
    for name, summary in report["by_configuration"].items():
        print(
            name,
            "attack",
            summary.get("attack_successes"),
            "/",
            summary.get("attack_trials"),
            "disclosure",
            summary.get("disclosure_count"),
            "/",
            summary.get("completed_trials"),
        )


def main() -> None:
    if not settings.database_url or not settings.llm_api_key:
        raise SystemExit("DATABASE_URL and LLM_API_KEY are required.")
    session = get_session_factory()()
    try:
        actor = session.scalar(select(Profile).where(Profile.email == ACTOR_EMAIL))
        if actor is None or actor.role not in {"admin", "researcher"}:
            raise SystemExit("The researcher account is not available.")
        dataset = _ensure_dataset(session, actor)
        existing = session.scalars(select(Experiment).where(Experiment.name == STUDY_NAME)).all()
        if existing:
            session.commit()
            identifiers = [item.id for item in existing if item.status != "completed"]
            finished = [item for item in existing if item.status == "completed"]
        else:
            ensure_idle(session)
            runtime = get_runtime_settings(session)
            group = uuid4()
            case_count = session.scalar(
                select(func.count()).select_from(TestCase).where(TestCase.dataset_id == dataset.id)
            )
            created = []
            for configuration in CONFIGURATIONS:
                experiment = Experiment(
                    name=STUDY_NAME,
                    configuration=configuration,
                    dataset_id=dataset.id,
                    repetitions=REPETITIONS,
                    status="pending",
                    parameters={
                        "llm_model": runtime.get("llm_model"),
                        "embedding_model": runtime.get("embedding_model"),
                        "top_k": runtime.get("top_k"),
                        "similarity_threshold": runtime.get("similarity_threshold"),
                        "temperature": runtime.get("temperature"),
                        "chunk_size": runtime.get("chunk_size"),
                        "chunk_overlap": runtime.get("chunk_overlap"),
                        "max_input_chars_secured": runtime.get("max_input_chars_secured"),
                        "max_input_chars_baseline": runtime.get("max_input_chars_baseline"),
                        "corpus_titles": synthetic_corpus_titles(DATASET_NAME),
                        "study": "five_configuration_control_study",
                    },
                    comparison_group=group,
                    created_by=actor.id,
                    progress_total=int(case_count) * REPETITIONS,
                )
                session.add(experiment)
                created.append(experiment)
            session.commit()
            identifiers = [item.id for item in created]
            finished = []
        print(f"pending {len(identifiers)} completed {len(finished)}", flush=True)
    finally:
        session.close()

    if identifiers:
        execute_experiments(identifiers)

    session = get_session_factory()()
    try:
        experiments = session.scalars(select(Experiment).where(Experiment.name == STUDY_NAME)).all()
        if not experiments or any(item.status != "completed" for item in experiments):
            statuses = {item.configuration: item.status for item in experiments}
            raise SystemExit(f"Control study did not complete: {statuses}")
        _export(session, list(experiments))
    finally:
        session.close()


if __name__ == "__main__":
    main()
