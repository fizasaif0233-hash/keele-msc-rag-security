"""Run an experiment from the command line and wait for it to finish."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.database import get_session_factory
from app.evaluation.runner import ensure_idle, execute_experiments
from app.models import Experiment, Profile, TestCase, TestDataset
from app.seed.catalog import DATASET_NAME, synthetic_corpus_titles
from app.services.runtime import get_runtime_settings
from sqlalchemy import func, select


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a stored evaluation experiment.")
    parser.add_argument("--email", required=True, help="Researcher or administrator email.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--configurations", nargs="+", choices=["baseline", "secured"], required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--dataset", default=DATASET_NAME)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 20:
        raise SystemExit("Repetitions must be between 1 and 20.")
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured.")

    session = get_session_factory()()
    try:
        actor = session.scalar(select(Profile).where(func.lower(Profile.email) == args.email.strip().lower()))
        if actor is None or actor.role not in {"admin", "researcher"}:
            raise SystemExit("The email must belong to an existing researcher or administrator.")
        dataset = session.scalar(select(TestDataset).where(TestDataset.name == args.dataset))
        if dataset is None:
            raise SystemExit("Dataset not found. Run scripts/seed.py first.")
        case_count = session.scalar(
            select(func.count()).select_from(TestCase).where(TestCase.dataset_id == dataset.id)
        )
        if not case_count:
            raise SystemExit("The dataset has no test cases.")
        ensure_idle(session)
        runtime = get_runtime_settings(session)
        group = uuid4()
        created = []
        for configuration in dict.fromkeys(args.configurations):
            experiment = Experiment(
                name=args.name.strip(),
                configuration=configuration,
                dataset_id=dataset.id,
                repetitions=args.repetitions,
                status="running",
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
                    "corpus_titles": synthetic_corpus_titles(dataset.name),
                },
                comparison_group=group,
                created_by=actor.id,
                started_at=datetime.now(timezone.utc),
                progress_total=int(case_count) * args.repetitions,
            )
            session.add(experiment)
            created.append(experiment)
        session.commit()
        identifiers = [experiment.id for experiment in created]
    finally:
        session.close()

    execute_experiments(identifiers)
    print("Experiment run finished. Review the results in the evaluation page.")


if __name__ == "__main__":
    main()
