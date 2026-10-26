# TexiAiBooks backend — প্রথম milestone

> **Phase 02 update (26 October 2026):** Authentication now includes revocable device sessions, rotating hashed refresh credentials, password recovery/change, profile updates, shared rate limits, security events and configurable Google/Apple ID-token validation. Read [docs/AUTH_API.md](docs/AUTH_API.md), [the audit](docs/BACKEND_AUDIT_REPORT.md) and [the completion report](docs/PHASE_02_COMPLETION_REPORT.md) for current contracts and external configuration. Google/Apple login, SMTP and SMS live verification remain pending. Existing `.env` is preserved; new installations default to 15-minute access tokens. Apply the additive migration and log in again after upgrading.

এখানে Register → Login → নিজের expense তৈরি, দেখা, বদলানো এবং soft delete করা যায়। এটি local development-এর ভিত্তি; production-ready দাবি করা হচ্ছে না।

Stack: Python 3.12, FastAPI/Uvicorn, PostgreSQL 16, synchronous SQLAlchemy 2 + psycopg 3, Alembic, Pydantic v2, PyJWT, pwdlib/Argon2, pytest/httpx। Database-এর কাজ করা route ও dependency-গুলো সাধারণ `def` ব্যবহার করে।

## ১. PowerShell ও Python environment

সব command এই repository-র PowerShell terminal-এ চালাবেন:

```powershell
Set-Location -LiteralPath 'D:\FLutter apps\TexiAiBooks_backend_2026'
py -0p
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
}
& '.\.venv\Scripts\python.exe' --version
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.txt
& '.\.venv\Scripts\python.exe' -m pip check
```

বর্তমান `.venv` Python 3.12-এর। অন্য version-এর `.venv` থাকলে আগে সেটি আলাদা নামে রাখুন, তারপর `py -3.12 -m venv .venv` চালান। Virtual environment activate বা PowerShell execution policy পরিবর্তনের দরকার নেই।

`requirements.txt`-এ runtime এবং `requirements-dev.txt`-এ অতিরিক্ত test dependency-র exact version আছে। এই dependency set Windows/Python 3.12-এ যাচাই করা। শুধু API চালাতে `-r requirements.txt` যথেষ্ট। নতুন dependency নিলে দুটি pinned file একসঙ্গে review/update করবেন।

## ২. Local configuration

```powershell
& '.\.venv\Scripts\python.exe' scripts/setup_env.py
```

এটি random database password ও JWT secret দিয়ে `.env` একবার তৈরি করে; secret দেখায় না এবং আগের `.env` বদলায় না। `.env.example` শুধু field ও placeholder দেখায়; সরাসরি copy করে চালানোর বদলে উপরের script ব্যবহার করুন। `.env` ও `.venv` Git-এ রাখা হবে না।

Default database: `taxiaibooks`, user: `taxi_user`, host: `127.0.0.1`, host port: `5433`, container port: `5432`। Password একবারই `.env`-এ রাখবেন; application সেটি দিয়ে নিরাপদে `postgresql+psycopg` URL বানায়। `@`, `%`, `/`-এর মতো character নিজে URL-encode করার দরকার নেই। Alembic-ও একই settings ব্যবহার করে এবং secret URL `alembic.ini`-এ রাখে না।

## ৩. Docker ও PostgreSQL চালানো

```powershell
docker --version
docker compose version
docker info
```

`docker info`-তে server-এর তথ্য আসতে হবে। শুধু CLI version দেখানো engine চলছে তার প্রমাণ নয়। Engine বন্ধ থাকলে Docker Desktop খুলে Linux engine ready হওয়া পর্যন্ত অপেক্ষা করুন। Command দিয়েও চালু করা যায়:

```powershell
docker desktop start
docker info
```

এই computer-এ Docker Desktop-এর user installation path পাওয়া গেছে। প্রয়োজনে:

```powershell
Start-Process -FilePath "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe" -WindowStyle Hidden
```

