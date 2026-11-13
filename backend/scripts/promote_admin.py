"""Promote an existing account to administrator.

Register the account through the application first. This script does not create
a password and does not install a default administrator credential.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.database import get_session_factory
from app.models import Profile
from sqlalchemy import func, select


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote an existing user to admin.")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured.")
    session = get_session_factory()()
    try:
        profile = session.scalar(select(Profile).where(func.lower(Profile.email) == args.email.strip().lower()))
        if profile is None:
            raise SystemExit(
                "That account has no profile. Register it in the application, then run this command again."
            )
        profile.role = "admin"
        session.commit()
        print(f"Promoted {profile.email} to admin.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
