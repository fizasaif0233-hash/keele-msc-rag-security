"""Second indirect run, plus the conventional baseline, on the same ten cases.

The first indirect export is not overwritten. The 13 November and 19 November
studies are not read or updated.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select, text

from app.config import settings
from app.database import get_engine, get_session_factory
from app.evaluation.runner import ensure_idle, execute_experiments
from app.models import Experiment, Profile, TestCase
from app.seed.ipi_extension import IPI_STUDY_NAME, ipi_corpus_titles
from app.services.runtime import get_runtime_settings
from scripts.run_ipi_study import (
    ACTOR_EMAIL,
    CONFIGURATIONS,
    REPETITIONS,
    _check_cases,
    _ensure_dataset,
    _ensure_documents,
    _export,
)

MIGRATION = ROOT.parent / "supabase" / "migrations" / "0004_conventional_configuration.sql"
REPRO_NAME = "Indirect extension reproduction 2026-11-21"
CONVENTIONAL_NAME = "Conventional baseline indirect 2026-11-21"


def _apply_migration() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    with get_engine().begin() as connection:
        connection.exec_driver_sql(sql)
    print("migration applied", flush=True)


def _create(session, actor, dataset, name: str, configurations: tuple[str, ...]) -> list:
    existing = session.scalars(select(Experiment).where(Experiment.name == name)).all()
    if existing:
        return [item.id for item in existing if item.status != "completed"]
    ensure_idle(session)
    runtime = get_runtime_settings(session)
    group = uuid4()
    case_count = session.scalar(
        select(func.count()).select_from(TestCase).where(TestCase.dataset_id == dataset.id)
    )
    created = []
    for configuration in configurations:
        experiment = Experiment(
            name=name,
            configuration=configuration,
            dataset_id=dataset.id,
            repetitions=REPETITIONS,
            status="pending",
            parameters={
                "llm_model": runtime.get("llm_model"),
                "embedding_model": runtime.get("embedding_model"),
                "top_k": len(ipi_corpus_titles()),
                "similarity_threshold": runtime.get("similarity_threshold"),
                "temperature": runtime.get("temperature"),
                "chunk_size": runtime.get("chunk_size"),
                "chunk_overlap": runtime.get("chunk_overlap"),
                "max_input_chars_secured": runtime.get("max_input_chars_secured"),
                "max_input_chars_baseline": runtime.get("max_input_chars_baseline"),
                "corpus_titles": ipi_corpus_titles(),
                "study": name,
            },
            comparison_group=group,
            created_by=actor.id,
            progress_total=int(case_count) * REPETITIONS,
        )
        session.add(experiment)
        created.append(experiment)
    session.commit()
    return [item.id for item in created]


def _export_named(session, name: str, filename: str) -> None:
    experiments = session.scalars(select(Experiment).where(Experiment.name == name)).all()
    if not experiments or any(item.status != "completed" for item in experiments):
        statuses = {item.configuration: item.status for item in experiments}
        raise SystemExit(f"{name} did not complete: {statuses}")
    evidence = ROOT.parent / "dissertation" / "EVIDENCE"
    original_json = evidence / "ipi-extension-2026-11-21.json"
    original_csv = evidence / "ipi-extension-2026-11-21.csv"
    backup_json = evidence / "_ipi_original_backup.json"
    backup_csv = evidence / "_ipi_original_backup.csv"
    shutil.copyfile(original_json, backup_json)
    shutil.copyfile(original_csv, backup_csv)
    import scripts.run_ipi_study as ipi

    ipi.IPI_STUDY_NAME = name
    ipi.CONFIGURATIONS = tuple(sorted({item.configuration for item in experiments}))
    try:
        ipi._export(session, list(experiments))
        original_json.replace(evidence / filename)
        if original_csv.exists():
            original_csv.replace(evidence / Path(filename).with_suffix(".csv").name)
    finally:
        if backup_json.exists():
            shutil.move(backup_json, original_json)
        if backup_csv.exists() and not original_csv.exists():
            shutil.move(backup_csv, original_csv)
        ipi.IPI_STUDY_NAME = IPI_STUDY_NAME
        ipi.CONFIGURATIONS = CONFIGURATIONS
    print(f"saved {filename}", flush=True)


def main() -> None:
    if not settings.database_url or not settings.llm_api_key:
        raise SystemExit("DATABASE_URL and LLM_API_KEY are required.")
    _check_cases()
    _apply_migration()
    session = get_session_factory()()
    try:
        admin = session.scalar(select(Profile).where(Profile.email == "admin.synthetic@keele-rag.example"))
        actor = session.scalar(select(Profile).where(Profile.email == ACTOR_EMAIL))
        if admin is None or actor is None or actor.role not in {"admin", "researcher"}:
            raise SystemExit("The synthetic administrator or researcher profile is not available.")
        _ensure_documents(session, {"admin": admin})
        dataset = _ensure_dataset(session, actor)
        pending = []
        pending.extend(_create(session, actor, dataset, REPRO_NAME, CONFIGURATIONS))
        pending.extend(_create(session, actor, dataset, CONVENTIONAL_NAME, ("conventional",)))
        session.commit()
        print(f"pending {len(pending)}", flush=True)
    finally:
        session.close()

    if pending:
        execute_experiments(pending)

    session = get_session_factory()()
    try:
        _export_named(session, REPRO_NAME, "ipi-reproduction-2026-11-21.json")
        _export_named(session, CONVENTIONAL_NAME, "conventional-baseline-2026-11-21.json")
    finally:
        session.close()


if __name__ == "__main__":
    main()
