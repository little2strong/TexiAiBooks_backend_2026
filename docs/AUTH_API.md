# Authentication API — Phase 02

Base path: `/api/v1`. Password authentication remains JSON registration plus OAuth2 form login. Protected endpoints require `Authorization: Bearer <access_token>`. Use HTTPS outside local development. Auth/profile responses, including handled errors, send `Cache-Control: no-store`, `Pragma: no-cache` and `X-Content-Type-Options: nosniff`.

## Endpoints

| Method/path | Auth | Request | Success |
| --- | --- | --- | --- |
| `POST /auth/register` | Public | JSON `email`, `password` | 201 existing user response: id/email/timestamps |
| `POST /auth/login` | Public | **Form** `username` (email), `password`, optional `device_name` (1–100 chars) | 200 token pair |
| `POST /auth/refresh` | Refresh credential | JSON `refresh_token` | 200 rotated pair, same session |
| `POST /auth/logout` | Access | No body | 204, current session revoked |
| `POST /auth/logout-all` | Access | No body | 204, all sessions including current revoked |
| `GET /auth/sessions` | Access | Query `limit=20` (1–100), `offset=0` (0–100000) | 200 array of own device sessions |
| `DELETE /auth/sessions/{session_id}` | Access | UUID path | 204; foreign/missing 404 |
| `GET /users/me` | Access | No body | 200 id/email/timestamps plus nullable `display_name` |
| `PATCH /users/me` | Access | JSON `display_name` (trimmed, 1–100 chars) | 200 updated profile |
| `POST /auth/change-password` | Access + current password | JSON `current_password`, `new_password` | 204; all sessions/recovery links invalidated |
| `POST /auth/reauthenticate` | Access + password | JSON `password` | 200 `{"reauthenticated":true,"expires_in":300}` |
| `POST /auth/forgot-password` | Public | JSON `email` | 200 uniform message when delivery configured; otherwise 503 |
| `POST /auth/reset-password` | Recovery credential | JSON `token`, `new_password` | 204; all sessions/recovery links invalidated |
| `POST /auth/provider-challenge` | Public | JSON `provider`: `google` or `apple` | 200 `challenge_id`, `nonce`, `expires_in:300` |
| `POST /auth/providers/{provider}` | Verified provider token | JSON `id_token`, `challenge_id`, optional `device_name` | 200 application token pair |
| `POST /auth/otp/send` | Access | JSON `phone` in E.164, e.g. `+447700900123` | 200 `challenge_id`, `expires_in:300`; disabled provider 503 |
| `POST /auth/otp/verify` | Access, same user/session | JSON `challenge_id`, `code` (six ASCII digits, string) | 200 `{"verified":true}` |

Extra JSON fields are rejected. Passwords remain 8–128 characters without trimming. Registration duplicate email: 409. Invalid credentials/tokens: 401 with Bearer challenge for application credentials. Invalid/expired/reused recovery or OTP credentials: 400. Invalid input: 422 without echoing secret values. Rate limits: 429 with `Retry-After`. Temporary database failure: 503 without connection details.

`PATCH /users/me` deliberately allows only display-name editing; email, ownership, password hashes and identity fields are rejected. Changing an email requires a future verified email-change workflow. Registration's original response shape is retained; `GET /users/me` adds `display_name`.

## Tokens and device sessions

Example token response (values are placeholders):

```json
{
  "access_token": "<signed-access-jwt>",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_token": "<opaque-one-time-refresh-credential>",
  "refresh_expires_in": 2591999,
  "session_id": "<uuid>"
}
```

The access-token default is 15 minutes, configurable from 1–30 minutes. Existing `.env` values of 30 minutes remain valid and are not rewritten. Refresh sessions have an absolute lifetime of 30 days by default (1–90 configurable); refreshing does not extend that deadline. Returned `refresh_expires_in` is the remaining lifetime in whole seconds.

Access tokens require HS256 signature, configured issuer/audience, `iat`, `exp`, UUID `sub`, UUID `sid`, UUID `jti` and `type=access`. Every protected request checks that the session belongs to that user and is neither expired nor revoked. Logout, replay detection and password changes therefore reject already-issued access JWTs too. Database unavailability never bypasses authentication.

Each login creates an independent device family. Refresh credentials are random 48-byte values; only keyed SHA-256 hashes are persisted. Refresh consumes its credential and issues a new one atomically. Reusing a consumed credential revokes that entire family, including its latest access/refresh credentials. Other devices remain active unless all sessions are revoked.