Port খালি আছে কি না দেখুন। কোনো output না এলে সাধারণত listener নেই:

```powershell
Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction SilentlyContinue
docker compose config --quiet
docker compose up -d --wait db
docker compose ps
```

প্রথমবার image download হতে সময় লাগে। PostgreSQL healthcheck সফল হলে service ready। Port অন্য application ব্যবহার করলে সেই application বন্ধ করুন, অথবা `.env`-এর `POSTGRES_PORT` একটি খালি port-এ বদলে Compose ও API পুনরায় চালান।

Database port শুধু `127.0.0.1`-এ publish হয়। Data `texiaibooks_postgres_data` named volume-এ থাকে। একই volume থাকলে `.env`-এ password বদলালেই PostgreSQL-এর পুরোনো password বদলায় না; পুরোনো সঠিক credential ফিরিয়ে দিন। সংযোগ ঠিক করতে volume/database মুছবেন না।

## ৪. Migration ও API

```powershell
& '.\.venv\Scripts\python.exe' -m alembic upgrade head
& '.\.venv\Scripts\python.exe' -m alembic current
& '.\.venv\Scripts\python.exe' -m alembic check
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Current revision হবে `0002_auth_security (head)`। Schema বদলাতে Alembic ব্যবহার করুন; application `create_all()` চালায় না। ভবিষ্যতে model বদলালে `alembic revision --autogenerate -m "describe change"` দিয়ে migration তৈরি করে SQL ও downgrade review করবেন, তারপর `upgrade head` চালাবেন। আগের migration মুছবেন বা নতুন করে শুরু করবেন না।

Browser-এ খুলুন:

- Swagger: <http://127.0.0.1:8000/docs>
- API liveness: <http://127.0.0.1:8000/health>
- Database check: <http://127.0.0.1:8000/health/db>

`/health` database বন্ধ থাকলেও `200` দেয়। `/health/db` সত্যিই `SELECT 1` চালায়; database unavailable হলে connection detail না দেখিয়ে `503` ও `{"detail":"Database unavailable"}` দেয়। API startup-এ database connection আবশ্যক নয়; business endpoint চালাতে database ও migration লাগবে।

## ৫. Swagger দিয়ে পুরো flow

১. `POST /api/v1/auth/register` → **Try it out** → এই JSON দিয়ে **Execute**:

```json
{
  "email": "driver@example.com",
  "password": "local-demo-password-123"
}
```

সফল হলে `201` এবং user-এর `id`, `email`, timestamp পাবেন। Password/hash response-এ থাকবে না। একই email আবার দিলে `409`।

২. `POST /api/v1/auth/login`-এ `username` ঘরে **email address** এবং `password` ঘরে password দিন। Login **form data** (`application/x-www-form-urlencoded`), JSON নয়। `grant_type` দিলে `password` দিন; `scope`, `client_id`, `client_secret` খালি রাখা যায়। Response-এ `access_token`, `token_type: bearer`, `expires_in`, `refresh_token`, `refresh_expires_in`, `session_id` পাবেন। Default `expires_in: 900`; existing 30-minute `.env` দিলে `1800`। Refresh credential নিরাপদ storage-এ রাখুন এবং প্রতিবার refresh-এর পরে নতুন মান বসান।

৩. Swagger-এর উপরের **Authorize** চাপুন। সেখানেও `username` ঘরে email ও password দিন, **Authorize** → **Close**। Swagger নিজে login করে Bearer token ব্যবহার করবে। এরপর `GET /api/v1/users/me` দিয়ে user দেখুন।

৪. `POST /api/v1/expenses`-এ এই JSON পাঠান:

```json
{
  "amount_pence": 1250,
  "currency": "GBP",
  "category": "fuel",
  "expense_date": "2026-10-25",
  "note": "Fuel stop"
}
```

`1250` pence = £12.50। `owner_id` পাঠাবেন না; token-এর user থেকেই সেটি বসে। অচেনা request field প্রত্যাখ্যান করা হয়।

৫. `GET /api/v1/expenses?limit=20&offset=0` চালান। Response:

```json
{"items": [], "limit": 20, "offset": 0}
```

Expense থাকলে `items`-এ আসবে। একটি expense-এর `id` দিয়ে detail/PATCH/DELETE চালাতে পারবেন। PATCH-এ শুধু পরিবর্তিত field পাঠান, যেমন `{"amount_pence":1800,"note":null}`। DELETE সফল হলে body ছাড়া `204`; পরে ordinary read-এ আর আসবে না। Database record ও `deleted_at` থাকবে।

### Request ও authentication-এর নিয়ম

- Email-এর চারপাশের whitespace বাদ দিয়ে পুরো address lowercase করা হয়; register ও login-এ একই নিয়ম। Database-এ normalized email-এর unique constraint আছে।
- Password ৮–১২৮ character; whitespace ইচ্ছাকৃতভাবে trim করা হয় না। Argon2id hash রাখা হয়। ভুল email/password-এ একই generic `401` message।
- JWT lifetime default ১৫ মিনিট; `.env`-এর `ACCESS_TOKEN_EXPIRE_MINUTES` দিয়ে ১–৩০ মিনিট করা যায়। HS256 signature, issuer/audience, expiry, issued-at, UUID identifiers ও active device session যাচাই করা হয়। Missing/invalid/expired/revoked token-এ `401`। Access token-এর মেয়াদ শেষ হলে `/api/v1/auth/refresh` ব্যবহার করুন; revoked বা expired session হলে আবার login করুন।
- Protected request header: `Authorization: Bearer <access_token>`। Token/password application log-এ লিখবেন না।
- `amount_pence`: JSON integer, `1` থেকে `2147483647`; float, string ও boolean চলে না। Currency শুধু `GBP`।
- Category: `fuel`, `maintenance`, `insurance`, `licensing`, `parking`, `other`। এগুলো expense label; tax treatment বোঝায় না।
- `expense_date`: `YYYY-MM-DD`; `note`: optional, সর্বোচ্চ ২০০০ character। শুধু note-এ `null` দিয়ে মান মুছতে পারবেন। PATCH-এ অন্য field-এ `null`, invalid value ও empty object চলে না।
- List-এ limit ১–১০০ (default ২০), offset ০–১০০০০০ (default ০)। Order: `expense_date DESC`, `created_at DESC`, `id DESC`। একই data-র ordering নির্দিষ্ট থাকে; নতুন record আসলে offset page সরতে পারে।
- অন্য user-এর expense ও missing/deleted expense-এ একই `404`। List-ও শুধু নিজের active expense দেখায়।
- Timestamp PostgreSQL-এ timezone-aware; application update-এ `updated_at` বদলায়।

### PowerShell থেকে login-এর উদাহরণ

Server চলার সময় দ্বিতীয় terminal-এ, আগে উপরের demo user register করা থাকলে:

```powershell
$loginResult = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/auth/login' -ContentType 'application/x-www-form-urlencoded' -Body @{username='driver@example.com'; password='local-demo-password-123'}
$authHeaders = @{Authorization = "Bearer $($loginResult.access_token)"}
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/users/me' -Headers $authHeaders
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/expenses' -Headers $authHeaders
```

Flutter থেকেও login-এ form fields পাঠাবেন, registration ও expense-এ JSON পাঠাবেন।

## ৬. Tests

Docker engine ready রেখে:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
```

