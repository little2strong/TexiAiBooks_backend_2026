"""Required engine and MTD cases from the Developer Build Spec and Prior-Year spec."""
from datetime import date
from decimal import Decimal

from app.services.ledger import mileage_deduction
from app.services.mtd_status import evaluate, quarters
from app.services.tax import MTD_THRESHOLDS, calculate

BASE = {"region": "england_wales_ni", "employments": []}
THRESHOLDS = [{"test_year": year, "threshold_pence": limit, "mandation_tax_year": start} for year, (limit, start) in MTD_THRESHOLDS.items()]
TODAY = date(2026, 11, 1)


def employed(pay, paid):
    return {**BASE, "employments": [{"gross_annual_pay_pence": pay, "tax_paid_pence": paid}]}


def history(**figures):
    return {year.replace("y", "").replace("_", "-"): {"gross_se_income_pence": amount, "source": "filed"} for year, amount in figures.items()}


def test_ali_khan_paye_and_driving_profit():
    # PAYE 20,000 with tax of (20,000 - 12,570) x 20% = 1,486 already deducted.
    result = calculate(1245000, employed(2000000, 148600), "2026-27")
    assert result["total_pence"] == 249000
    assert result["class4_pence"] == 0


def test_class4_boundary_is_charged_only_above_the_lower_limit():
    assert calculate(1257000, BASE, "2026-27")["class4_pence"] == 0
    assert calculate(1257100, BASE, "2026-27")["class4_pence"] == 6


def test_personal_allowance_tapers_above_100k():
    assert calculate(11000000, BASE, "2026-27")["personal_allowance_pence"] == 757000


def test_scottish_taxpayer_uses_scottish_bands():
    scottish = calculate(4000000, {**BASE, "region": "scotland"}, "2026-27")
    assert {row["rate"] for row in scottish["bands"]} >= {"0.19", "0.20", "0.21"}
    assert scottish["income_tax_pence"] != calculate(4000000, BASE, "2026-27")["income_tax_pence"]


def test_class2_is_credited_at_the_threshold_and_voluntary_below():
    assert calculate(710500, BASE, "2026-27")["class2_status"] == "credited"
    below = calculate(710499, BASE, "2026-27")
    assert below["class2_status"] == "voluntary"
    assert below["class2_weekly_rate_pence"] == 365
    assert below["class2_pence"] == 0


def test_mileage_first_band_uses_each_years_published_rate():
    # 45p to 2025-26 and 55p from 6 April 2026, per gov.uk simplified expenses.
    assert mileage_deduction(Decimal(11000), "2025-26") == 475000
    assert mileage_deduction(Decimal(11000), "2026-27") == 575000


def test_mtd_ali_is_not_required_and_paye_is_never_counted():
    result = evaluate({"2024-25": {"gross_se_income_pence": 1245000, "paye_income_pence": 2000000, "source": "filed"},
        "2025-26": {"gross_se_income_pence": 1245000, "paye_income_pence": 2000000, "source": "filed"}}, THRESHOLDS, TODAY)
    assert result["status"] == "not_required"
    assert result["qualifying_income_pence"] == 1245000


def test_mtd_mohammed_counts_rent_and_is_mandated_since_april_2026():
    result = evaluate({"2024-25": {"gross_se_income_pence": 4500000, "gross_property_income_pence": 600000, "source": "filed"}}, THRESHOLDS, TODAY)
    assert result["status"] == "mandated"
    assert result["start_date"] == date(2026, 4, 6)
    assert result["confidence"] == "confirmed"


def test_mtd_threshold_means_more_than():
    assert evaluate(history(y2025_26=3000100), THRESHOLDS, TODAY)["status"] == "upcoming"
    assert evaluate(history(y2025_26=3000100), THRESHOLDS, TODAY)["start_date"] == date(2027, 4, 6)
    assert evaluate(history(y2025_26=3000000), THRESHOLDS, TODAY)["status"] == "not_required"


def test_mtd_march_accounting_date_moves_the_start():
    assert evaluate(history(y2025_26=3000100), THRESHOLDS, TODAY, "03-31")["start_date"] == date(2027, 4, 1)


def test_mtd_threshold_config_changes_the_result_without_code():
    raised = [{**row, "threshold_pence": 4000000} if row["test_year"] == "2025-26" else row for row in THRESHOLDS]
    assert evaluate(history(y2025_26=3500000), raised, TODAY)["status"] == "not_required"
    assert evaluate(history(y2025_26=3500000), THRESHOLDS, TODAY)["status"] == "upcoming"


def test_mtd_exit_needs_three_consecutive_years_below():
    figures = {"2024-25": {"gross_se_income_pence": 6000000, "source": "filed"}, "2025-26": {"gross_se_income_pence": 1000000, "source": "filed"},
               "2026-27": {"gross_se_income_pence": 1000000, "source": "filed"}}
    two = evaluate(figures, THRESHOLDS, date(2028, 6, 1))
    assert (two["status"], two["years_below_count"]) == ("mandated", 2)
    three = evaluate({**figures, "2027-28": {"gross_se_income_pence": 1000000, "source": "filed"}}, THRESHOLDS, date(2029, 6, 1))
    assert three["status"] == "exit_eligible"


def test_mtd_unknown_without_figures_and_provisional_from_estimates():
    assert evaluate({}, THRESHOLDS, TODAY)["status"] == "unknown"
    estimated = evaluate({"2024-25": {"gross_se_income_pence": 6000000, "source": "estimate"}}, THRESHOLDS, TODAY)
    assert estimated["confidence"] == "provisional"


def test_mtd_part_year_new_trade_is_annualised_for_the_test():
    started = date(2025, 10, 6)
    # 16,000 over half a year is about 32,000 for a full year, so over the 30,000 test.
    assert evaluate(history(y2025_26=1600000), THRESHOLDS, TODAY, None, started)["status"] == "upcoming"
    assert evaluate(history(y2025_26=1600000), THRESHOLDS, TODAY)["status"] == "not_required"


def test_mtd_near_threshold_warning():
    assert evaluate(history(y2026_27=1900000), THRESHOLDS, TODAY)["near_threshold"] is True
    assert evaluate(history(y2026_27=1000000), THRESHOLDS, TODAY)["near_threshold"] is False


def test_mtd_quarter_dates():
    assert [item["due_on"] for item in quarters("2026-27")] == [date(2026, 8, 7), date(2026, 11, 7), date(2027, 2, 7), date(2027, 5, 7)]
