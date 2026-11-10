"""Explicit operator-only enrollment. Never run automatically on application startup."""
import argparse
from getpass import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import password_hash
from app.db import build_engine
from app.models import User
from app.models.staff import STAFF_ROLES, StaffAccount
from app.schemas.user import normalize_email


def main():
    parser = argparse.ArgumentParser(description="Provision an explicit staff identity with email and password")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=STAFF_ROLES, required=True,
        help="admin signs in at /admin/login; accountant signs in at /login")
    args = parser.parse_args()
    if not 1 <= len(args.name.strip()) <= 100:
        parser.error("Name must contain 1–100 characters")
    email = normalize_email(args.email)
    password = getpass("New staff password (at least 12 characters): ")
    if not 12 <= len(password) <= 128 or password != getpass("Confirm password: "):
        parser.error("Passwords must match and contain 12–128 characters")
    settings = get_settings()
    engine = build_engine(settings)
    try:
        with Session(engine) as db:
            if db.scalar(select(User).where(User.email == email)):
                parser.error("Identity already exists. Existing driver identities cannot be implicitly promoted")
            user = User(email=email, password_hash=password_hash.hash(password), display_name=args.name.strip())
            db.add(user)
            db.flush()
            db.add(StaffAccount(id=user.id, name=args.name.strip(), role=args.role, totp_secret=b""))
            db.commit()
        print("Staff account created. Sign in at " + ("/admin/login" if args.role == "admin" else "/login") + " with the staff email and password.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