PostgreSQL tests নিজের unique-name `postgres:16` container, random localhost port এবং temporary filesystem তৈরি করে। **Development database ব্যবহার করে না।** একদম clean test database-এ Alembic `upgrade head`, revision check ও schema drift check চলে। প্রতিটি test transaction rollback হয়; শেষে শুধু test-এর নিজের container সরানো হয়। Development named volume অক্ষত থাকে।

Docker বন্ধ থাকলে PostgreSQL tests error দেখাবে; SQLite দিয়ে বদলে পাস দেখানো হবে না। আগে image download না থাকলে `docker pull postgres:16` চালিয়ে নিন। শুধু infrastructure ছাড়া tests চালাতে:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -m 'not postgres' -q
```

এটি PostgreSQL integration পরীক্ষা করে না। পুরো suite registration/duplicate race, Argon2 storage, login, JWT rejection, current user, expense lifecycle, validation, pagination, ownership, forged owner, soft delete ও health behaviour পরীক্ষা করে।

## ৭. Flutter device থেকে URL

| Flutter কোথায় চলছে | API base URL |
| --- | --- |
| Android emulator | `http://10.0.2.2:8000` |
| Windows desktop | `http://127.0.0.1:8000` |
| Physical Android, একই private Wi-Fi/LAN | `http://<laptop-LAN-IP>:8000` |

