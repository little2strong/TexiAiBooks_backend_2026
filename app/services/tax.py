"""Versioned estimate rules, verified against official sources on 2026-10-27.

These estimates use pence rounding per band, not HMRC return-box rounding.
Unsupported relief/NI contexts are disclosed and never presented as assessments.
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.models.books import Profile
from app.models.common import utc_now
from app.services.books import digest, pence, profile, tax_dates, wire
from app.services.ledger import mileage_deduction, totals

VERIFIED_AT = "2026-10-27T00:00:00Z"
RULE_VERSION = "2026-10-27.1"
STUDENT_LOAN_THRESHOLDS = {"plan1": 2690000, "plan2": 2938500, "plan4": 3379500, "plan5": 2500000, "postgraduate": 2100000}
STUDENT_LOAN_RATES = {"undergraduate": "0.09", "postgraduate": "0.06"}
SOURCES = {
    "income": "https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past",
    "scotland": "https://www.mygov.scot/scottish-income-tax/current-income-tax-rates",
    "class4": "https://www.gov.uk/self-employed-national-insurance-rates",
    "mileage": "https://www.gov.uk/simpler-income-tax-simplified-expenses/vehicles",
    "poa": "https://www.gov.uk/understand-self-assessment-bill/payments-on-account",
    "trading": "https://www.gov.uk/guidance/tax-free-allowances-on-property-and-trading-income",
    "savings": "https://www.gov.uk/apply-tax-free-interest-on-savings",
    "student_loans": "https://www.gov.uk/guidance/tell-hmrc-about-a-student-loan-in-your-tax-return",
    "marriage": "https://www.gov.uk/marriage-allowance",
}


def today():
    return utc_now().astimezone(ZoneInfo("Europe/London")).date()


def rule_set(year, region):
    start, end = tax_dates(year)
    if year not in {"2025-26", "2026-27"} or region not in {"england_wales_ni", "scotland"}:
        raise HTTPException(422, "Rules not verified for this tax year and region")
    return {"id": str(uuid5(NAMESPACE_URL, f"taxiaibooks:rules:{year}:{region}:{RULE_VERSION}")),
        "tax_year": year, "region": region, "version": RULE_VERSION,
        "rules": [{"code": name, "value": value, "effective_from": start.isoformat(), "effective_to": end.isoformat(),
                   "official_url": SOURCES[name], "verified_at": VERIFIED_AT} for name, value in {
            "income": {"personal_allowance_pence": 1257000, "taper_from_pence": 10000000,
                       "bands": bands(year, region)},
            "class4": {"lower_pence": 1257000, "upper_pence": 5027000, "rates": ["0.06", "0.02"],
                       "class2_compulsory_pence": 0},
            "mileage": {"first_band_miles": "10000.00", "first_rate_pence": 55 if year == "2026-27" else 45,
                        "remaining_rate_pence": 25, "motorcycle_rate_pence": 24},
            "trading": {"allowance_pence": 100000, "eligibility_declaration_required": True},
            "poa": {"minimum_bill_pence": 100000, "outside_sa_exemption_percent": "80"},
            "savings": {"starting_rate_max_pence": 500000,"basic_psa_pence":100000,"higher_psa_pence":50000},
            "student_loans": {"single_plan_only":True,"unearned_income_inclusion_threshold_pence":200000,
                "verified_plan_tax_year": "2026-27", "thresholds_pence": STUDENT_LOAN_THRESHOLDS, "rates": STUDENT_LOAN_RATES},
            "marriage": {"transfer_pence":126000,"recipient_reduction_pence":25200,"declaration_required":True},
        }.items()]}


def bands(year, region):
    # Endpoints are cumulative TAXABLE income, after actual tapered allowance.
    if region == "england_wales_ni":
        return [(3770000, "0.20"), (12514000, "0.40"), (None, "0.45")]
    first, second = (396700, 1695600) if year == "2026-27" else (282700, 1492100)
    return [(first, "0.19"), (second, "0.20"), (3109200, "0.21"),
            (6243000, "0.42"), (12514000, "0.45"), (None, "0.48")]


def band_tax(taxable, year, region, allowance):
    result, lower = [], 0
    for index, (upper, rate) in enumerate(bands(year, region)):
        # Additional/top rate starts at total income 125140, where PA is zero.
        if upper == 12514000:
            upper -= allowance
        amount = max(0, taxable - lower) if upper is None else max(0, min(taxable, upper) - lower)
        if amount:
            result.append({"label": f"band_{index + 1}", "base_pence": amount, "rate": rate,
                           "tax_pence": pence(Decimal(amount) * Decimal(rate))})
        if upper is None: break
        lower = upper
    return sum(row["tax_pence"] for row in result), result


def calculate(profit, context, year):
    rule_set(year, context["region"])
    employments = context.get("employments", [])
    pay = sum(e["gross_annual_pay_pence"] for e in employments)
    paid = sum(e["tax_paid_pence"] for e in employments)
    property_income = context.get("property_income_pence") or 0
    interest = context.get("interest_pence") or 0
    nonsavings = pay + max(0, profit) + property_income
    combined = nonsavings + interest
    allowance = max(0, 1257000 - max(0, combined - 10000000) // 2)
    marriage=context.get("marriage_allowance_status")
    if marriage not in {None,"none"} and not context.get("marriage_allowance_eligible"):
        raise HTTPException(422,"Marriage Allowance requires an explicit eligibility declaration")
    if marriage=="transferor":
        if combined>1257000: raise HTTPException(422,"Transferor estimate supports income up to the standard allowance only")
        allowance=max(0,allowance-126000)
    income_tax, details = band_tax(max(0, nonsavings - allowance), year, context["region"], allowance)
    remaining_pa=max(0,allowance-nonsavings)
    taxable_interest=max(0,interest-remaining_pa)
    starting_rate=max(0,500000-max(0,nonsavings-allowance))
    taxable_total=max(0,combined-allowance)
    psa=0 if combined>12514000 else 50000 if taxable_total>3770000 else 100000
    exempt_interest=min(taxable_interest,starting_rate+psa)
    taxable_interest-=exempt_interest
    # Nil-rate savings still occupy UK tax bands, including for Scottish residents.
    savings_position=max(0,nonsavings-allowance)+exempt_interest
    savings_tax=0
    for lower,upper,rate in [(0,3770000,Decimal(".20")),(3770000,12514000-allowance,Decimal(".40")),(12514000-allowance,None,Decimal(".45"))]:
        amount=max(0,savings_position+taxable_interest-max(lower,savings_position)) if upper is None else max(0,min(savings_position+taxable_interest,upper)-max(lower,savings_position))
        if amount:
            tax=pence(Decimal(amount)*rate)
            savings_tax+=tax
            details.append({"label":"savings","base_pence":amount,"rate":str(rate),"tax_pence":tax})
    income_tax+=savings_tax
    if marriage=="recipient":
        limit=4366200 if context["region"]=="scotland" else 5027000
        if combined>limit: raise HTTPException(422,"Recipient income exceeds supported Marriage Allowance eligibility")
        income_tax=max(0,income_tax-25200)
    class4 = pence(Decimal(max(0, min(profit, 5027000) - 1257000)) * Decimal("0.06") +
                   Decimal(max(0, profit - 5027000)) * Decimal("0.02"))
    if context.get("class4_exempt"): class4=0
    plan=context.get("student_loan_plan")
    loan=0
    if plan not in {None,"none"}:
        if year!="2026-27": raise HTTPException(422,"Student loan rules currently verified for 2026-27 only")
        thresholds=STUDENT_LOAN_THRESHOLDS
        loan_income=pay+max(0,profit)+(property_income+interest if property_income+interest>200000 else 0)
        rate=Decimal(STUDENT_LOAN_RATES["postgraduate" if plan=="postgraduate" else "undergraduate"])
        # SA student loan repayment is rounded down to whole GBP.
        loan=max(0,int(Decimal(max(0,loan_income-thresholds[plan]))*rate/100)*100-
                 sum(e.get("student_loan_paid_pence",0) for e in employments))
    return {"personal_allowance_pence": allowance, "allowance_used_elsewhere_pence": min(allowance, pay + property_income),
            "income_tax_pence": income_tax, "paye_tax_paid_pence": paid,
            "class4_pence": class4, "class2_pence": 0, "student_loan_pence":loan,"savings_tax_pence":savings_tax,
            "total_pence": max(0, income_tax + class4 - paid) + loan,
            "bands": details, "combined_income_pence": combined,
            "warnings": ["estimate_not_assessed_liability", "NI_assumes_working_age_no_special_exemptions",
                         "pension_Gift_Aid_losses_and_other_reliefs_not_modelled"] +
                        (["PAYE_and_Class4_annual_maximum_not_modelled"] if pay else [])}


def estimate(db, owner, year, as_of=None, override=None, deduction_method="expenses"):
    item = profile(db, owner, "tax", year)
    if not item:
        raise HTTPException(409, "Save tax profile inputs before requesting an estimate")
    start, end = tax_dates(year)
    as_of = as_of or min(today(), end)
    if not start <= as_of <= end:
        raise HTTPException(422, "as_of must be inside the tax year")
    values = override or totals(db, owner, year, as_of)
    deduction = values["deductible_expenses_pence"] if deduction_method == "expenses" else min(100000, values["income_pence"])
    profit = values["income_pence"] - deduction
    calculation = calculate(profit, item.data, year)
    rules = rule_set(year, item.data["region"])
    snapshot = [values, item.version, rules["id"], as_of.isoformat(), deduction_method]
    return {"id": str(uuid5(NAMESPACE_URL, digest(snapshot))), "tax_year": year, "as_of": as_of,
            "rule_set_id": rules["id"], "profile_version": item.version, "ledger_version": values["ledger_version"],
            "income_pence": values["income_pence"], "expense_deduction_pence": deduction, "profit_pence": profit,
            **calculation, "estimate_only": True, "deduction_method": deduction_method,
            "assumptions": ["GBP cash-basis sole trader; no VAT reclaim or capital allowances",
                            "PAYE inputs are annual; ledger is confirmed activity through as_of",
                            "Round each band to nearest penny, half up; not return-box rounding"]}


def forecast(db, owner, year, scenario="current_pace"):
    if scenario != "current_pace": raise HTTPException(422, "Unsupported forecast scenario")
    start, end = tax_dates(year)
    as_of = min(today(), end)
    if as_of < start: raise HTTPException(422, "No observation period yet")
    observed = (as_of - start).days + 1
    total_days = (end - start).days + 1
    values = totals(db, owner, year, as_of)
    multiplier = Decimal(total_days) / observed
    projected_income = pence(Decimal(values["income_pence"]) * multiplier)
    projected_miles = (Decimal(values["business_miles"]) * multiplier).quantize(Decimal("0.01"))
    # Project separately per vehicle to retain each vehicle's own band threshold.
    from app.models.books import Vehicle
    from app.services.books import rows
    mileage_claim = 0
    threshold_dates = []
    for vehicle in db.scalars(rows(db, Vehicle, owner)):
        actual = __import__("app.services.ledger", fromlist=["mileage_total"]).mileage_total(db, owner, year, vehicle.id, as_of)
        miles = Decimal(actual["business_miles"])
        if vehicle.claim_method == "mileage":
            mileage_claim += mileage_deduction(miles * multiplier, year, vehicle.licence_class)
            if miles > 0 and miles < 10000 and miles * multiplier >= 10000:
                threshold_dates.append(start + timedelta(days=int(Decimal(10000) * observed / miles)))
    other = pence(Decimal(values["deductible_expenses_pence"] - values["mileage_deduction_pence"]) * multiplier)
    projected = {**values, "income_pence": projected_income, "deductible_expenses_pence": other + mileage_claim}
    predicted = estimate(db, owner, year, as_of, projected)
    return {"estimate": predicted, "observed_days": observed, "projected_days": total_days,
            "projected_income_pence": projected_income, "projected_miles": str(projected_miles),
            "projected_mileage_deduction_pence": mileage_claim, "projected_other_expenses_pence": other,
            "threshold_date": min(threshold_dates) if threshold_dates else None,
            "weekly_saving_pence": pence(Decimal(predicted["total_pence"]) / 52), "scenario": scenario,
            "assumptions": ["Linear pace from 6 April through as_of; incomplete historic books distort projections",
                            "No seasonality; annual PAYE unchanged; each vehicle mileage band applied separately"]}


def deadlines(year):
    start, end = tax_dates(year)
    return [{"id": f"{year}:online", "label_key": "deadline.self_assessment", "due_on": date(end.year + 1, 1, 31),
             "tax_year": year, "type": "online_filing_and_balancing", "estimated": False, "amount_pence": None}]


def payment_timeline(db, owner, year):
    inputs = profile(db, owner, "prior_assessment", year)
    if not inputs:
        return {"items": deadlines(year), "prior_year_liability_pence": None, "advance_payments_pence": None,
                "adjustments_pence": None, "warnings": ["Prior assessed liability, outside-SA tax and payments required; no payment amount inferred"]}
    values = inputs.data
    bill = values["prior_year_liability_pence"]
    outside = values["tax_paid_outside_sa_pence"]
    eligible = bill >= 100000 and (outside * 100 <= (bill + outside) * 80)
    first = bill // 2 if eligible else 0
    second = bill - first if eligible else 0
    _, end = tax_dates(year)
    warnings=["Based on user-reported prior assessment, not an HMRC account balance",
              "Prior liability must exclude CGT and student loans; outside-SA exemption uses the supplied tax basis"]
    try:
        projected=forecast(db,owner,year)["estimate"]
        liability=projected["total_pence"]
        balancing=liability-values["advance_payments_pence"]+values["adjustments_pence"]
    except HTTPException:
        liability,balancing=None,None
        warnings.append("Current-year projection unavailable; balancing amount unknown")
    return {**values,"estimated_year_liability_pence":liability,"items": [{"id": year + ":poa1", "due_on": date(end.year, 1, 31), "amount_pence": first,
        "type": "payment_on_account", "estimated": True, "tax_year": year},
        {"id": year + ":poa2", "due_on": date(end.year, 7, 31), "amount_pence": second,
        "type": "payment_on_account", "estimated": True, "tax_year": year},
        {"id":year+":balance","due_on":date(end.year+1,1,31),"amount_pence":balancing,
         "type":"estimated_balancing_or_credit","estimated":True,"tax_year":year}],"warnings":warnings}
