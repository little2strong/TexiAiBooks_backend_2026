"""Pure MTD status engine: no database or web code, so every rule is unit-testable.

Inputs are stored yearly figures and the threshold table. PAYE, dividends and
pensions never reach this module; qualifying income is gross trade plus gross rent.
"""
from datetime import date

UPCOMING, MANDATED, NOT_REQUIRED = "upcoming", "mandated", "not_required"
NEAR_THRESHOLD_PERCENT = 90


def qualifying_pence(figure):
    return (figure.get("gross_se_income_pence") or 0) + (figure.get("gross_other_se_income_pence") or 0) + \
        (figure.get("gross_property_income_pence") or 0)


def annualised(amount, year, trade_start):
    # A part-year new trade is scaled to twelve months for the threshold test only.
    start, end = year_dates(year)
    if not trade_start or not start < trade_start <= end:
        return amount
    return amount * ((end - start).days + 1) // ((end - trade_start).days + 1)


def year_dates(year):
    first = int(year[:4])
    return date(first, 4, 6), date(first + 1, 4, 5)


def start_date(mandation_year, accounting_date):
    first = int(mandation_year[:4])
    return date(first, 4, 1) if accounting_date == "03-31" else date(first, 4, 6)


def next_year(year):
    first = int(year[:4]) + 1
    return f"{first}-{(first + 1) % 100:02d}"


def years_below(history, thresholds, mandating_year, trade_start):
    """Consecutive most-recent years at or below the threshold after mandation."""
    table = {row["test_year"]: row["threshold_pence"] for row in thresholds}
    latest_threshold = sorted(thresholds, key=lambda row: row["test_year"])[-1]["threshold_pence"]
    count, year = 0, next_year(mandating_year)
    while year in history:
        limit = table.get(year, latest_threshold)
        if annualised(qualifying_pence(history[year]), year, trade_start) > limit:
            count = 0
        else:
            count += 1
        year = next_year(year)
    return count


def evaluate(history, thresholds, today, accounting_date=None, trade_start=None,
             exempt=False, voluntary=False, ceased_on=None, exited=False):
    """Return status, start date, confidence and a plain reason from stored figures."""
    result = {"status": "unknown", "start_date": None, "confidence": None, "years_below_count": 0,
              "test_year": None, "threshold_pence": None, "qualifying_income_pence": None, "near_threshold": False,
              "reason": "Add last year's figures to check if MTD applies to you."}
    if exempt:
        return {**result, "status": "exempt", "confidence": "confirmed", "reason": "An accountant confirmed an exemption from MTD."}
    if ceased_on:
        return {**result, "status": "ceased", "confidence": "confirmed", "reason": f"Self-employment stopped on {ceased_on}. MTD ends after the final update."}
    rows = sorted(thresholds, key=lambda row: row["test_year"])
    known = [row for row in rows if row["test_year"] in history]
    if not known:
        return result
    for row in known:
        amount = annualised(qualifying_pence(history[row["test_year"]]), row["test_year"], trade_start)
        if amount > row["threshold_pence"]:
            start = start_date(row["mandation_tax_year"], accounting_date)
            below = years_below(history, thresholds, row["test_year"], trade_start)
            filed = history[row["test_year"]].get("source") == "filed"
            base = {**result, "start_date": start, "test_year": row["test_year"], "threshold_pence": row["threshold_pence"],
                    "qualifying_income_pence": amount, "years_below_count": below, "confidence": "confirmed" if filed else "provisional"}
            if exited or below >= 3:
                return {**base, "status": NOT_REQUIRED if exited else "exit_eligible",
                        "reason": "Qualifying income has been at or below the threshold for three years in a row."}
            if start > today:
                return {**base, "status": UPCOMING, "reason": f"Takings before costs were over the threshold in {row['test_year']}, so MTD starts on {start}."}
            return {**base, "status": MANDATED, "reason": f"Takings before costs were over the threshold in {row['test_year']}, so MTD has applied since {start}."}
    last = known[-1]
    amount = annualised(qualifying_pence(history[last["test_year"]]), last["test_year"], trade_start)
    near = amount * 100 >= last["threshold_pence"] * NEAR_THRESHOLD_PERCENT
    confidence = "confirmed" if all(history[row["test_year"]].get("source") == "filed" for row in known) else "provisional"
    base = {**result, "test_year": last["test_year"], "threshold_pence": last["threshold_pence"], "qualifying_income_pence": amount,
            "near_threshold": near, "confidence": confidence}
    if voluntary:
        return {**base, "status": "voluntary", "start_date": today, "reason": "You chose to join MTD early."}
    return {**base, "status": NOT_REQUIRED, "reason": f"Takings before costs were not over the threshold in {last['test_year']}. PAYE wages do not count."}


def quarters(year):
    first = int(year[:4])
    return [{"id": f"{year}:q{index + 1}", "period_start": start, "period_end": end, "due_on": due} for index, (start, end, due) in enumerate((
        (date(first, 4, 6), date(first, 7, 5), date(first, 8, 7)),
        (date(first, 7, 6), date(first, 10, 5), date(first, 11, 7)),
        (date(first, 10, 6), date(first + 1, 1, 5), date(first + 1, 2, 7)),
        (date(first + 1, 1, 6), date(first + 1, 4, 5), date(first + 1, 5, 7))))]
