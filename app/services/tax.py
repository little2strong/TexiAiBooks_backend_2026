"""Versioned estimate rules, verified against official sources on 2026-10-27.

These estimates use pence rounding per band, not HMRC return-box rounding.
Unsupported relief/NI contexts are disclosed and never presented as assessments.
The built-in registry is the verified baseline. Admin-activated tax_rates rows
overlay it, so a rate change is a data entry and a new year needs no deploy.
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.models.books import Profile, TaxAdjustment, TaxReturn
from app.models.common import utc_now
from app.models.staff import TaxRate
from app.services.books import digest, pence, profile, rows, tax_dates, tax_year, wire
from app.services.ledger import builtin_mileage, mileage_deduction, totals

VERIFIED_AT = "2026-10-27T00:00:00Z"
RULE_VERSION = "2026-10-27.1"
STUDENT_LOAN_THRESHOLDS = {"plan1": 2690000, "plan2": 2938500, "plan4": 3379500, "plan5": 2500000, "postgraduate": 2100000}
STUDENT_LOAN_RATES = {"undergraduate": "0.09", "postgraduate": "0.06"}
# Class 2: from HMRC's self-employed National Insurance rates, per tax year.
CLASS2 = {"2025-26": (684500, 350), "2026-27": (710500, 365)}
BUILTIN_YEARS = ("2025-26", "2026-27")
REGIONS = ("england_wales_ni", "scotland")
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
UK_SOURCES = {
    "mtd_threshold": "https://www.gov.uk/guidance/find-out-if-and-when-you-need-to-use-making-tax-digital-for-income-tax",
    "vat": "https://www.gov.uk/vat-registration/when-to-register",
}
# Test year -> threshold -> mandation year, from the Prior-Year spec. Editable through tax_rates.
MTD_THRESHOLDS = {"2024-25": (5000000, "2026-27"), "2025-26": (3000000, "2027-28"), "2026-27": (2000000, "2028-29")}
VAT_THRESHOLD_PENCE = 9000000
RULE_CODES = tuple(name for name in SOURCES if name != "scotland")


def today():
    return utc_now().astimezone(ZoneInfo("Europe/London")).date()


def builtin_values(year, region):
    spt, weekly = CLASS2[year]
    return {"income": {"personal_allowance_pence": 1257000, "taper_from_pence": 10000000, "bands": bands(year, region)},
        "class4": {"lower_pence": 1257000, "upper_pence": 5027000, "rates": ["0.06", "0.02"], "class2_compulsory_pence": 0,
                   "class2_small_profits_threshold_pence": spt, "class2_weekly_rate_pence": weekly},
        "mileage": builtin_mileage(year),
        "trading": {"allowance_pence": 100000, "eligibility_declaration_required": True},
        "poa": {"minimum_bill_pence": 100000, "outside_sa_exemption_percent": "80"},
        "savings": {"starting_rate_max_pence": 500000, "basic_psa_pence": 100000, "higher_psa_pence": 50000},
        "student_loans": {"single_plan_only": True, "unearned_income_inclusion_threshold_pence": 200000,
            "verified_plan_tax_year": "2026-27", "thresholds_pence": STUDENT_LOAN_THRESHOLDS, "rates": STUDENT_LOAN_RATES},
        "marriage": {"transfer_pence": 126000, "recipient_reduction_pence": 25200, "declaration_required": True}}


def active_rates(db, year, region):
    if db is None:
        return {}
    return {row.code: row for row in db.scalars(select(TaxRate).where(
        TaxRate.tax_year == year, TaxRate.region == region, TaxRate.status == "active"))}


def rule_set(year, region, db=None):
    start, end = tax_dates(year)
    overlay = active_rates(db, year, region) if region in REGIONS else {}
    known = year in BUILTIN_YEARS and region in REGIONS
    if not known and not (region in REGIONS and set(RULE_CODES) <= set(overlay)):
        raise HTTPException(422, "Rules not verified for this tax year and region")
    base = builtin_values(year, region) if known else {}
    version = RULE_VERSION if not overlay else RULE_VERSION + "+" + digest(sorted(f"{row.code}:{row.id}:{row.version}" for row in overlay.values()))[:12]
    rules = []
    for name in RULE_CODES:
        row = overlay.get(name)
        rules.append({"code": name, "value": row.value if row else base[name], "effective_from": start.isoformat(),
            "effective_to": end.isoformat(), "official_url": row.official_url if row else SOURCES[name],
            "verified_at": row.activated_at.isoformat() if row and row.activated_at else VERIFIED_AT, "managed": bool(row)})
    return {"id": str(uuid5(NAMESPACE_URL, f"taxiaibooks:rules:{year}:{region}:{version}")),
        "tax_year": year, "region": region, "version": version, "rules": rules}


def rule_values(rules):
    return {rule["code"]: rule["value"] for rule in rules["rules"]}


def supported_years(db):
    # A managed year becomes selectable only when every rule family is active.
    years = set(BUILTIN_YEARS)
    candidates = db.execute(select(TaxRate.tax_year, TaxRate.code).where(TaxRate.status == "active", TaxRate.region == "england_wales_ni"))
    found = {}
    for year, code in candidates:
        found.setdefault(year, set()).add(code)
    years |= {year for year, codes in found.items() if set(RULE_CODES) <= codes}
    return sorted(years)


def filing_year(day=None):
    """The tax year with the next filing deadline; the previous year until its 31 January."""
    day = day or today()
    current = tax_year(day)
    first = int(current[:4])
    previous = f"{first - 1}-{first % 100:02d}"
    return previous if day <= date(first + 1, 1, 31) else current


def mtd_thresholds(db):
    table = {year: {"test_year": year, "threshold_pence": threshold, "mandation_tax_year": mandation}
             for year, (threshold, mandation) in MTD_THRESHOLDS.items()}
    if db is not None:
        for row in db.scalars(select(TaxRate).where(TaxRate.code == "mtd_threshold", TaxRate.region == "uk", TaxRate.status == "active")):
            table[row.tax_year] = {"test_year": row.tax_year, **row.value}
    return list(table.values())


def vat_threshold(db, year):
    row = db.scalar(select(TaxRate).where(TaxRate.code == "vat", TaxRate.region == "uk", TaxRate.status == "active", TaxRate.tax_year == year))
    return row.value["threshold_pence"] if row else VAT_THRESHOLD_PENCE


def bands(year, region):
    # Endpoints are cumulative TAXABLE income, after actual tapered allowance.
    if region == "england_wales_ni":
        return [(3770000, "0.20"), (12514000, "0.40"), (None, "0.45")]
    first, second = (396700, 1695600) if year == "2026-27" else (282700, 1492100)
    return [(first, "0.19"), (second, "0.20"), (3109200, "0.21"),
            (6243000, "0.42"), (12514000, "0.45"), (None, "0.48")]


def band_tax(taxable, band_rows, allowance):
    result, lower = [], 0
    for index, (upper, rate) in enumerate(band_rows):
        # The top band starts at total income where the allowance is fully tapered.
        if index == len(band_rows) - 2:
            upper -= allowance
        amount = max(0, taxable - lower) if upper is None else max(0, min(taxable, upper) - lower)
        if amount:
            result.append({"label": f"band_{index + 1}", "base_pence": amount, "rate": rate,
                           "tax_pence": pence(Decimal(amount) * Decimal(rate))})
        if upper is None: break
        lower = upper
    return sum(row["tax_pence"] for row in result), result


def class2_position(profit, class4):
    threshold = class4.get("class2_small_profits_threshold_pence")
    if threshold is None:
        return {"class2_status": "unknown", "class2_weekly_rate_pence": None, "class2_small_profits_threshold_pence": None}
    return {"class2_status": "credited" if profit >= threshold else "voluntary", "class2_weekly_rate_pence": class4["class2_weekly_rate_pence"],
            "class2_small_profits_threshold_pence": threshold}


def calculate(profit, context, year, rules=None):
    values = rule_values(rules or rule_set(year, context["region"]))
    income_rules, class4_rules = values["income"], values["class4"]
    employments = context.get("employments", [])
    pay = sum(e["gross_annual_pay_pence"] for e in employments)
    paid = sum(e["tax_paid_pence"] for e in employments)
    property_income = context.get("property_income_pence") or 0
    interest = context.get("interest_pence") or 0
    nonsavings = pay + max(0, profit) + property_income
    combined = nonsavings + interest
    allowance = max(0, income_rules["personal_allowance_pence"] - max(0, combined - income_rules["taper_from_pence"]) // 2)
    marriage=context.get("marriage_allowance_status")
    if marriage not in {None,"none"} and not context.get("marriage_allowance_eligible"):
        raise HTTPException(422,"Marriage Allowance requires an explicit eligibility declaration")
    if marriage=="transferor":
        if combined>1257000: raise HTTPException(422,"Transferor estimate supports income up to the standard allowance only")
        allowance=max(0,allowance-126000)
    income_tax, details = band_tax(max(0, nonsavings - allowance), income_rules["bands"], allowance)
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
    lower, upper = class4_rules["lower_pence"], class4_rules["upper_pence"]
    main_rate, top_rate = (Decimal(rate) for rate in class4_rules["rates"])
    class4 = pence(Decimal(max(0, min(profit, upper) - lower)) * main_rate + Decimal(max(0, profit - upper)) * top_rate)
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
            "class4_pence": class4, "class2_pence": 0, **class2_position(profit, class4_rules),
            "student_loan_pence":loan,"savings_tax_pence":savings_tax,
            "total_pence": max(0, income_tax + class4 - paid) + loan,
            "bands": details, "combined_income_pence": combined,
            "warnings": ["estimate_not_assessed_liability", "NI_assumes_working_age_no_special_exemptions",
                         "pension_Gift_Aid_losses_and_other_reliefs_not_modelled"] +
                        (["PAYE_and_Class4_annual_maximum_not_modelled"] if pay else [])}


def active_adjustments(db, owner, year):
    return list(db.scalars(rows(db, TaxAdjustment, owner).where(TaxAdjustment.tax_year == year, TaxAdjustment.voided_at.is_(None))))


def adjustment_totals(records):
    income = sum(row.amount_pence for row in records if row.target == "income")
    expense = sum(row.amount_pence for row in records if row.target == "expenses")
    allowances = sum(row.amount_pence for row in records if row.target == "capital_allowances")
    return income, expense, allowances


def filed_return(db, owner, year):
    return db.scalar(rows(db, TaxReturn, owner).where(TaxReturn.tax_year == year, TaxReturn.status == "filed"))


def estimate(db, owner, year, as_of=None, override=None, deduction_method="expenses"):
    # A filed year is one frozen calculation. New rates must never change it.
    if as_of is None and override is None and deduction_method == "expenses":
        filed = filed_return(db, owner, year)
        if filed and filed.snapshot:
            return {**filed.snapshot["estimate"], "frozen": True, "filing_reference": filed.filing_reference}
    item = profile(db, owner, "tax", year)
    if not item:
        raise HTTPException(409, "Save tax profile inputs before requesting an estimate")
    start, end = tax_dates(year)
    as_of = as_of or min(today(), end)
    if not start <= as_of <= end:
        raise HTTPException(422, "as_of must be inside the tax year")
    values = override or totals(db, owner, year, as_of)
    rules = rule_set(year, item.data["region"], db)
    records = active_adjustments(db, owner, year)
    income_adjustment, expense_adjustment, allowances = adjustment_totals(records)
    income = values["income_pence"] + income_adjustment
    allowance = rule_values(rules)["trading"]["allowance_pence"]
    # The Trading Allowance replaces expenses, mileage and capital allowances alike.
    deduction = values["deductible_expenses_pence"] + expense_adjustment + allowances if deduction_method == "expenses" else min(allowance, income)
    profit = income - deduction
    calculation = calculate(profit, item.data, year, rules)
    snapshot = [values, item.version, rules["id"], as_of.isoformat(), deduction_method, [[str(row.id), row.version] for row in records]]
    return {"id": str(uuid5(NAMESPACE_URL, digest(snapshot))), "tax_year": year, "as_of": as_of,
            "rule_set_id": rules["id"], "profile_version": item.version, "ledger_version": values["ledger_version"],
            "income_pence": income, "expense_deduction_pence": deduction, "profit_pence": profit,
            "adjustment_income_pence": income_adjustment, "adjustment_expenses_pence": expense_adjustment,
            "adjustment_capital_allowances_pence": allowances, "frozen": False,
            **calculation, "estimate_only": True, "deduction_method": deduction_method,
            "assumptions": ["GBP cash-basis sole trader; no VAT reclaim. Capital allowances appear only as accountant adjustments",
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
    from app.services.ledger import eligible_miles, mileage_rates
    car_miles, motorcycle_miles = eligible_miles(db, owner, year, as_of)
    rates = mileage_rates(db, owner, year)
    mileage_claim = mileage_deduction(car_miles * multiplier, year, rates=rates) + mileage_deduction(motorcycle_miles * multiplier, year, "motorcycle", rates=rates)
    threshold_dates = []
    # The 10,000-mile band is per person across simplified vehicles, so project the total.
    if 0 < car_miles < 10000 and car_miles * multiplier >= 10000:
        threshold_dates.append(start + timedelta(days=int(Decimal(10000) * observed / car_miles)))
    other = pence(Decimal(values["deductible_expenses_pence"] - values["mileage_deduction_pence"]) * multiplier)
    projected = {**values, "income_pence": projected_income, "deductible_expenses_pence": other + mileage_claim}
    predicted = estimate(db, owner, year, as_of, projected)
    return {"estimate": predicted, "observed_days": observed, "projected_days": total_days,
            "projected_income_pence": projected_income, "projected_miles": str(projected_miles),
            "projected_mileage_deduction_pence": mileage_claim, "projected_other_expenses_pence": other,
            "threshold_date": min(threshold_dates) if threshold_dates else None,
            "weekly_saving_pence": pence(Decimal(predicted["total_pence"]) / 52), "scenario": scenario,
            "assumptions": ["Linear pace from 6 April through as_of; incomplete historic books distort projections",
                            "No seasonality; annual PAYE unchanged; mileage band applied across all simplified vehicles"]}


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
