"""Print category and repetition counts for the 19 November control study."""

import json
from collections import defaultdict
from pathlib import Path

data = json.loads(
    (Path(__file__).resolve().parents[2] / "dissertation" / "EVIDENCE" / "control-study-2026-11-19.json").read_text(
        encoding="utf-8"
    )
)
trials = data["results"]
print("group", data["comparison_group"])
print("exported", data["exported_on"])


def done(trial: dict) -> bool:
    return trial.get("counts_toward_rates", True) and trial.get("actual_outcome") != "infrastructure_failure"


for name in ("baseline", "permission_only", "prompt_separation_only", "redaction_only", "secured"):
    by_rep: dict[int, int] = defaultdict(int)
    den: dict[int, int] = defaultdict(int)
    for trial in trials:
        if trial["configuration"] != name or not done(trial):
            continue
        if trial["category"] == "input_validation" or not trial.get("is_attack"):
            continue
        den[trial["repetition_number"]] += 1
        if trial.get("attack_success"):
            by_rep[trial["repetition_number"]] += 1
    print(name, {rep: f"{by_rep[rep]}/{den[rep]}" for rep in sorted(den)})

print("baseline indirect")
for trial in trials:
    if (
        trial["configuration"] == "baseline"
        and trial["category"] == "indirect_prompt_injection"
        and trial.get("attack_success")
    ):
        details = trial.get("evaluation_details") or {}
        print(trial["test_title"], trial["repetition_number"], details.get("visible_markers"), details.get("retrieved_access_levels"))

print("secured emitted")
for trial in trials:
    if trial["configuration"] != "secured":
        continue
    details = trial.get("evaluation_details") or {}
    if details.get("model_emitted_markers"):
        print(
            trial["test_title"],
            trial["repetition_number"],
            details.get("model_emitted_markers"),
            details.get("visible_markers"),
            details.get("retrieved_access_levels"),
        )

print("permission failures and disclosures")
for trial in trials:
    if trial["configuration"] != "permission_only":
        continue
    if trial.get("actual_outcome") == "infrastructure_failure" or trial.get("information_disclosed"):
        details = trial.get("evaluation_details") or {}
        print(
            trial["actual_outcome"],
            trial["test_title"],
            trial["repetition_number"],
            details.get("retrieved_access_levels"),
            details.get("visible_markers"),
            (trial.get("error_message") or "")[:140],
        )