Clients must serialize refresh requests and atomically replace their stored credential. A retry of a refresh whose response was lost is treated as replay and requires a new login. There is intentionally no reuse grace period. A device name is an untrusted display label, never proof of device identity.

Device listings contain `id`, `device_name`, `created_at`, `last_used_at`, `expires_at`, `revoked_at`, including historical/expired sessions, ordered newest first with an ID tiebreaker. No credential hashes or raw tokens are returned. `last_used_at` records token issuance/refresh, not every API read.

Deployment compatibility: apply `0002_auth_security` before running this application. Existing users, Argon2 password hashes and expenses are preserved. JWTs issued by the old implementation lack session claims and are intentionally rejected; users must log in once after rollout. Rollback requires the previous application build; downgrade removes Phase 02 records and the display-name column while preserving baseline users/expenses.

## Password recovery and account security

Set `SMTP_HOST`, `SMTP_PORT` (implicit TLS, default 465), `SMTP_FROM`, optional `SMTP_USERNAME`/`SMTP_PASSWORD`, and an HTTPS `PASSWORD_RESET_URL`. SMTP uses certificate-verified TLS and a timeout. No credentials or delivery messages are logged. Configuration is server-only.

Recovery requests use the same public message for existing and nonexistent accounts: `If the account exists, recovery instructions will be sent`. Unconfigured delivery returns 503 for every account. A delivery failure for an existing account records `password_reset_delivery_failed`, rolls back the new credential, and retains the same public response. Inspect operational events for delivery failures. SMTP transport is synchronous; the API does not claim identical response timing for known and unknown accounts.

Reset credentials are random, hashed with a separate domain prefix, single use and valid for 20 minutes by default (5–60 configurable). A successful resend invalidates previous links. Successful reset/change invalidates all device sessions and all outstanding recovery links; a new login is required. Password change requires the current password and rejects an identical replacement. Reset does not log a user in automatically.

The email link uses `PASSWORD_RESET_URL#token=...` so ordinary query/access logs do not receive the credential. The HTTPS reset screen must read the fragment, remove it from browser history, avoid third-party scripts/analytics on that screen and POST the token in a JSON body. That frontend and real email delivery still need configuration and verification.

Password reauthentication checks the current hash and records `reauthenticated_at` on the active session. It does not extend session lifetime or issue an additional token. The 300-second result defines a freshness window for future sensitive operations; those operations must check the stored timestamp and active session themselves.

## Google and Apple native sign-in

**Live provider login is pending configuration and valid-credential testing.** Set JSON environment arrays `GOOGLE_CLIENT_IDS=["approved-client-id"]` and/or `APPLE_CLIENT_IDS=["approved-bundle-or-service-id"]`. Empty arrays return 503. Do not enable IDs belonging to other apps or use test IDs in deployment.

1. Request a provider challenge before opening the native authorization flow.
2. Pass the returned `nonce` **exactly** as the provider authorization nonce. Apple receives a SHA-256 nonce generated by the backend; do not hash that returned value again.
3. POST the resulting ID token plus challenge ID to that provider's endpoint.

The validator uses fixed HTTPS JWKS endpoints and cached key lookup with refresh for unknown key IDs. It accepts only RS256, requires a key ID, verifies the cryptographic signature, issuer, configured audience, expiry, issued-at and subject, and checks authorized presenter (`azp`) where supplied or required for multiple audiences. It verifies an expiring, provider-specific, single-use nonce before account/session creation. Token header URLs never control key fetching.

Users are identified by provider + stable subject, never by email alone. New provider accounts require a verified email claim. A matching existing email produces 409; automatic account linking is disabled. Returning users can authenticate by subject without a newly supplied email. A random unguessable Argon2 password is stored for provider-created accounts; no client-selected password is silently assigned.

This is a native ID-token exchange, not an Apple web authorization-code exchange. Apple developer keys/client-secret generation, code exchange/refresh-token validation, credential-state callbacks and provider revocation notifications are not implemented. The native client must handle Apple's credential-state changes and log out appropriately. Real provider setup, client nonce behavior and revocation lifecycle must be verified before release.

