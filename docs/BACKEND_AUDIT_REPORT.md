# TaxiAiBooks backend audit

Date: 26 October 2026 (Asia/Dhaka). Scope: repository baseline and Phase 02 authentication/security. The attachment contains a broader Phase 02–16 roadmap; this implementation covers the audit and Phase 02. No pre-existing audit report was present.

## Baseline inspected

Python 3.12/FastAPI; synchronous SQLAlchemy 2/psycopg; PostgreSQL 16; Alembic revision `0001_users_expenses`; Pydantic v2; PyJWT HS256; pwdlib Argon2id; pytest/httpx. Registration, form-based email login, `GET /api/v1/users/me`, health endpoints and owner-scoped expense CRUD were present.

Existing strengths:

- Random local secret generation, ignored `.env`, validated secret lengths, parameter hiding on database errors.
- Normalized unique email addresses, Argon2id password hashes, generic credential failures and dummy password verification for unknown accounts.
- Strict expense input, integer pence, soft deletion, predictable pagination and ownership filters returning indistinguishable missing/foreign-record errors.
- Validation responses omit raw inputs; database failures hide connection details.
- Tests use disposable PostgreSQL containers, apply migrations and check schema drift. They never substitute SQLite or use the development database.

Baseline infrastructure-free tests: `23 passed, 55 deselected`. The first PostgreSQL regression run during implementation passed all 78 existing cases after adapting assertions for the new access-token lifetime and additive profile field.

## Findings and Phase 02 disposition

| Priority | Baseline gap | Disposition |
| --- | --- | --- |
| High | Access JWTs could not be revoked before expiry | Added required session IDs and server-side expiry/revocation checks to every authenticated request |
| High | No refresh rotation or replay detection | Added hashed refresh credentials, user-row locking and family revocation on reuse |
| High | No logout/session management | Added current/all-session logout, paginated device sessions and owner-scoped revocation |
| High | No password recovery/change | Added hashed single-use expiring recovery credentials, SMTP adapter, password changes and session invalidation |
| High | No login/OTP throttling | Added atomic PostgreSQL counters shared across workers; failures commit counters |
| Medium | No authentication audit trail | Added minimal security events without credentials, raw email, phone or biometric data |
| Medium | No self-service profile updates | Added a validated display-name PATCH; identity/password fields cannot be mass assigned |
| Medium | No external identity verification | Added strict Google/Apple native ID-token validation and one-time nonce binding; live integration remains unverified |
| Medium | No SMS verification design | Added provider interface, disabled default, hashed codes, expiry, attempt limits and user/session binding |
| Medium | No biometric design | Documented device-local biometric gating and server password reauthentication; server never accepts biometric assertions |

No confirmed cross-user expense access was found in the inspected implementation. Existing expense ownership and regression tests remain required; see the completion report for the final result.

## Phase 02 follow-up review

Reviewing the implemented phase found a login-throttling mismatch: authentication canonicalized Unicode/IDNA emails, while rate-limit target keys only stripped/lowercased them. Regression tests confirmed that alternating equivalent spellings admitted an eleventh attempt against the same account. Login now uses the authentication canonicalizer for its rate-limit key; both punycode/Unicode-domain and composed/decomposed local-part tests enforce the shared ten-attempt budget.

The review also found missing audit records for unknown/foreign-session OTP challenges and failed SMS delivery. These paths now commit `otp_rejected` and `otp_delivery_failed` respectively, while retaining generic errors, rolling back failed issuance and storing no secret values. Four new PostgreSQL regression cases reproduced these gaps before the fixes and pass afterward. No schema changes were required; revision `0002_auth_security` remains the migration head.

## Remaining deployment/external work

Google/Apple approved client IDs, actual native credentials and end-to-end verification are outstanding. SMTP credentials, a hosted HTTPS recovery screen and delivery validation are outstanding. A real SMS provider must be selected, implemented and tested. Apple web authorization-code exchange, provider revocation notifications, explicit identity linking and verified email-change flows are outside the implemented native ID-token scope.

Production infrastructure remains outside Phase 02: HTTPS and trusted proxy setup, ingress request-size/rate controls, database role permissions/backups, monitoring/alerting and approved retention/purge scheduling. Synchronous SMTP can create observable recovery timing differences; a durable delivery worker is a future production hardening item. Generic recovery response bodies and failure handling do not promise timing indistinguishability.

Phases 03–16 (onboarding, vehicles, ledger extensions, tax/HMRC, receipts, subscriptions, notifications, privacy exports and deployment) have not been implemented by this change. No tax-rule, legal-compliance or live-provider approval claim is made.

See [AUTH_API.md](AUTH_API.md) and [PHASE_02_COMPLETION_REPORT.md](PHASE_02_COMPLETION_REPORT.md).
