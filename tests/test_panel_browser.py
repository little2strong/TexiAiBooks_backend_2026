"""Opt-in live browser checks against an owned, disposable PostgreSQL server.

Run: set RUN_PANEL_BROWSER=1 and run python -m pytest tests/test_panel_browser.py -q
No development database, application provider or saved credential is used.
"""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
from urllib.request import urlopen

from cryptography.fernet import Fernet
from pydantic import SecretStr
import pytest
from sqlalchemy.orm import Session

from app.core.security import password_hash
from app.models import User
from app.models.books import Business, PrivateFile, Profile, Receipt, SupportRecord, Transaction
from app.models.staff import AccountantHandoff, DriverAssignment, StaffAccount, StaffTeam
from app.services.books import catalog_id
from app.services.vault import encrypt


@pytest.mark.skipif(os.environ.get("RUN_PANEL_BROWSER") != "1", reason="Set RUN_PANEL_BROWSER=1 for live browser checks")
def test_live_panel_browser(postgres_engine, settings):
    root = Path(__file__).resolve().parents[1]
    npm = "npm.cmd" if os.name == "nt" else "npm"
    build_args = [npm, "run", "build"]
    if os.environ.get("PANEL_EVIDENCE_MODE") == "before":
        # The source-only snapshot predates this debugging change. Keep the
        # active worktree untouched while reproducing the original production UI.
        import zipfile
        baseline = root / "accountant-panel/.ui-baseline"
        with zipfile.ZipFile(root / "artifacts/ui-debug/before-source.zip") as archive:
            for name in archive.namelist():
                if name.startswith("accountant-panel/"):
                    target = baseline / Path(name).relative_to("accountant-panel")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
        build_args = [npm, "exec", "--", "vite", "build", ".ui-baseline", "--config", "vite.config.ts", "--outDir", "../dist", "--emptyOutDir"]
    build = subprocess.run(build_args, cwd=root / "accountant-panel", capture_output=True, text=True, timeout=120)
    assert build.returncode == 0, build.stdout + build.stderr
    settings.identifier_encryption_keys = [SecretStr(Fernet.generate_key().decode())]
    password = secrets.token_urlsafe(24)
    with Session(postgres_engine) as db:
        team = StaffTeam(name="Synthetic browser team")
        driver = User(email="driver@browser.example", display_name="Browser Driver", password_hash=password_hash.hash(secrets.token_urlsafe(32)))
        db.add_all([team, driver]); db.flush()
        owner = driver.id
        db.add(Profile(owner_id=owner, kind="me", data={"first_name": "Browser", "last_name": "Driver", "preferences": {"locale": "en", "timezone": "Europe/London"}}))
        db.add(Profile(owner_id=owner, kind="tax", scope="2026-27", data={"region": "england_wales_ni", "has_paye_job": False, "employments": [], "utr_masked": "******7890", "ni_masked": "*****456C"}, identifiers=encrypt(settings, {"utr": "1234567890", "ni_number": "AB123456C"})))
        for name, role in [("admin-flow", "admin"), ("accountant-receipt", "accountant"), ("support-flow", "support"), ("admin-accessibility", "admin")]:
            user = User(email=f"{name}@browser.example", password_hash=password_hash.hash(password), display_name=name)
            db.add(user); db.flush()
            db.add(StaffAccount(id=user.id, name=name, role=role, team_id=team.id))
            db.flush()
            if role == "accountant": db.add(DriverAssignment(driver_id=owner, accountant_id=user.id))
        business = Business(owner_id=owner, kind="self_employment", name="Synthetic browser business")
        request = SupportRecord(owner_id=owner, kind="accountant_request", data={"kind": "filing_question", "tax_year": "2026-27", "status": "requested", "consent_version": "synthetic-only"})
        db.add_all([business, request]); db.flush()
        db.add(AccountantHandoff(id=request.id, driver_id=owner, tax_year="2026-27"))
        db.add(Transaction(owner_id=owner, business_id=business.id, kind="income", amount_pence=1000000, occurred_on="2026-10-20", source_id=catalog_id("source", "uber"), review_status="confirmed", claim_status="claimable", business_use_percent=100, description="Synthetic platform earnings"))
        file = PrivateFile(owner_id=owner, sha256="e" * 64, mime_type="image/png", content=b"quarantined synthetic evidence", size_bytes=30, scan_status="pending")
        db.add(file); db.flush()
        db.add(Receipt(owner_id=owner, business_id=business.id, file_id=file.id, reviewed={"merchant": "Browser receipt", "amount_pence": 10000, "occurred_on": "2026-10-20", "category_id": str(catalog_id("category", "phone_data")), "business_use_percent": "100"}))
        db.commit()
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0)); port = candidate.getsockname()[1]
    url = postgres_engine.url
    env = dict(os.environ, POSTGRES_HOST=url.host, POSTGRES_PORT=str(url.port), POSTGRES_DB=url.database,
        POSTGRES_USER=url.username, POSTGRES_PASSWORD=url.password, JWT_SECRET_KEY=settings.jwt_secret_key.get_secret_value(),
        IDENTIFIER_ENCRYPTION_KEYS=json.dumps([key.get_secret_value() for key in settings.identifier_encryption_keys]),
        PANEL_API_URL=f"http://127.0.0.1:{port}", PANEL_TEST_PASSWORD=password, PANEL_TEST_DRIVER_ID=str(owner))
    server = subprocess.Popen([str(root / ".venv/Scripts/python.exe"), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
        cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response: assert response.status == 200
                break
            except OSError:
                if time.monotonic() > deadline: pytest.fail("Owned browser API did not start")
                time.sleep(.2)
        browser_args = [npm, "run", "test:e2e"]
        if env.get("PANEL_EVIDENCE_MODE"):
            browser_args += ["--", "e2e/evidence.spec.ts"]
        elif env.get("PANEL_DIAGNOSTICS"):
            browser_args += ["--", "e2e/diagnostics.spec.ts"]
        result = subprocess.run(browser_args, cwd=root / "accountant-panel", env=env, capture_output=True, text=True, timeout=300)
        evidence = root / "artifacts/ui-debug/validation"
        evidence.mkdir(parents=True, exist_ok=True)
        name = "react-diagnostics" if env.get("PANEL_DIAGNOSTICS") else "evidence-" + env["PANEL_EVIDENCE_MODE"] if env.get("PANEL_EVIDENCE_MODE") else "browser-suite"
        import re
        log = (result.stdout + result.stderr).replace(password, "[redacted]")
        log = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[redacted JWT]", log)
        (evidence / f"{name}.txt").write_text(log, encoding="utf-8")
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        server.terminate()
        server.wait(timeout=15)
