# Backend runbook

Python 3.12, PostgreSQL 16, pinned requirements, FastAPI/SQLAlchemy 2/Pydantic 2/Alembic. Work in the existing repository. No production deployment or development database migration was performed by this implementation.

## Environment

`python scripts/setup_env.py` creates a new `.env` with random development credentials and local encryption/hash keys, without printing values. It preserves an existing `.env` in full. For an existing file, provision the new keys through your secret manager or local secure configuration; do not overwrite database/JWT credentials. `.env` is ignored by Git and excluded from Docker build context.

| Variable | Purpose |
| --- | --- |
| POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD | Database identity; password required and validated |
| POSTGRES_HOST, POSTGRES_PORT | Local defaults 127.0.0.1:5433; Compose app/worker override to db:5432 |
| JWT_SECRET_KEY, JWT_ISSUER, JWT_AUDIENCE | Signing and claim validation; random signing secret at least 32 characters |
| ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS | Access lifetime and absolute device refresh lifetime |
| RESET_TOKEN_EXPIRE_MINUTES | Password recovery expiry |
| GOOGLE_CLIENT_IDS, APPLE_CLIENT_IDS | JSON arrays of approved native/OIDC audiences; empty disables provider sign-in |
| SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM, PASSWORD_RESET_URL | TLS password recovery delivery; HTTPS reset URL required |
| IDENTIFIER_ENCRYPTION_KEYS | JSON Fernet key ring; first key encrypts, all keys decrypt. Required for optional tax identifiers, phone challenge destinations and HMRC credentials |
| PHONE_IDENTITY_HMAC_KEY | Stable random key independent of JWT/encryption rotation; required for permanent phone identity hashes |
| UPLOAD_MAX_BYTES | File limit, default 10 MiB; total HTTP body bounded with multipart overhead |
| EXPORT_EXPIRE_HOURS | Private export download lifetime, default 24 hours |
| WORKER_POLL_SECONDS | Durable job polling interval, default 3 seconds |
| CLAMAV_HOST, CLAMAV_PORT | ClamAV INSTREAM service; missing scanner fails file processing explicitly |
| SUBSCRIPTION_PLANS | JSON approved offer catalog; required ID/code/GBP price/month interval/trial days/cohort/terms version, optional entitlements |
| ACCOUNTANT_RECIPIENTS | JSON allowlist of verified accountant references; empty disables request creation |
| ENTITLEMENT_REQUIREMENTS | JSON mapping of feature (`exports`, `assistant`) to required entitlement; empty until product approves gating |

Provider client secrets, API keys, HMRC recognition, SMS/OCR/assistant endpoints and billing signatures are **not** invented environment variables that imply an implementation. Supply a selected adapter/composition root and its external secret configuration. Interfaces are in `app/services/integrations.py`, `delivery.py`, `files.py`; app providers default to disabled. The file worker accepts controlled adapters through `process_one`; a production composition root must supply a real OCR/parser adapter. `process_mtd_once` requires a configured recognized HMRC adapter and its integration worker. No mock adapter is installed by normal startup.

## Local startup and migrations

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/setup_env.py
docker compose up -d db
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Use a separate terminal for `.\.venv\Scripts\python.exe -m app.worker`; `--once` processes at most one queued file/export job and runs the reminder scheduler once. Open `/docs`; liveness is `/health`, database readiness `/health/db`. The API does not auto-run migrations on import. Access logging is disabled in the provided command to avoid logging OAuth callback query credentials; proxy logs must redact these routes too.

Migrations 0003–0005 are additive upgrades: 0003 creates 20 bookkeeping/support tables; 0004 preserves existing expense IDs/records while backfilling a canonical ledger and permits nullable email for phone-only identities; 0005 records explicit versus inherited work shares. Existing user/expense values are not reset. Legacy fuel/other costs lacking eligibility evidence are retained with a zero deduction and an explicit review reason. No historical demo financial data is inserted.

Before an upgrade on valuable data, take and verify your normal PostgreSQL backup and review offline migration SQL. Run `alembic current`, `alembic upgrade head`, then `alembic check`. Do not use `Base.metadata.create_all` as an upgrade mechanism. Downgrading the bookkeeping schema removes new bookkeeping tables; it is only exercised on disposable test data. 0004 refuses downgrade if phone-only accounts would become incompatible. Do not use downgrade/reset/volume removal as an application repair.

