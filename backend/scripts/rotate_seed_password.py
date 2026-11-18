"""Replace the synthetic account password in Supabase and backend/.env.

The new password is not printed.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.constants import SYNTHETIC_USERS


def headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def find_user(client: httpx.Client, email: str) -> str:
    base = settings.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    for page in range(1, 6):
        response = client.get(base, headers=headers(), params={"page": page, "per_page": 200})
        response.raise_for_status()
        users = response.json().get("users") or []
        for user in users:
            if (user.get("email") or "").lower() == email.lower():
                return user["id"]
        if len(users) < 200:
            break
    raise SystemExit(f"Account was not found: {email}")


def main() -> None:
    password = secrets.token_urlsafe(18)
    if len(password) < 12:
        raise SystemExit("Generated password was too short.")
    base = settings.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    updated = 0
    with httpx.Client(timeout=30) as client:
        for email in SYNTHETIC_USERS.values():
            user_id = find_user(client, email)
            response = client.put(f"{base}/{user_id}", headers=headers(), json={"password": password})
            if response.status_code >= 400:
                raise SystemExit(f"Password update failed for {email} with status {response.status_code}.")
            updated += 1
    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith("SEED_USER_PASSWORD="):
            lines[index] = f"SEED_USER_PASSWORD={password}"
            replaced = True
            break
    if not replaced:
        raise SystemExit("SEED_USER_PASSWORD was not found in backend/.env.")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"rotated {updated} accounts")


if __name__ == "__main__":
    main()
