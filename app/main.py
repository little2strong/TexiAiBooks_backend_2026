from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api import auth, expenses, health, users, profiles, ledger, reports, documents, reconciliation, support, integrations, phone_auth
from app.core.config import Settings, get_settings
from app.db import build_engine
from app.services.delivery import DisabledSMS, SMTPResetDelivery
from app.services.identity import IdentityVerifier
from app.core.limits import BodyLimitMiddleware


def create_app(
    settings: Settings | None = None, session_factory: sessionmaker[Session] | None = None
) -> FastAPI:
    settings = settings or get_settings()
    engine = build_engine(settings) if session_factory is None else None
    if session_factory is None:
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        if engine is not None:
            engine.dispose()

    application = FastAPI(title="TexiAiBooks API", version="0.1.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.session_factory = session_factory
    application.state.reset_delivery = SMTPResetDelivery(settings)
    application.state.sms_delivery = DisabledSMS()
    application.state.identity_verifier = IdentityVerifier(settings)
    application.state.billing_provider = None
    application.state.hmrc_provider = None
    application.state.assistant_provider = None
    application.add_middleware(BodyLimitMiddleware,max_bytes=settings.upload_max_bytes+65536)

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/v1") and request.url.path not in {"/api/v1/reference-data", "/api/v1/subscription-plans"}:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response
    application.include_router(health.router)
    for router in (auth.router, users.router, expenses.router, profiles.router, ledger.router,
                   reports.router, documents.router, reconciliation.router, support.router,
                   integrations.router, phone_auth.router):
        application.include_router(router, prefix="/api/v1")

    @application.exception_handler(OperationalError)
    def unavailable(request: Request, exc: OperationalError):
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @application.exception_handler(IntegrityError)
    def conflict(request: Request, exc: IntegrityError):
        return JSONResponse(status_code=409,content={"detail":"The operation conflicts with an existing record or constraint"})

    @application.exception_handler(RequestValidationError)
    def invalid_request(request: Request, exc: RequestValidationError):
        # Pydantic's default errors can echo passwords/raw request input.
        errors = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    return application


app = create_app()

