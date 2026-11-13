"""Execute stored test cases and persist trial-level results."""

import logging
import threading
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.constants import SYNTHETIC_USERS
from app.database import get_session_factory
from app.evaluation.outcomes import TrialObservation, evaluate_trial
from app.exceptions import ConflictError, InfrastructureError
from app.models import Document, Experiment, Profile, TestCase, TestResult
from app.rag.pipeline import answer_question
from app.services.runtime import get_runtime_settings

logger = logging.getLogger("ragsec.experiments")
_thread_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_actor(db: Session, criteria: dict) -> Profile:
    email = criteria.get("actor_email")
    if not email:
        role = criteria.get("actor_role") or "employee"
        email = {
            "admin": SYNTHETIC_USERS["admin"],
            "employee": SYNTHETIC_USERS["employee"],
            "researcher": SYNTHETIC_USERS["researcher"],
        }.get(role)
    if not email:
        raise InfrastructureError("The test case does not name an actor account.")
    profile = db.scalar(select(Profile).where(Profile.email == email))
    if profile is None:
        raise InfrastructureError(
            "The synthetic actor account is not available. Run the seed script after creating Supabase users."
        )
    return profile


def _overlay(runtime: dict, parameters: dict) -> dict:
    merged = dict(runtime)
    for key in (
        "top_k",
        "similarity_threshold",
        "temperature",
        "llm_model",
        "embedding_model",
        "max_input_chars_secured",
        "max_input_chars_baseline",
        "corpus_titles",
    ):
        if parameters.get(key) is not None:
            merged[key] = parameters[key]
    return merged


def restrict_to_corpus(
    requested_ids: list[UUID] | None,
    corpus_ids: set[UUID] | None,
) -> list[UUID] | None:
    """Limit a trial to the snapshot corpus.

    `None` means the caller did not name a corpus, so the existing scope stands.
    An empty corpus stays empty and must not fall back to every ready document.
    """

    if corpus_ids is None:
        return requested_ids
    if requested_ids is None:
        return list(corpus_ids)
    return [item for item in requested_ids if item in corpus_ids]


def execute_case(db: Session, case: TestCase, configuration: str, runtime: dict, experiment_id: UUID) -> dict:
    criteria = dict(case.evaluation_criteria or {})
    try:
        actor = resolve_actor(db, criteria)
    except InfrastructureError as exc:
        observation = TrialObservation(
            configuration=configuration,
            category=case.category,
            criteria=criteria,
            infrastructure_error=exc.message,
        )
        evaluated = evaluate_trial(observation)
        evaluated["response_latency_ms"] = None
        return evaluated

    document_ids = None
    titles = criteria.get("requested_document_titles") or []
    if titles:
        documents = db.scalars(select(Document).where(Document.title.in_(list(titles)))).all()
        found = {document.title for document in documents}
        missing = [title for title in titles if title not in found]
        if missing:
            observation = TrialObservation(
                configuration=configuration,
                category=case.category,
                criteria=criteria,
                infrastructure_error="A requested test document is not in the corpus: " + ", ".join(missing),
            )
            evaluated = evaluate_trial(observation)
            evaluated["response_latency_ms"] = None
            return evaluated
        document_ids = [document.id for document in documents]

    corpus_titles = runtime.get("corpus_titles")
    if corpus_titles:
        titled = db.scalars(select(Document).where(Document.title.in_(list(corpus_titles)))).all()
        found = {document.title for document in titled}
        missing = [title for title in corpus_titles if title not in found]
        if missing:
            observation = TrialObservation(
                configuration=configuration,
                category=case.category,
                criteria=criteria,
                infrastructure_error="A document named in the experiment corpus is not available: " + ", ".join(missing),
            )
            evaluated = evaluate_trial(observation)
            evaluated["response_latency_ms"] = None
            return evaluated
        not_ready = [document.title for document in titled if document.processing_status != "ready"]
        if not_ready:
            observation = TrialObservation(
                configuration=configuration,
                category=case.category,
                criteria=criteria,
                infrastructure_error="A document named in the experiment corpus is not ready: " + ", ".join(not_ready),
            )
            evaluated = evaluate_trial(observation)
            evaluated["response_latency_ms"] = None
            return evaluated
        document_ids = restrict_to_corpus(document_ids, {document.id for document in titled})

    pipeline = answer_question(
        db,
        actor=actor,
        question=case.input,
        configuration=configuration,
        document_ids=document_ids,
        runtime=runtime,
        experiment_id=experiment_id,
        test_case_id=case.id,
        experiment_execution=True,
        target_access_levels=list(criteria.get("target_access_levels") or []),
    )
    observation = TrialObservation(
        configuration=configuration,
        category=case.category,
        criteria=criteria,
        answer=pipeline.answer,
        input_rejected=pipeline.input_rejected,
        rejection_reason=pipeline.rejection_reason,
        infrastructure_error=pipeline.infrastructure_error,
        retrieved_access_levels=pipeline.retrieved_access_levels,
        retrieved_document_ids=pipeline.retrieved_document_ids,
        output_filter_applied=pipeline.output_filter_applied,
        model_emitted_markers=pipeline.model_emitted_markers,
        visible_markers=pipeline.visible_markers,
        latency_ms=pipeline.latency_ms,
        targets_excluded=pipeline.targets_excluded,
        target_documents_missing=pipeline.target_documents_missing,
        security_decisions=pipeline.security_decisions,
    )
    evaluated = evaluate_trial(observation)
    evaluated["response_latency_ms"] = pipeline.latency_ms
    evaluated["evaluation_details"]["warnings"] = pipeline.warnings
    evaluated["evaluation_details"]["sources"] = [
        {key: value for key, value in source.items() if key != "excerpt"} for source in pipeline.sources
    ]
    return evaluated


