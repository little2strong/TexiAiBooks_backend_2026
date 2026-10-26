# Phase 02 completion review

Review date: 26 October 2026, Asia/Dhaka. Scope: backend audit and Phase 02 authentication/security from the supplied roadmap. Phases 03–16 have not been executed.

## Result

The local backend checkpoint passes: existing registration/login and expense APIs work, expired/revoked credentials are rejected, refresh reuse revokes its device family, recovery is single use, and cross-user sessions/expenses are protected. Proceeding to Phase 03 backend development is reasonable. Production release and live external integrations remain pending the configuration and verification below.

## Requirement review

| # | Requirement | Implemented/verified |
| --- | --- | --- |
| 1 | Preserve registration/login | Existing JSON registration/form login retained; regression suite passes |
| 2 | Short access JWT + rotating refresh | Default 15-minute access JWT; absolute 30-day refresh family; rotation and expiry tested |
| 3 | Hash refresh credentials | Domain-separated HMAC-SHA256 hashes only; storage assertions |
| 4 | Logout/revoke all | Current/all/individual session revocation; unexpired access JWTs rejected afterward |
| 5 | GET/PATCH self profile | Authenticated self-only GET and validated display-name PATCH; mass assignment blocked |
| 6 | Change/reset password | Current-password check; hashed expiring single-use recovery; all-session invalidation; SMTP adapter mocked, live delivery pending |
| 7 | Throttling/audit | PostgreSQL atomic shared counters; login/recovery/OTP/provider limits; secret-free security events; concurrent counter test |
| 8 | Google/Apple ID tokens | Actual RSA signature/issuer/audience/expiry/nonce validation; local cryptographic fixtures + stub JWKS; live provider setup pending |
| 9 | SMS OTP design | Provider protocol, disabled default, keyed code hashes, expiry/five attempts, one-time use, session/user binding; fake delivery in tests; real provider pending |
| 10 | Devices/biometrics | Paginated owner-scoped sessions; password reauthentication; documented OS secure-storage design; no biometric storage or trusted client flags |
| 11 | Additive migration/tests | Revision 0002; clean schema/drift, upgrade/downgrade/data compatibility, real PostgreSQL concurrency and API tests |
| 12 | API documentation | `docs/AUTH_API.md`, README and this report |

## Migration and compatibility

`0002_auth_security`, parent `0001_users_expenses`, adds nullable `users.display_name` plus `device_sessions`, `refresh_credentials`, `auth_challenges`, `external_identities`, `security_events`, and `auth_rate_limits`. No original migration or expense schema was changed. Original users, password hashes and expenses survive the additive upgrade and downgrade test.

Tests run migrations only against disposable test infrastructure. The development database has not been migrated or modified. Before running the updated local application, install dependencies and execute:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.txt
& '.\.venv\Scripts\python.exe' -m alembic upgrade head
```

Old JWTs intentionally stop working because they lack required session/issuer/audience/type claims. Log in again after rollout. Login responses add refresh/session fields; GET profile adds nullable `display_name`. Registration response and expense contracts remain compatible. Access lifetime defaults to 15 minutes; a previous 30-minute local `.env` remains valid. Maximum configurable access lifetime is now 30 minutes.

Downgrade removes the Phase 02 tables and display names, so it requires a backup/review and the previous application build. No downgrade was run on the development database.

## Tests and checks

Final full-suite result after the follow-up review: **180 passed, 0 failed, 0 skipped**, one upstream deprecation warning, in 47.61 seconds. This includes 126 PostgreSQL cases and 54 infrastructure-free cases. `pip check` reports no broken requirements; `git diff --check` passes. OpenAPI inspection confirms all 17 authentication/profile operations and security declarations on protected operations. `alembic heads` reports the single head `0002_auth_security`.

Commands:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
& '.\.venv\Scripts\python.exe' -m pip check
git diff --check
```

Coverage includes prior expense CRUD/ownership/validation, registration duplicates, JWT claim/expiry/session rejection, hashed credential storage, replay family isolation, logout variants, session IDOR, profile persistence after logout/login, password changes, recovery resend/reuse/expiry, delivery failure rollback, secret redaction, authenticated route coverage, rate-limit persistence/window reset, OTP limits/expiry/user/session binding, and no trusted biometric flag. Provider tests sign real local RSA tokens and exercise the actual verifier with a stub JWKS transport, including signature, issuer, audience, nonce, subject, expiry and authorized-presenter failures. SMTP TLS behavior uses a mocked transport.

Concurrency tests use independent committed PostgreSQL connections: two refresh attempts yield one rotation plus a replay rejection/family revocation; two resets yield one password change; six shared-limit attempts yield exactly three admitted requests. Migration testing downgrades/upgrades within an isolated test transaction, preserves seeded baseline user/expense values and checks Alembic schema drift.

The existing Starlette TestClient emits one upstream deprecation warning recommending httpx2. It does not fail tests. This change does not migrate the existing test transport.

