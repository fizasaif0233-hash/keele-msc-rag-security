"""Metric calculations.

Rates are None when the denominator is zero. They are never replaced with a
placeholder zero, because a measured zero and an absent result are different.
"""

import math
from collections import Counter
from typing import Any


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return (numerator / denominator) * 100


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (percent / 100) * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[low])
    weight = rank - low
    return float(ordered[low] * (1 - weight) + ordered[high] * weight)


def reduction(baseline: float | None, secured: float | None) -> dict[str, Any]:
    if baseline is None or secured is None:
        return {
            "percentage_reduction": None,
            "absolute_reduction": None,
            "note": "Insufficient measured trials.",
        }
    absolute = baseline - secured
    if baseline == 0:
        return {
            "percentage_reduction": None,
            "absolute_reduction": absolute,
            "note": "Percentage reduction is undefined because the baseline rate is zero.",
        }
    return {
        "percentage_reduction": (absolute / baseline) * 100,
        "absolute_reduction": absolute,
        "note": None,
    }


def summarise(trials: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [
        trial
        for trial in trials
        if trial.get("counts_toward_rates", True)
        and trial.get("actual_outcome") != "infrastructure_failure"
    ]
    attacks = [trial for trial in completed if trial.get("is_attack")]
    benign = [trial for trial in completed if trial.get("is_benign")]
    latencies = [
        float(trial["response_latency_ms"])
        for trial in completed
        if trial.get("response_latency_ms") is not None
    ]
    disclosures = sum(1 for trial in completed if trial.get("information_disclosed"))
    attack_successes = sum(1 for trial in attacks if trial.get("attack_success"))
    legitimate = sum(1 for trial in benign if trial.get("legitimate_task_success"))
    average = (sum(latencies) / len(latencies)) if latencies else None
    return {
        "completed_trials": len(completed),
        "excluded_infrastructure_failures": sum(
            1 for trial in trials if trial.get("actual_outcome") == "infrastructure_failure"
        ),
        "excluded_other": sum(
            1
            for trial in trials
            if not trial.get("counts_toward_rates", True)
            and trial.get("actual_outcome") != "infrastructure_failure"
        ),
        "attack_trials": len(attacks),
        "attack_successes": attack_successes,
        "attack_success_rate": _rate(attack_successes, len(attacks)),
        "disclosure_count": disclosures,
        "disclosure_rate": _rate(disclosures, len(completed)),
        "benign_trials": len(benign),
        "legitimate_successes": legitimate,
        "legitimate_task_success_rate": _rate(legitimate, len(benign)),
        "average_latency_ms": average,
        "median_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "outcome_counts": dict(Counter(trial.get("actual_outcome") for trial in trials)),
    }


def summarise_by_category(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trial in trials:
        key = (str(trial.get("category") or "unknown"), str(trial.get("configuration") or "unknown"))
        grouped.setdefault(key, []).append(trial)
    rows = []
    for (category, configuration), items in sorted(grouped.items()):
        summary = summarise(items)
        rows.append(
            {
                "category": category,
                "configuration": configuration,
                "attack_success_rate": summary["attack_success_rate"],
                "disclosure_rate": summary["disclosure_rate"],
                "legitimate_task_success_rate": summary["legitimate_task_success_rate"],
                "completed_trials": summary["completed_trials"],
                "attack_trials": summary["attack_trials"],
                "benign_trials": summary["benign_trials"],
            }
        )
    return rows


def compare_configurations(by_configuration: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = by_configuration.get("baseline") or {}
    secured = by_configuration.get("secured") or {}
    return {
        "attack_success_rate": reduction(
            baseline.get("attack_success_rate"), secured.get("attack_success_rate")
        ),
        "disclosure_rate": reduction(baseline.get("disclosure_rate"), secured.get("disclosure_rate")),
        "legitimate_task_success_rate": {
            "absolute_difference": (
                None
                if baseline.get("legitimate_task_success_rate") is None
                or secured.get("legitimate_task_success_rate") is None
                else secured["legitimate_task_success_rate"] - baseline["legitimate_task_success_rate"]
            )
        },
        "average_latency_ms": {
            "absolute_difference": (
                None
                if baseline.get("average_latency_ms") is None or secured.get("average_latency_ms") is None
                else secured["average_latency_ms"] - baseline["average_latency_ms"]
            )
        },
    }
