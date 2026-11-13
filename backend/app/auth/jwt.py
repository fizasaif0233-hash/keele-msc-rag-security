"""Authentication helpers.

Role claims inside a Supabase token are ignored. The profile row is the only
source of role information.
"""

import threading
from typing import Any
from uuid import UUID

import jwt
from jwt import PyJWKClient

from app.config import settings
from app.exceptions import AuthError

_jwks_client: PyJWKClient | None = None
_jwks_lock = threading.Lock()


def identity_from_claims(claims: dict[str, Any]) -> dict[str, str | None]:
    """Return the authenticated identity. The role claim is intentionally omitted."""

    subject = claims.get("sub")
    if not subject:
        raise AuthError("The session token is missing a subject.")
    email = claims.get("email")
    return {"id": str(subject), "email": str(email) if email else None}


def profile_defaults_from_identity(identity: dict[str, str | None]) -> dict[str, Any]:
    """New profiles always start as employees, even if the token contains another role."""

    return {
        "id": UUID(str(identity["id"])),
        "email": identity.get("email") or "unknown@invalid.example",
        "role": "employee",
    }


def _jwks() -> PyJWKClient:
    global _jwks_client
    if not settings.supabase_url:
        raise AuthError("Supabase authentication is not configured.", code="auth_not_configured")
    with _jwks_lock:
        if _jwks_client is None:
            url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
            _jwks_client = PyJWKClient(url)
        return _jwks_client


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthError("The session token is invalid.") from exc

    algorithm = header.get("alg")
    try:
        if algorithm == "HS256":
            if not settings.supabase_jwt_secret:
                raise AuthError(
                    "The authentication secret is not configured.",
                    code="auth_not_configured",
                )
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        elif algorithm in {"RS256", "ES256"}:
            signing_key = _jwks().get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "ES256"],
                audience="authenticated",
            )
        else:
            raise AuthError("The session token uses an unsupported algorithm.")
    except AuthError:
        raise
    except jwt.PyJWTError as exc:
        raise AuthError("The session token is invalid or has expired.") from exc

    identity_from_claims(claims)
    return claims
