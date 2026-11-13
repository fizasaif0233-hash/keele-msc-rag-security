"""Load stored trials and calculate reports. Empty tables produce an empty report."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.metrics import compare_configurations, summarise, summarise_by_category
from app.models import Experiment, TestCase, TestResult


def csv_safe(value: object) -> str:
    """Stop a text cell from being executed as a formula when the file is opened."""

    if value is None:
        return ""
    text = str(value)
    if text[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + text
    return text


def load_trials(db: Session, experiment_ids: list[UUID] | None = None) -> list[dict]:
    query = (
        select(TestResult, Experiment, TestCase)
        .join(Experiment, Experiment.id == TestResult.experiment_id)
        .join(TestCase, TestCase.id == TestResult.test_case_id)
    )
    if experiment_ids:
        query = query.where(Experiment.id.in_(experiment_ids))
    rows = db.execute(query).all()
    trials = []
    for result, experiment, case in rows:
        details = result.evaluation_details or {}
        trials.append(
            {
                "result_id": str(result.id),
                "experiment_id": str(experiment.id),
                "experiment_name": experiment.name,
                "experiment_status": experiment.status,
                "test_case_id": str(case.id),
                "test_title": case.title,
                "test_description": case.description,
                "category": case.category,
                "configuration": experiment.configuration,
                "repetition_number": result.repetition_number,
                "expected_outcome": case.expected_outcome,
                "actual_outcome": result.actual_outcome,
                "attack_success": result.attack_success,
                "information_disclosed": result.information_disclosed,
                "legitimate_task_success": result.legitimate_task_success,
                "response_latency_ms": result.response_latency_ms,
                "error_message": result.error_message,
                "created_at": result.created_at,
                "is_attack": bool(details.get("is_attack", case.category != "benign")),
                "is_benign": bool(details.get("is_benign", case.category == "benign")),
                "counts_toward_rates": bool(
                    details.get("counts_toward_rates", result.actual_outcome != "infrastructure_failure")
                ),
                "evaluation_details": details,
                "input": case.input,
            }
        )
    return trials


def build_report(db: Session, experiment_ids: list[UUID] | None = None) -> dict:
    trials = load_trials(db, experiment_ids)
    by_configuration: dict[str, dict] = {}
    for name in ("baseline", "secured"):
        subset = [trial for trial in trials if trial["configuration"] == name]
        summary = summarise(subset)
        summary["has_results"] = summary["completed_trials"] > 0
        by_configuration[name] = summary
    has_results = any(item["has_results"] for item in by_configuration.values())
    return {
        "has_results": has_results,
        "trial_count": len(trials),
        "by_configuration": by_configuration,
        "reductions": compare_configurations(by_configuration) if has_results else None,
        "category_breakdown": summarise_by_category(trials) if trials else [],
        "outcome_distribution": _outcome_distribution(trials),
    }


def _outcome_distribution(trials: list[dict]) -> list[dict]:
    counts: dict[tuple[str, str], int] = {}
    for trial in trials:
        key = (trial["configuration"], trial["actual_outcome"])
        counts[key] = counts.get(key, 0) + 1
    return [
        {"configuration": configuration, "outcome": outcome, "count": count}
        for (configuration, outcome), count in sorted(counts.items())
    ]
