"""Write the stored paired-run trials to CSV and JSON. Prints counts only."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import get_session_factory
from app.models import Experiment
from app.services.reporting import build_report, csv_safe, load_trials
from sqlalchemy import select

GROUP = UUID("6a65fe15-9e7c-4ca8-8892-cf2d9584e655")
RUN_NAME = "Synthetic suite paired run 2026-11-13"
OUT = ROOT.parent / "dissertation" / "EVIDENCE"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    db = get_session_factory()()
    try:
        experiments = db.scalars(
            select(Experiment).where(Experiment.comparison_group == GROUP, Experiment.name == RUN_NAME)
        ).all()
        ids = [item.id for item in experiments]
        trials = load_trials(db, ids)
        report = build_report(db, ids)
    finally:
        db.close()
    payload = {
        "comparison_group": str(GROUP),
        "run_name": RUN_NAME,
        "exported_on": "2026-11-18",
        "experiment_ids": [str(item) for item in ids],
        "report": report,
        "results": trials,
    }
    (OUT / "paired-run-2026-11-13.json").write_text(
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
    with (OUT / "paired-run-2026-11-13.csv").open("w", encoding="utf-8", newline="") as handle:
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


if __name__ == "__main__":
    main()