## Docker Compose

```powershell
docker compose config --quiet
docker compose build api worker
docker compose up -d
docker compose ps
```

The existing `postgres_data` volume is preserved. The migration service runs against that configured database after PostgreSQL is healthy; API/worker wait for its successful completion. The API binds localhost port 8000; the database keeps its localhost port mapping. This startup command intentionally applies migrations, so use it only on the intended configured environment.

ClamAV integration follows the [official daemon/protocol documentation](https://docs.clamav.net/manual/Usage/Scanning.html); its socket stays private to the service network. For local malware scanning, set `CLAMAV_HOST=clamav` in local configuration and start `docker compose --profile scanning up -d`. The optional ClamAV service has its own signature volume and no public port. Processing may fail while signatures initialize; inspect the sanitized job error and retry after readiness. ClamAV is an implemented adapter; OCR remains a separate provider requirement. Private uploads/exports live in PostgreSQL BYTEA, so the database backup includes file bytes. No public file hosting is configured.

## Tests and contract regeneration

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/export_contracts.py
.\.venv\Scripts\python.exe -m compileall -q app migrations scripts
```

The test fixture starts a randomly named PostgreSQL 16 container with a random database/password, random localhost port and tmpfs storage. It migrates to head and runs Alembic metadata drift checks before tests. Tests roll back ordinary cases and use explicit test-owned accounts for real concurrent connections. Migration downgrade/upgrade experiments run in a disposable schema, never the configured development database. Docker failures are test failures, not hidden skips or SQLite substitutes.

The original isolated HEAD baseline passed 180 tests. Added tests exercise owner isolation, idempotent posting under concurrent connections, stale edits, old expense synchronization, edited receipt values/drafts/confirmation/reversal, mileage bands/odometers, statement gross/fee/net/dedup/overlap/reversal, both reconciliation modes, encrypted identifiers, phone challenge failures, reports, private exports/photos, reminder dedup, consent, trial policy and uncertain HMRC outcomes. Controlled adapters prove internal contracts only. See the implementation status for the final test result.

## Jobs and operations

File/export jobs commit their actual result. Workers use owner locking, transactional savepoints and `FOR UPDATE SKIP LOCKED`; a process crash before commit leaves the job queued. A provider error produces sanitized `error_code`, `retryable`, attempts and a failed state. Poll the job/resource; retry eligible failures with `/jobs/{id}/retries` or C08, using expected version and a new action key. Processing is limited to five attempts. OCR manual review is available even if extraction fails; unscanned attachments remain quarantined.

CSV import requires exactly the header documented in the frontend handoff. Do not enable a PDF/platform parser until sample fixtures validate its actual layout, fees, dates, external IDs, refunds and adjustments. Unsupported formats fail rather than inventing extraction results. Ledger changes after an MTD enqueue/unknown/accepted period require a supported provider correction process and are rejected by current routes.

MTD sends are a durable outbox. The integration worker commits intent before remote calls and stores each business's actual accepted/rejected/unknown result. A timeout is unknown; a lost submitting worker becomes unknown through `recover_uncertain_submissions` after five minutes. Never automatically resend an uncertain snapshot. Reconcile against the provider, preserve references and resolve status through `/mtd/updates/{id}/reconciliation` with the current update version and an idempotency key. This invokes the configured adapter's status-query method, not submit. No real HMRC provider or production recognition is installed; current official HMRC access restrictions are linked in the status report.

Billing adapters must verify signatures before returning normalized events, enforce the selected provider's idempotency protocol, map customers to server-approved subscriptions and supply ordered events. Checkout/cancellation receive the action idempotency key. Webhook event IDs deduplicate under the owner lock; stale sequences do not regrant old states. Paid entitlements derive from the approved server plan, not arbitrary event entitlement strings. An HTTP 503 is not a successful payment.

Keep encryption keys outside backups of database data. Rotate by prepending a new Fernet key, retaining old keys until all ciphertext has been deliberately re-encrypted and verified. Do not rotate the phone identity hashing key as a JWT rotation; it identifies existing accounts. Define and approve file/identifier/conversation retention, legal hold, hosting jurisdiction and deletion workflows before automated removal. Expired export URLs are denied; this implementation does not delete retained evidence or promise a fixed legal retention date.
