import csv
import io
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serialize import iso
from app.auth.permissions import (
    can_edit_settings,
    can_read_document,
    can_upload,
    can_view_logs,
    can_view_research,
)
from app.config import settings
from app.constants import EMBEDDING_DIMENSIONS
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.evaluation.runner import ensure_idle, start_experiments
from app.exceptions import ConflictError, InputRejected, NotFoundError, PermissionDenied
from app.models import (
    AppSetting,
    ChatSession,
    Document,
    DocumentPermission,
    Experiment,
    Profile,
    SecurityLog,
    TestCase,
    TestDataset,
)
from app.security.configurations import describe_configurations
from app.security.logging import write_security_log
from app.seed.catalog import synthetic_corpus_titles
from app.services.reporting import build_report, csv_safe, load_trials
from app.services.runtime import get_runtime_settings, validate_runtime_update

router = APIRouter(tags=["platform"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    configurations: list[str] = Field(min_length=1, max_length=2)
    dataset_id: UUID
    repetitions: int = Field(default=1, ge=1, le=20)
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=-1, le=1)
    temperature: float | None = Field(default=None, ge=0, le=1)


class SettingUpdate(BaseModel):
    values: dict[str, Any]


class RoleUpdate(BaseModel):
    role: str = Field(pattern="^(admin|employee|researcher)$")


def _experiment_payload(experiment: Experiment) -> dict:
    return {
        "id": str(experiment.id),
        "name": experiment.name,
        "configuration": experiment.configuration,
        "dataset_id": str(experiment.dataset_id),
        "repetitions": experiment.repetitions,
        "status": experiment.status,
        "parameters": experiment.parameters or {},
        "comparison_group": str(experiment.comparison_group) if experiment.comparison_group else None,
        "started_at": iso(experiment.started_at),
        "completed_at": iso(experiment.completed_at),
        "progress_completed": experiment.progress_completed,
        "progress_total": experiment.progress_total,
        "error_message": experiment.error_message,
        "created_at": iso(experiment.created_at),
    }


def _visible_document_count(db: Session, user: Profile) -> int:
    grants: dict = {}
    for row in db.scalars(select(DocumentPermission)).all():
        grants.setdefault(row.document_id, set()).add(row.user_id)
    count = 0
    for document in db.scalars(select(Document)).all():
        if can_read_document(
            role=user.role,
            user_id=user.id,
            document_owner_id=document.owner_id,
            access_level=document.access_level,
            explicit_user_ids=grants.get(document.id, set()),
        ):
            count += 1
    return count


def _log_rows(db: Session, user: Profile, limit: int) -> list[dict]:
    query = select(SecurityLog, Profile).join(Profile, Profile.id == SecurityLog.user_id, isouter=True)
    if not can_view_logs(user.role):
        query = query.where(SecurityLog.user_id == user.id)
    query = query.order_by(SecurityLog.created_at.desc()).limit(limit)
    payload = []
    for entry, profile in db.execute(query).all():
        payload.append(
            {
                "id": str(entry.id),
                "user_id": str(entry.user_id) if entry.user_id else None,
                "user_email": profile.email if profile else None,
                "event_type": entry.event_type,
                "severity": entry.severity,
                "outcome": entry.outcome,
                "configuration": entry.configuration,
                "experiment_id": str(entry.experiment_id) if entry.experiment_id else None,
                "test_case_id": str(entry.test_case_id) if entry.test_case_id else None,
                "metadata": entry.log_metadata or {},
                "created_at": iso(entry.created_at),
            }
        )
    return payload


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "database_configured": bool(settings.database_url),
        "llm_configured": bool(settings.llm_api_key),
        "supabase_configured": bool(settings.supabase_url),
    }


@router.get("/me")
def me(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    runtime = get_runtime_settings(db)
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "created_at": iso(user.created_at),
        "can_upload": can_upload(user.role, bool(runtime.get("allow_employee_upload"))),
    }


@router.get("/configurations")
def configurations(user: Profile = Depends(get_current_user)) -> dict:
    del user
    return describe_configurations()


@router.get("/dashboard")
def dashboard(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    research = can_view_research(user.role)
    report = build_report(db) if research else None
    latest = None
    if research:
        experiment = db.scalar(select(Experiment).order_by(Experiment.created_at.desc()))
        latest = _experiment_payload(experiment) if experiment else None
    chat_count = db.scalar(select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user.id))
    return {
        "role": user.role,
        "documents": _visible_document_count(db, user),
        "test_cases": int(db.scalar(select(func.count()).select_from(TestCase)) or 0) if research else None,
        "experiments": int(db.scalar(select(func.count()).select_from(Experiment)) or 0) if research else None,
        "chat_sessions": int(chat_count or 0),
        "metrics": None
        if not research or report is None or not report["has_results"]
        else {
            "baseline": report["by_configuration"]["baseline"],
            "secured": report["by_configuration"]["secured"],
            "reductions": report["reductions"],
        },
        "has_results": bool(report and report["has_results"]),
        "recent_events": _log_rows(db, user, 8),
        "latest_experiment": latest,
    }