Confirmed implementation defects found and fixed during review: incompatible regex constraint on SecretStr OTP input; null provider email causing an internal error; malformed session-identifier types needing explicit rejection. Final results supersede earlier failing development runs.

Follow-up Phase 02 review also reproduced and fixed a login rate-limit bypass using equivalent Unicode/IDNA email spellings, missing audit records for unknown/foreign-session OTP challenges, and missing SMS-delivery-failure events after issuance rollback. Four new PostgreSQL regressions failed before the corrections and passed afterward (`4 passed, 53 deselected`). Login uses the exact authentication email canonicalizer for its target budget. OTP failure events contain only existing event metadata and never provider exception text or codes. These fixes add no migration or endpoint and preserve the documented response contracts.

## Endpoint inventory

All paths below are relative to `/api/v1`; full request/response/error contracts are in `AUTH_API.md`.

| Methods | Path |
| --- | --- |
| POST | `/auth/register` |
| POST | `/auth/login` |
| POST | `/auth/refresh` |
| POST | `/auth/logout` |
| POST | `/auth/logout-all` |
| GET | `/auth/sessions` |
| DELETE | `/auth/sessions/{session_id}` |
| GET, PATCH | `/users/me` |
| POST | `/auth/change-password` |
| POST | `/auth/reauthenticate` |
| POST | `/auth/forgot-password` |
| POST | `/auth/reset-password` |
| POST | `/auth/provider-challenge` |
| POST | `/auth/providers/{provider}` (`google`, `apple`) |
| POST | `/auth/otp/send` |
| POST | `/auth/otp/verify` |

## Changed files

| Files | Purpose |
| --- | --- |
| `app/api/auth.py`, `app/api/deps.py`, `app/api/users.py` | Endpoints, session-bound authentication, self profile |
| `app/core/config.py`, `app/core/security.py`, `app/main.py` | Settings, JWT/hash helpers, adapter wiring and security headers |
| `app/models/auth.py`, `app/models/user.py`, `app/models/__init__.py` | Session/credential/challenge/identity/rate/audit models; nullable name |
| `app/schemas/auth.py`, `app/schemas/user.py` | Strict requests, token/session/profile responses and secret validation |
| `app/services/auth.py`, `app/services/auth_security.py`, `app/services/sessions.py` | Registration/login, locking/rotation/revocation, rate limits/audits |
| `app/services/passwords.py`, `app/services/delivery.py` | Recovery/change-password and verified-TLS SMTP abstraction |
| `app/services/identity.py`, `app/services/otp.py` | OIDC verification, nonce consumption and SMS verification primitive |
| `migrations/versions/0002_auth_security.py` | Additive database revision |
| `tests/test_auth.py`, `tests/test_unit.py` | Existing regression assertions updated for new contracts |
| `tests/test_auth_security.py`, `tests/test_auth_transactions.py` | API, security, rate-limit, concurrency and migration regressions |
| `tests/test_identity.py`, `tests/test_delivery.py` | Local RSA/stub JWKS verification and mocked TLS SMTP |
| `.env.example`, `scripts/setup_env.py`, `requirements.txt` | Documented configuration, new-install 15-minute default, pinned cryptography |
| `README.md`, `docs/BACKEND_AUDIT_REPORT.md`, `docs/AUTH_API.md`, `docs/PHASE_02_COMPLETION_REPORT.md` | Audit, API and completion documentation |

## Outstanding external configuration and limitations

- Google: approved client IDs, native client nonce support, actual ID-token login and provider/network behavior verification.
- Apple: approved app identifiers/capabilities, native nonce/credential-state behavior and actual ID-token verification. Apple web code exchange/client-secret flow and server-to-server revocation notifications are not implemented.
- Email: SMTP host/from/auth credentials and hosted HTTPS reset page, deliverability, monitoring and a real reset walkthrough. The adapter uses verified implicit TLS. The current synchronous delivery path has timing differences; a durable background delivery workflow is a future production hardening item.
- SMS: select a provider, implement/wire `SMSDelivery`, configure credentials and verify delivery. Current OTP proves delivery for the authenticated session; it does not persist an enrolled phone or enable passwordless login/MFA.
- Flutter biometric integration: implement OS-controlled storage/user-presence gating. Server behavior is tested; no Flutter app was changed. Refresh cannot serve as remote proof of fresh biometric verification.
- Production: HTTPS, explicitly trusted proxies, ingress abuse/body-size controls, least-privilege database roles, monitoring/alerts and approved audit/credential retention with purge scheduling remain deployment work. There is no claim of a completed penetration test or production readiness certification.
- Verified email changes, explicit provider linking and account deletion are outside this Phase 02 contract. Email/security fields cannot be patched through the profile endpoint.

No provider verification has been bypassed for production. No live Google, Apple, SMTP or SMS integration has been represented as tested. No production services were deployed or modified.
