from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.models.books import Profile, Vehicle
from app.models import User
from app.schemas.books import (DriverInput, MePatch, OnboardingPatch, Preferences,
                               SourcesInput, TaxProfileInput)
from app.services.books import (CATEGORIES, SOURCES, check_version, history, owned,
                                primary_business, profile, rows, tax_dates, wire, write)
from app.services.vault import decrypt, encrypt
from app.schemas.results import MeRead

router = APIRouter(tags=["profiles"])
Key = Annotated[UUID, Header(alias="Idempotency-Key")]
DEFAULT_ME = {"first_name": None, "last_name": None, "preferences": Preferences().model_dump()}
DEFAULT_ONBOARDING = {"current_step": 1, "completed_steps": [], "skipped_fields": [], "completed_at": None}


def me_response(db, user):
    item = profile(db, user.id, "me")
    data = item.data if item else DEFAULT_ME
    onboarding = profile(db, user.id, "onboarding")
    return {"id": user.id, **data, "locale": data["preferences"]["locale"],
            "timezone": data["preferences"]["timezone"], "phone_masked": None,
            "email_masked": (user.email[:1] + "***@" + user.email.split("@")[-1]) if user.email else None,
            "onboarding_complete": bool(onboarding and onboarding.data.get("completed_at")),
            "version": item.version if item else 1, "created_at": user.created_at}


@router.get("/me", operation_id="A06",response_model=MeRead)
def me(user: CurrentUser, db: SessionDep):
    return me_response(db, user)