Rules checked on 26 October 2026 against [Google backend verification](https://developers.google.com/identity/sign-in/ios/backend-auth), [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [Apple user verification](https://developer.apple.com/documentation/signinwithapple/verifying-a-user), and provider discovery metadata ([Google](https://accounts.google.com/.well-known/openid-configuration), [Apple](https://appleid.apple.com/.well-known/openid-configuration)). Both discovery documents advertise RS256. Local tests use real RSA signatures and stub JWKS transport; they are not live-provider verification.

## SMS OTP and biometrics

SMS is disabled by default. `SMSDelivery` defines `enabled` and `send_code(phone, code)`; select and implement a real provider, wire it through application initialization and validate delivery before enabling. There is no mock/test provider switch in production configuration. Tests inject adapters only in test applications.

OTP is currently an authenticated phone-delivery verification primitive. It does not grant a login session, replace a password, assert MFA, or persist a verified contact on the user profile. A later passwordless/MFA flow requires a previously bound verified phone and separate recovery/security policy. This avoids allowing a caller to choose an arbitrary phone as proof of account ownership.

Codes have five-minute expiry and a maximum of five verification attempts per challenge. Resending invalidates earlier phone challenges for that user. Challenges bind to user, current device session and a hashed E.164 target. Codes are stored only as keyed hashes including the challenge ID; phone values and codes are passed only to the provider and never returned by the API. Provider failure rolls back issuance. Verification is single use and does not expose the target.

For biometric unlock, Flutter should store its refresh credential in OS secure storage protected by the platform's biometric/user-presence policy. After local verification it can request ordinary refresh, subject to the same rotation, expiry and revocation checks. Store access tokens in memory when possible. Clear local credentials on logout, account change and biometric-enrollment/key invalidation. No fingerprint, face template, image, biometric flag or sensor output belongs in an API request or database.

A locally gated refresh token is not remote cryptographic proof that biometrics just occurred. Sensitive server actions require the actual password endpoint or a future audited WebAuthn/passkey challenge/response implementation. Client booleans such as `biometric_verified` are rejected; no bypass exists. The current endpoint accepts password reauthentication only.

## Rate limits, events and operations

Fixed 15-minute windows are stored atomically in PostgreSQL and apply across application workers. Both IP and normalized target/user limits apply where specified; successful and failed attempts count. Login target keys use exactly the same email normalization as authentication, including IDNA/punycode and Unicode normalization, so equivalent email spellings share an attempt budget. Invalid addresses still consume attempts and return the same generic credential error. Forwarded headers are not read by the limiter. Deploy the ASGI server behind explicitly trusted proxies only, because trusted proxy middleware can legitimately set the peer address. Fixed windows permit boundary bursts; add ingress-wide abuse controls for deployment.

| Action | Per target/user | Per peer IP |
| --- | --- | --- |
| Registration | 5 | 20 |
| Login | 10 | 30 |
| Refresh | — | 120 |
| Password change / reauthentication (separate counters) | 5 | 30 |
| Forgot password | 3 | 20 |
| Reset password | — | 20 |
| Provider challenge / provider login (separate counters) | — | 30 |
| OTP send | 3 | 10 |
| OTP verification | 10, plus five attempts/challenge | 30 |

Audit events cover registration/login, session creation/rotation/replay/revocation, password recovery/change/reauthentication, provider failures, profile updates, OTP and throttling. An unknown, foreign-user or foreign-session OTP challenge records the same `otp_rejected` event without exposing the supplied code or challenge owner. Failed SMS delivery rolls back issuance and then commits a separate `otp_delivery_failed` event. Stored fields are event name, UUID references, timestamps and optional keyed peer hash. They contain no raw credentials, email, phone or biometric data. There is no public audit-edit endpoint. Production database roles and operational audit retention still need configuration; database administrators are not cryptographically prevented from modifying these rows.

All credential/session mutations serialize on the user row before locking session/challenge records. Provider nonces are consumed in their own transaction before locking/creating an account. A request already authorized before a concurrent logout may finish; subsequent authentication checks reject the revoked session. Concurrent refresh and recovery tests use independent PostgreSQL connections.

Keep consumed refresh hashes until their device family's absolute expiry; deleting them early loses replay detection. Retention cleanup should delete expired challenges and old rate-limit windows, then expired families with their credentials and referencing challenges, according to the approved operational policy. Keep security events according to an approved security/privacy retention period. No automatic purge or speculative legal retention period is enabled in this phase. Monitor delivery-failure, replay and throttle events. Rotating the JWT/HMAC secret invalidates existing JWTs and hashed recovery/refresh credentials and requires fresh login.

## Verification

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.txt
& '.\.venv\Scripts\python.exe' -m pytest -q
& '.\.venv\Scripts\python.exe' -m pip check
```

The suite provisions its own disposable PostgreSQL 16 container, migrates to head, checks schema drift, and tests original APIs plus expiry/revocation, ownership, replay, concurrency, recovery, rate limits, OTP and local RSA provider verification. Tests never require or claim valid provider credentials. See [PHASE_02_COMPLETION_REPORT.md](PHASE_02_COMPLETION_REPORT.md) for recorded commands/counts and remaining configuration.