def execute_experiment(db: Session, experiment_id: UUID) -> None:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        return
    cases = db.scalars(
        select(TestCase).where(TestCase.dataset_id == experiment.dataset_id).order_by(TestCase.created_at)
    ).all()
    experiment.status = "running"
    experiment.started_at = experiment.started_at or _now()
    experiment.progress_total = len(cases) * experiment.repetitions
    experiment.progress_completed = 0
    experiment.error_message = None
    db.commit()

    runtime = _overlay(get_runtime_settings(db), experiment.parameters or {})
    try:
        for repetition in range(1, experiment.repetitions + 1):
            for case in cases:
                existing = db.scalar(
                    select(TestResult).where(
                        TestResult.experiment_id == experiment.id,
                        TestResult.test_case_id == case.id,
                        TestResult.repetition_number == repetition,
                    )
                )
                if existing is None:
                    try:
                        evaluated = execute_case(db, case, experiment.configuration, runtime, experiment.id)
                    except Exception:
                        logger.exception("Trial failed")
                        db.rollback()
                        experiment = db.get(Experiment, experiment_id)
                        if experiment is None:
                            return
                        evaluated = evaluate_trial(
                            TrialObservation(
                                configuration=experiment.configuration,
                                category=case.category,
                                criteria=case.evaluation_criteria or {},
                                infrastructure_error="The trial failed because of an unexpected application error.",
                            )
                        )
                        evaluated["response_latency_ms"] = None
                    db.add(
                        TestResult(
                            experiment_id=experiment.id,
                            test_case_id=case.id,
                            repetition_number=repetition,
                            actual_outcome=evaluated["actual_outcome"],
                            attack_success=bool(evaluated["attack_success"]),
                            information_disclosed=bool(evaluated["information_disclosed"]),
                            legitimate_task_success=bool(evaluated["legitimate_task_success"]),
                            response_latency_ms=evaluated.get("response_latency_ms"),
                            evaluation_details=evaluated["evaluation_details"],
                            error_message=evaluated.get("error_message"),
                        )
                    )
                experiment.progress_completed += 1
                db.commit()
        experiment.status = "completed"
        experiment.completed_at = _now()
        experiment.error_message = None
        db.commit()
    except Exception as exc:
        logger.exception("Experiment failed")
        db.rollback()
        failed = db.get(Experiment, experiment_id)
        if failed is not None:
            failed.status = "failed"
            failed.error_message = "The experiment stopped because of an application error."
            failed.completed_at = _now()
            db.commit()
        del exc


def execute_experiments(experiment_ids: list[UUID]) -> None:
    session = get_session_factory()()
    try:
        for experiment_id in experiment_ids:
            execute_experiment(session, experiment_id)
    finally:
        session.close()


def ensure_idle(db: Session) -> None:
    db.execute(text("select pg_advisory_xact_lock(841234567)"))
    running = db.scalar(select(Experiment.id).where(Experiment.status == "running").limit(1))
    if running is not None:
        raise ConflictError("An experiment is already running. Wait for it to finish.")


def start_experiments(experiment_ids: list[UUID]) -> None:
    with _thread_lock:
        thread = threading.Thread(target=execute_experiments, args=(experiment_ids,), daemon=True)
        thread.start()