@router.patch("/me", operation_id="P01",response_model=MeRead)
def patch_me(data: MePatch, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        item = profile(db, user.id, "me", default=DEFAULT_ME, create=True)
        check_version(item, data.expected_version)
        before = wire(item)
        values = dict(item.data)
        changes = data.model_dump(exclude_unset=True, exclude={"expected_version", "preferences"})
        values.update(changes)
        if data.preferences:
            values["preferences"] = {**values["preferences"], **data.preferences.model_dump(exclude_unset=True)}
        item.data = values
        item.version += 1
        history(db, item, "profile", before)
        return me_response(db, user)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.get("/me/onboarding", operation_id="P02")
def onboarding(user: CurrentUser, db: SessionDep):
    item = profile(db, user.id, "onboarding")
    return {**(item.data if item else DEFAULT_ONBOARDING), "version": item.version if item else 1}


@router.patch("/me/onboarding", operation_id="P03")
def patch_onboarding(data: OnboardingPatch, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        from app.models.common import utc_now
        item = profile(db, user.id, "onboarding", default=DEFAULT_ONBOARDING, create=True)
        check_version(item, data.expected_version)
        values = {**item.data, **data.model_dump(exclude_unset=True, exclude={"expected_version", "complete"})}
        if any(values.get(name) is None for name in ("current_step", "completed_steps", "skipped_fields")):
            raise HTTPException(422, "Progress fields cannot be null")
        if data.complete:
            driver = profile(db, user.id, "driver")
            vehicles = list(db.scalars(rows(db, Vehicle, user.id).where(Vehicle.active.is_(True))))
            if not driver or not vehicles or any(v.claim_method == "unset" for v in vehicles):
                raise HTTPException(409, "Save driver profile, vehicle and claim election before completion")
            if not db.scalar(rows(db, Profile, user.id).where(Profile.kind == "tax")):
                raise HTTPException(409, "Save tax context before completion")
            values["completed_at"] = utc_now().isoformat()
        before = wire(item)
        item.data = values
        item.version += 1
        history(db, item, "onboarding", before)
        return {**item.data, "version": item.version}
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.get("/me/driver-profile", operation_id="P04")
def driver_profile(user: CurrentUser, db: SessionDep):
    item = profile(db, user.id, "driver")
    if not item:
        raise HTTPException(404, "Driver profile not set")
    names = me_response(db, user)
    return {**item.data, "first_name": names["first_name"], "last_name": names["last_name"], "version": item.version}


@router.put("/me/driver-profile", operation_id="P05")
def put_driver(data: DriverInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        item = profile(db, user.id, "driver")
        if item:
            check_version(item, data.expected_version)
            if data.licence_type!=item.data["licence_type"] and db.scalar(rows(db,Vehicle,user.id).where(Vehicle.method_locked.is_(True))):
                raise HTTPException(409,"Claimed mileage history requires specialist review before changing licence context")
            item.version += 1
        else:
            if data.expected_version is not None:
                raise HTTPException(409, "Profile does not exist")
            item = profile(db, user.id, "driver", create=True)
        business = primary_business(db, user.id)
        item.data = {**data.model_dump(mode="json", exclude={"expected_version", "first_name", "last_name"}),
                     "primary_business_id": str(business.id)}
        if {"first_name", "last_name"} & data.model_fields_set:
            names = profile(db, user.id, "me", default=DEFAULT_ME, create=True)
            names.data = {**names.data, **data.model_dump(include={"first_name", "last_name"}, exclude_unset=True)}
            names.version += 1
        history(db, item, "driver")
        return driver_profile(user, db)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


def tax_profile_response(item):
    return {**item.data, "version": item.version}


@router.get("/me/tax-profile", operation_id="P06")
def tax_profile(tax_year: str, user: CurrentUser, db: SessionDep):
    tax_dates(tax_year)
    item = profile(db, user.id, "tax", tax_year)
    if not item:
        raise HTTPException(404, "Tax profile not set")
    return tax_profile_response(item)


@router.put("/me/tax-profile", operation_id="P07")
def put_tax_profile(data: TaxProfileInput, user: CurrentUser, db: SessionDep, settings: SettingsDep,
                    request: Request, key: Key):
    def apply():
        tax_dates(data.tax_year)
        item = profile(db, user.id, "tax", data.tax_year)
        if item:
            check_version(item, data.expected_version)
            item.version += 1
        else:
            if data.expected_version is not None:
                raise HTTPException(409, "Profile does not exist")
            item = profile(db, user.id, "tax", data.tax_year, create=True)
        identifiers = decrypt(settings, item.identifiers) if item.identifiers else {}
        for name in ("utr", "ni_number"):
            if name in data.model_fields_set:
                value = getattr(data, name)
                identifiers[name] = value.get_secret_value() if value else None
        if any(identifiers.values()):
            item.identifiers = encrypt(settings, identifiers)
        else:
            item.identifiers = None
        item.data = {**data.model_dump(mode="json", exclude={"utr", "ni_number", "expected_version"}),
                     "utr_masked": "******" + identifiers["utr"][-4:] if identifiers.get("utr") else None,
                     "ni_masked": "*****" + identifiers["ni_number"][-4:] if identifiers.get("ni_number") else None,
                     "identifiers_complete": bool(identifiers.get("utr") and identifiers.get("ni_number"))}
        history(db, item, "tax_profile")
        return tax_profile_response(item)
    # Hash secrets in the request fingerprint; never cache raw identifiers.
    from app.services.books import digest
    payload = data.model_dump(mode="json", exclude={"utr", "ni_number"})
    for name in ("utr", "ni_number"):
        if name in data.model_fields_set:
            value = getattr(data, name)
            from app.core.security import hash_secret
            payload[name] = hash_secret("identifier:" + value.get_secret_value(), settings) if value else None
    return write(db, user, request, key, payload, apply)


@router.get("/me/income-sources", operation_id="I01")
def sources(user: CurrentUser, db: SessionDep):
    item = profile(db, user.id, "sources")
    return [SOURCES[UUID(value)] for value in item.data.get("source_ids", [])] if item else []


@router.put("/me/income-sources", operation_id="I02")
def put_sources(data: SourcesInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        if any(value not in SOURCES for value in data.source_ids):
            raise HTTPException(422, "Unknown income source")
        item = profile(db, user.id, "sources", create=True)
        item.data = {"source_ids": sorted(set(map(str, data.source_ids)))}
        item.version += 1
        return sources(user, db)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.get("/reference-data", operation_id="F01")
def references(settings: SettingsDep, locale: str = "en"):
    if locale not in {"en", "ur", "bn", "pa", "pl", "ro", "ar"}:
        raise HTTPException(422, "Unsupported locale")
    languages = [("en", "English", "English", False), ("ur", "اردو", "Urdu", True),
                 ("bn", "বাংলা", "Bengali", False), ("pa", "ਪੰਜਾਬੀ", "Punjabi", False),
                 ("pl", "Polski", "Polish", False), ("ar", "العربية", "Arabic", True), ("ro", "Română", "Romanian", False)]
    return {"version": "2026-10-27.1", "vehicle_claim_acknowledgement_version":"hmrc-2026-10-27",
            "languages": [{"code": c, "native": n, "english": e, "rtl": r} for c,n,e,r in languages],
            "councils": [], "council_entry": "manual_code", "licence_types": ["private_hire", "hackney"],
            "sources": list(SOURCES.values()), "categories": list(CATEGORIES.values()),
            "upload_limits": {"max_bytes": settings.upload_max_bytes,
                              "mime_types": ["image/jpeg", "image/png", "application/pdf", "text/csv"]}}


@router.get("/capabilities")
def capabilities(user: CurrentUser,request: Request,settings: SettingsDep):
    return {"supported_tax_years":["2025-26","2026-27"],"statement_formats":["canonical-csv-v1"],
        "statement_native_pdf":False,"manual_receipt_review":True,"exports":["csv","pdf","zip_with_photos"],
        "sms_configured":bool(request.app.state.sms_delivery.enabled),
        "identifier_encryption_configured":bool(settings.identifier_encryption_keys),
        "scanner_configured":bool(settings.clamav_host),
        "vehicle_lookup_configured":getattr(request.app.state,"vehicle_lookup",None) is not None,
        "billing_configured":getattr(request.app.state,"billing_provider",None) is not None,
        "hmrc_configured":getattr(request.app.state,"hmrc_provider",None) is not None,
        "assistant_configured":getattr(request.app.state,"assistant_provider",None) is not None,
        "approved_subscription_offers_configured":bool(settings.subscription_plans)}
