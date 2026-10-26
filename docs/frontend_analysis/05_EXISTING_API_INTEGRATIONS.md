# Existing API integrations

Analysis date: 27 October 2026 (Asia/Dhaka). Source commit: `a5a9c4456ac190c0cb4bde9b4ae043f04f9a832f`. Documentation only.

**Evidence:** OBSERVED = source behavior; PROPOSED = future requirement; UNVERIFIED = external backend report or unresolved decision. No backend source/contract supplied.

## Finding: zero observed API operations

All lib/test files were searched for Dio/HTTP invocations, endpoints, DTO serialization, auth and storage. Only Dio construction and dependency registration exist. SVG namespace URLs and example API_BASE_URL strings are not endpoints. A configured client is not an API integration.

| Feature | Method | Endpoint | Flutter File | Request | Response | Auth | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HTTP infrastructure | N/A | API_BASE_URL (empty default) | lib/core/config/app_config.dart::AppConfig; lib/core/network/api_client.dart::ApiClient | BaseOptions only | No response model | None | OBSERVED plumbing, no request |
| DI registration | N/A | None | lib/apps/binding/initial_binding.dart::InitialBinding | Get.put permanent | Client instance | None | OBSERVED registration |
| All functional modules | None | None | All lib/features views/controllers | None sent | Local literals | No session/JWT | ZERO integrations |

Base configuration: Accept application/json, connect/send 15s, receive 30s, optional injected Dio. No authorization header, token storage, refresh, interceptor, retries, cancellation usage, error mapping, pagination, multipart, downloads, file picker, OCR, PDF parser, provider OAuth, HMRC call or Firebase. TimedReveal results are simulations, not HTTP mocks. No fromJson/toJson or API repository exists.

## Reported backend remains unverified

The user reports FastAPI/PostgreSQL registration, login, JWT, expense CRUD and tests. No Python service, Alembic migrations, Compose, OpenAPI or backend tests were supplied here. Obtain its OpenAPI and redacted request/response examples before implementation. Check login content type, claims/token lifecycle, ownership isolation, and expense date/money semantics. Reuse verified behavior rather than creating parallel expense ledgers. No live backend was called.

## Proposed contracts are separate

Document 06 is the canonical PROPOSED catalog; document 10 maps it to screens. Count unique HTTP method + path pairs. None asserts an existing backend contract. No credentials are needed for this analysis.
