from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import identity_from_claims, profile_defaults_from_identity, verify_access_token
from app.database import get_db
from app.exceptions import AuthError, PermissionDenied
from app.models import Profile
from app.security.logging import write_security_log

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> Profile:
    token = None
    if credentials is not None:
        token = credentials.credentials
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    if not token:
        write_security_log(
            user_id=None,
            event_type="authentication_failure",
            severity="medium",
            outcome="denied",
            metadata={"reason": "missing_token"},
        )
        raise AuthError()

    try:
        claims = verify_access_token(token)
    except AuthError:
        write_security_log(
            user_id=None,
            event_type="authentication_failure",
            severity="medium",
            outcome="denied",
            metadata={"reason": "invalid_token"},
        )
        raise

    identity = identity_from_claims(claims)
    user_id = UUID(str(identity["id"]))
    profile = db.get(Profile, user_id)
    if profile is None:
        defaults = profile_defaults_from_identity(identity)
        profile = Profile(id=defaults["id"], email=defaults["email"], role=defaults["role"])
        db.add(profile)
        db.commit()
        db.refresh(profile)
    elif identity.get("email") and profile.email != identity["email"]:
        profile.email = str(identity["email"])
        db.commit()
    return profile


def require_roles(*roles: str):
    def dependency(user: Profile = Depends(get_current_user)) -> Profile:
        if user.role not in roles:
            write_security_log(
                user_id=user.id,
                event_type="authorisation_failure",
                severity="medium",
                outcome="denied",
                metadata={"required_roles": list(roles), "role": user.role},
            )
            raise PermissionDenied()
        return user

    return dependency
