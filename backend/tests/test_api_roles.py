"""Role checks against the HTTP API, using the synthetic accounts."""

import httpx
import pytest
from app.config import settings
from app.constants import SYNTHETIC_USERS
from app.main import app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not (settings.database_url and settings.supabase_url and settings.supabase_service_role_key and settings.seed_user_password),
    reason="Live sign-in is not configured.",
)

HIDDEN = {
    "HR confidential policy",
    "Finance internal report",
    "Administrator security policy",
    "Employee personal note",
}


def _token(email: str) -> str:
    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        headers={
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        },
        json={"email": email, "password": settings.seed_user_password},
        timeout=30,
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def tokens() -> dict[str, str]:
    return {role: _token(email) for role, email in SYNTHETIC_USERS.items()}


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_role_matrix(client: TestClient, tokens: dict[str, str]):
    employee = _headers(tokens["employee"])
    researcher = _headers(tokens["researcher"])
    admin = _headers(tokens["admin"])

    assert client.get("/api/v1/experiments", headers=employee).status_code == 403
    assert client.get("/api/v1/analytics/export", params={"format": "json"}, headers=employee).status_code == 403
    assert client.put("/api/v1/settings", json={"values": {}}, headers=employee).status_code == 403
    assert client.put("/api/v1/settings", json={"values": {}}, headers=researcher).status_code == 403
    assert client.get("/api/v1/admin/users", headers=employee).status_code == 403

    assert client.get("/api/v1/experiments", headers=admin).status_code == 200
    assert client.get("/api/v1/experiments", headers=researcher).status_code == 200
    assert client.get("/api/v1/analytics/export", params={"format": "json"}, headers=researcher).status_code == 200
    assert client.get("/api/v1/admin/users", headers=admin).status_code == 200

    documents = client.get("/api/v1/documents", headers=employee)
    assert documents.status_code == 200
    titles = {item["title"] for item in documents.json()["documents"]}
    assert HIDDEN.isdisjoint(titles)
    assert "Public FAQ" in titles


def test_grant_and_label_change_apply_on_the_next_request(client: TestClient, tokens: dict[str, str]):
    admin = _headers(tokens["admin"])
    employee = _headers(tokens["employee"])
    listed = client.get("/api/v1/documents", headers=admin)
    assert listed.status_code == 200
    finance = next(item for item in listed.json()["documents"] if item["title"] == "Finance internal report")
    document_id = finance["id"]
    employee_email = SYNTHETIC_USERS["employee"]
    try:
        granted = client.post(
            f"/api/v1/documents/{document_id}/permissions",
            headers=admin,
            json={"email": employee_email, "permission": "read"},
        )
        assert granted.status_code == 200
        visible = client.get("/api/v1/documents", headers=employee)
        assert "Finance internal report" in {item["title"] for item in visible.json()["documents"]}
        permissions = client.get(f"/api/v1/documents/{document_id}/permissions", headers=admin)
        assert permissions.status_code == 200
        match = next(row for row in permissions.json()["permissions"] if row["email"] == employee_email)
        removed = client.delete(
            f"/api/v1/documents/{document_id}/permissions/{match['id']}",
            headers=admin,
        )
        assert removed.status_code == 200
        hidden = client.get("/api/v1/documents", headers=employee)
        assert "Finance internal report" not in {item["title"] for item in hidden.json()["documents"]}

        opened = client.put(
            f"/api/v1/documents/{document_id}/access",
            headers=admin,
            json={"access_level": "public"},
        )
        assert opened.status_code == 200
        public_view = client.get("/api/v1/documents", headers=employee)
        assert "Finance internal report" in {item["title"] for item in public_view.json()["documents"]}
    finally:
        client.put(
            f"/api/v1/documents/{document_id}/access",
            headers=admin,
            json={"access_level": "confidential"},
        )
        permissions = client.get(f"/api/v1/documents/{document_id}/permissions", headers=admin)
        if permissions.status_code == 200:
            for row in permissions.json()["permissions"]:
                if row["email"] == employee_email:
                    client.delete(
                        f"/api/v1/documents/{document_id}/permissions/{row['id']}",
                        headers=admin,
                    )
