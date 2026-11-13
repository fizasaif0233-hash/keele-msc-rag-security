from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serialize import iso
from app.auth.permissions import can_view_research
from app.constants import ABSOLUTE_MAX_INPUT_CHARS, TEST_CATEGORIES
from app.database import get_db
from app.deps import require_roles
from app.exceptions import ConflictError, InputRejected, NotFoundError, PermissionDenied
from app.models import Experiment, Profile, TestCase, TestDataset, TestResult
from app.security.logging import write_security_log

router = APIRouter(tags=["research"])


class DatasetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)


class CaseCreate(BaseModel):
    category: str
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)
    input: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=3, max_length=2000)
    evaluation_criteria: dict = Field(default_factory=dict)


class CaseUpdate(BaseModel):
    category: str | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    input: str | None = None
    expected_outcome: str | None = Field(default=None, max_length=2000)
    evaluation_criteria: dict | None = None


def _require_research(user: Profile) -> None:
    if not can_view_research(user.role):
        write_security_log(
            user_id=user.id,
            event_type="authorisation_failure",
            severity="medium",
            outcome="denied",
            metadata={"action": "research"},
        )
        raise PermissionDenied()


def _check_case(body_category: str, body_input: str, criteria: dict) -> None:
    if body_category not in TEST_CATEGORIES:
        raise InputRejected("Unknown test category.")
    if len(body_input) > ABSOLUTE_MAX_INPUT_CHARS:
        raise InputRejected("The test input exceeds the absolute length ceiling.")
    if not isinstance(criteria, dict):
        raise InputRejected("Evaluation criteria must be an object.")


def _case_payload(case: TestCase) -> dict:
    return {
        "id": str(case.id),
        "dataset_id": str(case.dataset_id),
        "category": case.category,
        "title": case.title,
        "description": case.description,
        "input": case.input,
        "expected_outcome": case.expected_outcome,
        "evaluation_criteria": case.evaluation_criteria or {},
        "created_at": iso(case.created_at),
    }


@router.get("/datasets")
def list_datasets(
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    _require_research(user)
    rows = db.scalars(select(TestDataset).order_by(TestDataset.created_at.desc())).all()
    payload = []
    for dataset in rows:
        count = db.scalar(select(func.count()).select_from(TestCase).where(TestCase.dataset_id == dataset.id))
        payload.append(
            {
                "id": str(dataset.id),
                "name": dataset.name,
                "description": dataset.description,
                "case_count": int(count or 0),
                "created_at": iso(dataset.created_at),
            }
        )
    return {"datasets": payload}


@router.post("/datasets")
def create_dataset(
    body: DatasetCreate,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.scalar(select(TestDataset).where(TestDataset.name == body.name.strip()))
    if existing is not None:
        raise ConflictError("A dataset with that name already exists.")
    dataset = TestDataset(name=body.name.strip(), description=body.description.strip(), created_by=user.id)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return {"id": str(dataset.id), "name": dataset.name, "description": dataset.description}


@router.get("/datasets/{dataset_id}/cases")
def list_cases(
    dataset_id: UUID,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    dataset = db.get(TestDataset, dataset_id)
    if dataset is None:
        raise NotFoundError()
    cases = db.scalars(
        select(TestCase).where(TestCase.dataset_id == dataset.id).order_by(TestCase.created_at)
    ).all()
    return {"dataset": {"id": str(dataset.id), "name": dataset.name}, "cases": [_case_payload(case) for case in cases]}


@router.post("/datasets/{dataset_id}/cases")
def create_case(
    dataset_id: UUID,
    body: CaseCreate,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    dataset = db.get(TestDataset, dataset_id)
    if dataset is None:
        raise NotFoundError()
    _check_case(body.category, body.input, body.evaluation_criteria)
    case = TestCase(
        dataset_id=dataset.id,
        category=body.category,
        title=body.title.strip(),
        description=body.description.strip(),
        input=body.input,
        expected_outcome=body.expected_outcome.strip(),
        evaluation_criteria=body.evaluation_criteria,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return _case_payload(case)


@router.put("/cases/{case_id}")
def update_case(
    case_id: UUID,
    body: CaseUpdate,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    case = db.get(TestCase, case_id)
    if case is None:
        raise NotFoundError()
    if body.category is not None:
        case.category = body.category
    if body.title is not None:
        case.title = body.title.strip()
    if body.description is not None:
        case.description = body.description.strip()
    if body.input is not None:
        case.input = body.input
    if body.expected_outcome is not None:
        case.expected_outcome = body.expected_outcome.strip()
    if body.evaluation_criteria is not None:
        case.evaluation_criteria = body.evaluation_criteria
    _check_case(case.category, case.input, case.evaluation_criteria or {})
    db.commit()
    return _case_payload(case)


@router.delete("/cases/{case_id}")
def delete_case(
    case_id: UUID,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    case = db.get(TestCase, case_id)
    if case is None:
        raise NotFoundError()
    used = db.scalar(select(func.count()).select_from(TestResult).where(TestResult.test_case_id == case.id))
    if used:
        raise ConflictError("This test case already has experiment results and cannot be deleted.")
    db.delete(case)
    db.commit()
    return {"deleted": True}


@router.delete("/datasets/{dataset_id}")
def delete_dataset(
    dataset_id: UUID,
    user: Profile = Depends(require_roles("admin", "researcher")),
    db: Session = Depends(get_db),
) -> dict:
    del user
    dataset = db.get(TestDataset, dataset_id)
    if dataset is None:
        raise NotFoundError()
    in_use = db.scalar(select(func.count()).select_from(Experiment).where(Experiment.dataset_id == dataset.id))
    if in_use:
        raise ConflictError("This dataset is referenced by an experiment and cannot be deleted.")
    db.delete(dataset)
    db.commit()
    return {"deleted": True}