Emulator/phone access-এর জন্য server এভাবে চালানো লাগতে পারে:

```powershell
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
ipconfig
```

`ipconfig`-এর Wi-Fi/Ethernet IPv4 address ব্যবহার করুন; `0.0.0.0` client URL নয়। Phone-এ `127.0.0.1` দিলে phone নিজেকেই বোঝায়।

Windows Firewall বাধা দিলে Windows Security → Firewall & network protection → Advanced settings থেকে Python/API port `8000`-এর inbound permission **শুধু Private profile ও Local subnet**-এ দিন। Public profile বা PostgreSQL port খুলবেন না। এখানে কোনো firewall rule স্বয়ংক্রিয়ভাবে বদলানো হয়নি।

Local HTTP শুধু development-এর জন্য। Android cleartext HTTP blocked হলে Flutter project-এর **debug configuration**-এ HTTP allow করতে হবে (যেমন debug manifest-এর application-এ `android:usesCleartextTraffic="true"`) এবং INTERNET permission থাকতে হবে। এই backend কাজের অংশ হিসেবে Flutter repository বদলানো হয়নি। Release-এ HTTPS ব্যবহার করবেন। Flutter Web হলে তার browser origin অনুযায়ী আলাদা CORS configuration লাগবে; native emulator/desktop-এর জন্য CORS দরকার হয় না।

## ৮. নিরাপদে বন্ধ করা ও পরেরবার চালানো

Uvicorn terminal-এ `Ctrl+C`। PostgreSQL থামাতে:

```powershell
docker compose stop db
```

এতে database data থাকে। Container/network সরাতে চাইলে `docker compose down`-ও data volume রাখে। **`docker compose down -v` চালাবেন না**; এতে data volume মুছে যায়।

পরেরবার:

```powershell
docker info
docker compose up -d --wait db
& '.\.venv\Scripts\python.exe' -m alembic upgrade head
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## ফাইল কোথায়

| Path | কাজ |
| --- | --- |
| `app/main.py` | API entry point, app factory, controlled errors |
| `app/core/` | Settings, hashing, JWT |
| `app/db.py` | SQLAlchemy Base, engine, request-scoped session |
| `app/models/` | User/Expense database models |
| `app/schemas/` | Input validation ও public responses |
| `app/services/` | Auth ও owner-scoped expense operations |
| `app/api/` | Health, auth, users, expense routes |
| `migrations/`, `alembic.ini` | Schema history ও migration configuration |
| `compose.yaml` | Local PostgreSQL 16, healthcheck, named volume |
| `scripts/setup_env.py` | একবার random local `.env` তৈরি |
| `tests/` | Independent ও isolated PostgreSQL tests |

Income tracking, receipts, mileage, tax estimates, AI, subscriptions, accountant handoff ও production deployment এই implementation-এর বাইরে। Phase 02-এ refresh/session security, password recovery এবং configurable SMTP/provider validation যোগ হয়েছে; live SMTP, SMS, Google ও Apple verification বাকি। কোনো tax rule যোগ করা হয়নি।