@router.get("/experiments")
def list_experiments(
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    rows = db.scalars(select(Experiment).order_by(Experiment.created_at.desc())).all()
    return {"experiments": [_experiment_payload(row) for row in rows]}


@router.post("/experiments")
def create_experiment(
    body: ExperimentCreate,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    configurations = []
    for name in body.configurations:
        if name not in {"baseline", "secured"}:
            raise InputRejected("Configuration must be baseline or secured.")
        if name not in configurations:
            configurations.append(name)
    dataset = db.get(TestDataset, body.dataset_id)
    if dataset is None:
        raise NotFoundError("The selected dataset was not found.")
    case_count = db.scalar(select(func.count()).select_from(TestCase).where(TestCase.dataset_id == dataset.id))
    if not case_count:
        raise InputRejected("The selected dataset has no test cases.")
    ensure_idle(db)
    runtime = get_runtime_settings(db)
    parameters = {
        "llm_model": runtime.get("llm_model"),
        "embedding_model": runtime.get("embedding_model"),
        "top_k": body.top_k if body.top_k is not None else runtime.get("top_k"),
        "similarity_threshold": (
            body.similarity_threshold
            if body.similarity_threshold is not None
            else runtime.get("similarity_threshold")
        ),
        "temperature": body.temperature if body.temperature is not None else runtime.get("temperature"),
        "chunk_size": runtime.get("chunk_size"),
        "chunk_overlap": runtime.get("chunk_overlap"),
        "max_input_chars_secured": runtime.get("max_input_chars_secured"),
        "max_input_chars_baseline": runtime.get("max_input_chars_baseline"),
        "corpus_titles": synthetic_corpus_titles(dataset.name),
    }
    group = uuid4()
    created = []
    for configuration in configurations:
        experiment = Experiment(
            name=body.name.strip(),
            configuration=configuration,
            dataset_id=dataset.id,
            repetitions=body.repetitions,
            status="running",
            parameters=parameters,
            comparison_group=group,
            created_by=user.id,
            started_at=_now(),
            progress_completed=0,
            progress_total=int(case_count) * body.repetitions,
        )
        db.add(experiment)
        created.append(experiment)
    db.commit()
    for experiment in created:
        db.refresh(experiment)
    start_experiments([experiment.id for experiment in created])
    return {"experiments": [_experiment_payload(experiment) for experiment in created]}


@router.post("/experiments/{experiment_id}/start")
def start_existing(
    experiment_id: UUID,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise NotFoundError()
    if experiment.status == "running":
        raise ConflictError("This experiment is already running.")
    if experiment.status == "completed":
        raise ConflictError("Completed experiments are kept as evidence. Create a new run to repeat them.")
    ensure_idle(db)
    experiment.status = "running"
    experiment.started_at = _now()
    experiment.completed_at = None
    experiment.error_message = None
    db.commit()
    start_experiments([experiment.id])
    db.refresh(experiment)
    return _experiment_payload(experiment)


@router.get("/experiments/{experiment_id}")
def get_experiment(
    experiment_id: UUID,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise NotFoundError()
    return _experiment_payload(experiment)


@router.get("/experiments/{experiment_id}/results")
def experiment_results(
    experiment_id: UUID,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise NotFoundError()
    trials = load_trials(db, [experiment.id])
    report = build_report(db, [experiment.id])
    return {"experiment": _experiment_payload(experiment), "report": _json_ready(report), "results": _json_trials(trials)}


@router.get("/analytics")
def analytics(
    experiment_ids: list[UUID] | None = Query(default=None),
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    report = build_report(db, experiment_ids)
    experiments = db.scalars(select(Experiment).order_by(Experiment.created_at.desc())).all()
    if experiment_ids:
        selected = {str(item) for item in experiment_ids}
        experiments = [item for item in experiments if str(item.id) in selected]
    return {
        "report": _json_ready(report),
        "experiments": [_experiment_payload(item) for item in experiments],
    }


@router.get("/analytics/export")
def export_results(
    export_format: str = Query(alias="format", pattern="^(csv|json)$"),
    experiment_ids: list[UUID] | None = Query(default=None),
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> Response:
    del user
    trials = _json_trials(load_trials(db, experiment_ids))
    report = _json_ready(build_report(db, experiment_ids))
    if export_format == "json":
        import json

        body = json.dumps({"report": report, "results": trials}, indent=2)
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=experiment-results.json"},
        )
    buffer = io.StringIO()
    fieldnames = [
        "test_id",
        "test_category",
        "test_description",
        "configuration",
        "expected_outcome",
        "actual_outcome",
        "attack_success",
        "information_disclosed",
        "legitimate_task_success",
        "response_latency_ms",
        "error_message",
        "timestamp",
        "repetition_number",
        "experiment_id",
        "manual_review",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for trial in trials:
        writer.writerow(
            {
                "test_id": trial["test_case_id"],
                "test_category": csv_safe(trial["category"]),
                "test_description": csv_safe(trial["test_description"]),
                "configuration": csv_safe(trial["configuration"]),
                "expected_outcome": csv_safe(trial["expected_outcome"]),
                "actual_outcome": csv_safe(trial["actual_outcome"]),
                "attack_success": trial["attack_success"],
                "information_disclosed": trial["information_disclosed"],
                "legitimate_task_success": trial["legitimate_task_success"],
                "response_latency_ms": trial["response_latency_ms"],
                "error_message": csv_safe(trial["error_message"]),
                "timestamp": trial["created_at"],
                "repetition_number": trial["repetition_number"],
                "experiment_id": trial["experiment_id"],
                "manual_review": (trial.get("evaluation_details") or {}).get("manual_review"),
            }
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=experiment-results.csv"},
    )


@router.get("/security-logs")
def security_logs(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = None,
    configuration: str | None = None,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    if not can_view_logs(user.role):
        raise PermissionDenied()
    query = select(SecurityLog, Profile).join(Profile, Profile.id == SecurityLog.user_id, isouter=True)
    if event_type:
        query = query.where(SecurityLog.event_type == event_type)
    if configuration:
        query = query.where(SecurityLog.configuration == configuration)
    total = db.scalar(select(func.count()).select_from(SecurityLog))
    rows = db.execute(query.order_by(SecurityLog.created_at.desc()).offset(offset).limit(limit)).all()
    return {
        "total": int(total or 0),
        "logs": [
            {
                "id": str(entry.id),
                "user_id": str(entry.user_id) if entry.user_id else None,
                "user_email": profile.email if profile else None,
                "event_type": entry.event_type,
                "severity": entry.severity,
                "outcome": entry.outcome,
                "configuration": entry.configuration,
                "experiment_id": str(entry.experiment_id) if entry.experiment_id else None,
                "test_case_id": str(entry.test_case_id) if entry.test_case_id else None,
                "metadata": entry.log_metadata or {},
                "created_at": iso(entry.created_at),
            }
            for entry, profile in rows
        ],
    }


@router.get("/settings")
def get_settings(
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    runtime = get_runtime_settings(db)
    return {
        "can_edit": can_edit_settings(user.role),
        "settings": {key: value for key, value in runtime.items() if key != "unused"},
        "environment": {
            "database_configured": bool(settings.database_url),
            "supabase_url_configured": bool(settings.supabase_url),
            "supabase_jwt_secret_configured": bool(settings.supabase_jwt_secret),
            "supabase_service_role_configured": bool(settings.supabase_service_role_key),
            "llm_api_key_configured": bool(settings.llm_api_key),
            "llm_base_url": settings.llm_base_url,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
        },
    }


@router.put("/settings")
def update_settings(
    body: SettingUpdate,
    user: Profile = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not can_edit_settings(user.role):
        raise PermissionDenied()
    updated = {}
    for key, value in body.values.items():
        try:
            updated[key] = validate_runtime_update(key, value)
        except ValueError as exc:
            raise InputRejected(str(exc)) from exc
    current = get_runtime_settings(db)
    current.update(updated)
    if int(current["chunk_overlap"]) >= int(current["chunk_size"]):
        raise InputRejected("Chunk overlap must be smaller than chunk size.")
    if int(current["max_input_chars_secured"]) > int(current["max_input_chars_baseline"]):
        raise InputRejected("The secured input limit cannot be higher than the baseline limit.")
    for key, value in updated.items():
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value={"value": value}, updated_at=_now()))
        else:
            row.value = {"value": value}
            row.updated_at = _now()
    db.commit()
    return get_settings(user, db)


@router.get("/admin/users")
def list_users(
    user: Profile = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    rows = db.scalars(select(Profile).order_by(Profile.created_at)).all()
    return {
        "users": [
            {"id": str(row.id), "email": row.email, "role": row.role, "created_at": iso(row.created_at)}
            for row in rows
        ]
    }


@router.patch("/admin/users/{user_id}/role")
def update_role(
    user_id: UUID,
    body: RoleUpdate,
    user: Profile = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    target = db.get(Profile, user_id)
    if target is None:
        raise NotFoundError()
    if target.role == "admin" and body.role != "admin":
        admins = db.scalar(select(func.count()).select_from(Profile).where(Profile.role == "admin"))
        if int(admins or 0) <= 1:
            raise ConflictError("The last administrator cannot be demoted.")
    target.role = body.role
    db.commit()
    write_security_log(
        user_id=user.id,
        event_type="role_change",
        severity="high",
        outcome="updated",
        metadata={"target_user_id": str(target.id), "role": body.role},
    )
    return {"id": str(target.id), "email": target.email, "role": target.role}


def _json_trials(trials: list[dict]) -> list[dict]:
    converted = []
    for trial in trials:
        item = dict(trial)
        created = item.get("created_at")
        if isinstance(created, datetime):
            item["created_at"] = created.isoformat()
        converted.append(item)
    return converted


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
