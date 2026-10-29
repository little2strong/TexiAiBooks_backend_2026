"""Explicit operator-only enrollment. Never run automatically on application startup."""
import argparse
import base64
from getpass import getpass
from pathlib import Path
import secrets
import sys
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import password_hash
from app.db import build_engine
from app.models import User
from app.models.staff import StaffAccount, StaffTeam
from app.schemas.user import normalize_email
from app.services.vault import encrypt


def main():
    parser = argparse.ArgumentParser(description="Provision an explicit staff identity and authenticator enrollment")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["accountant", "senior_accountant", "admin", "support"], required=True)
    parser.add_argument("--team", help="Existing or new team name; required for accountants")
    args = parser.parse_args()
    if args.role in {"accountant", "senior_accountant"} and not args.team:
        parser.error("--team is required for accountants")
    if not 1 <= len(args.name.strip()) <= 100 or (args.team and not 1 <= len(args.team.strip()) <= 100):
        parser.error("Name and team must contain 1–100 characters")
    email = normalize_email(args.email)
    password = getpass("New staff password (at least 12 characters): ")
    if not 12 <= len(password) <= 128 or password != getpass("Confirm password: "):
        parser.error("Passwords must match and contain 12–128 characters")
    settings = get_settings()
    seed = base64.b32encode(secrets.token_bytes(20)).decode()
    encrypted = encrypt(settings, seed)
    engine = build_engine(settings)
    try:
        with Session(engine) as db:
            if db.scalar(select(User).where(User.email == email)):
                parser.error("Identity already exists. Existing driver identities cannot be implicitly promoted")
            team = db.scalar(select(StaffTeam).where(StaffTeam.name == args.team.strip())) if args.team else None
            if args.team and not team:
                team = StaffTeam(name=args.team.strip())
                db.add(team)
                db.flush()
            user = User(email=email, password_hash=password_hash.hash(password), display_name=args.name.strip())
            db.add(user)
            db.flush()
            db.add(StaffAccount(id=user.id, name=args.name.strip(), role=args.role,
                team_id=team.id if team else None, totp_secret=encrypted))
            db.commit()
        print("Staff account created. Enrol the authenticator privately; this seed is shown once.")
        print(f"otpauth://totp/{quote('TaxiAiBooks:' + email)}?secret={seed}&issuer=TaxiAiBooks&digits=6&period=30")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
