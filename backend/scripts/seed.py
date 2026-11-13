"""Create the synthetic corpus and official test cases.

The script can be run more than once. Official documents are matched by title and
official test cases are matched by seed_key. Custom test cases are left in place.
Synthetic account passwords are read from SEED_USER_PASSWORD and are never hardcoded.
"""

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.constants import SYNTHETIC_USERS
from app.database import get_session_factory
from app.models import Document, Profile, TestCase, TestDataset
from app.rag.documents import file_sha256, process_document_text, store_upload
from app.seed.catalog import DATASET_DESCRIPTION, DATASET_NAME, DOCUMENTS, SEED_CASES
from app.services.runtime import get_runtime_settings
from sqlalchemy import select

FILES = ROOT / "app" / "seed" / "files"
ROLE_BY_KEY = {
    "admin": "admin",
    "employee": "employee",
    "employee_two": "employee",
    "researcher": "researcher",
}


def _fail(message: str) -> None:
    raise SystemExit(message)


def _headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _find_user(email: str) -> str | None:
    base = settings.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    with httpx.Client(timeout=30) as client:
        for page in range(1, 6):
            response = client.get(base, headers=_headers(), params={"page": page, "per_page": 200})
            if response.status_code >= 400:
                _fail(f"Supabase user lookup failed with status {response.status_code}.")
            users = response.json().get("users") or []
            for user in users:
                if (user.get("email") or "").lower() == email.lower():
                    return user["id"]
            if len(users) < 200:
                break
    return None


def _create_user(email: str, password: str) -> str:
    existing = _find_user(email)
    if existing:
        return existing
    url = settings.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    with httpx.Client(timeout=30) as client:
        response = client.post(
            url,
            headers=_headers(),
            json={"email": email, "password": password, "email_confirm": True},
        )
    if response.status_code >= 400:
        existing = _find_user(email)
        if existing:
            return existing
        _fail(f"Could not create {email}. Supabase returned status {response.status_code}.")
    return response.json()["id"]


def ensure_profiles(db) -> dict[str, Profile]:
    password = settings.seed_user_password.strip()
    can_create = bool(settings.supabase_url and settings.supabase_service_role_key and password)
    if password and len(password) < 12:
        _fail("SEED_USER_PASSWORD must contain at least 12 characters.")
    if password.lower() in {"password", "password123", "admin123", "changeme"}:
        _fail("SEED_USER_PASSWORD is too predictable. Choose a different password.")

    profiles: dict[str, Profile] = {}
    for key, email in SYNTHETIC_USERS.items():
        profile = db.scalar(select(Profile).where(Profile.email == email))
        if profile is None and can_create:
            user_id = _create_user(email, password)
            profile = db.get(Profile, user_id)
            if profile is None:
                profile = Profile(id=user_id, email=email, role=ROLE_BY_KEY[key])
                db.add(profile)
                db.flush()
        if profile is None:
            _fail(
                "Synthetic profiles are missing. Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, "
                "and SEED_USER_PASSWORD, apply the SQL migration, then run this script again. "
                f"Missing account: {email}"
            )
        profile.role = ROLE_BY_KEY[key]
        profile.email = email
        profiles[key] = profile
    db.flush()
    return profiles


def seed_documents(db, profiles: dict[str, Profile], refresh: bool) -> None:
    runtime = get_runtime_settings(db)
    for spec in DOCUMENTS:
        content = (FILES / spec["filename"]).read_bytes()
        digest = file_sha256(content)
        owner = profiles[spec["owner"]]
        document = db.scalar(select(Document).where(Document.title == spec["title"]))
        if document is None:
            document = Document(
                owner_id=owner.id,
                title=spec["title"],
                file_path="",
                document_type="txt",
                access_level=spec["access_level"],
                processing_status="processing",
                content_hash=digest,
                protected_markers=[],
            )
            db.add(document)
            db.flush()
            document.file_path = store_upload(document.id, ".txt", content)
            process_document_text(db, document, content.decode("utf-8"), runtime)
            print(f"Created {spec['title']} ({document.processing_status})")
            continue

        document.owner_id = owner.id
        document.access_level = spec["access_level"]
        changed = document.content_hash != digest or refresh or document.processing_status != "ready"
        document.content_hash = digest
        if changed:
            document.file_path = store_upload(document.id, ".txt", content)
            process_document_text(db, document, content.decode("utf-8"), runtime)
            print(f"Updated {spec['title']} ({document.processing_status})")
        else:
            print(f"Unchanged {spec['title']}")
    db.flush()


def seed_cases(db, owner: Profile) -> None:
    dataset = db.scalar(select(TestDataset).where(TestDataset.name == DATASET_NAME))
    if dataset is None:
        dataset = TestDataset(name=DATASET_NAME, description=DATASET_DESCRIPTION, created_by=owner.id)
        db.add(dataset)
        db.flush()
    else:
        dataset.description = DATASET_DESCRIPTION

    existing = db.scalars(select(TestCase).where(TestCase.dataset_id == dataset.id)).all()
    by_key = {
        (case.evaluation_criteria or {}).get("seed_key"): case
        for case in existing
        if (case.evaluation_criteria or {}).get("seed_key")
    }
    for spec in SEED_CASES:
        case = by_key.get(spec["seed_key"])
        if case is None:
            db.add(
                TestCase(
                    dataset_id=dataset.id,
                    category=spec["category"],
                    title=spec["title"],
                    description=spec["description"],
                    input=spec["input"],
                    expected_outcome=spec["expected_outcome"],
                    evaluation_criteria=spec["evaluation_criteria"],
                )
            )
        else:
            case.category = spec["category"]
            case.title = spec["title"]
            case.description = spec["description"]
            case.input = spec["input"]
            case.expected_outcome = spec["expected_outcome"]
            case.evaluation_criteria = spec["evaluation_criteria"]
    db.flush()
    print(f"Dataset '{DATASET_NAME}' has {len(SEED_CASES)} official test cases.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the synthetic research corpus.")
    parser.add_argument("--refresh", action="store_true", help="Re-embed documents even when the text is unchanged.")
    args = parser.parse_args()
    if not settings.database_url:
        _fail("DATABASE_URL is not configured.")
    session = get_session_factory()()
    try:
        profiles = ensure_profiles(session)
        seed_documents(session, profiles, args.refresh)
        seed_cases(session, profiles["researcher"])
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print("Seed completed.")


if __name__ == "__main__":
    main()
