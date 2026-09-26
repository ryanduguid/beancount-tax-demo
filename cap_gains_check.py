"""Classify ordinary purchased investment property without calculating tax due."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext

RULES = {"schema": "ordinary-us-capital-gains-v1", "holding_period": "more_than_calendar_year",
         "scope": "individual_ordinary_investment_property"}


def money(value):
    with localcontext() as context:
        context.prec = 80
        return f"USD {value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def check(gain: dict, oa_skill: dict) -> dict:
    base = {"oa_skill": oa_skill.get("slug"), "oa_skill_name": oa_skill.get("name"),
            "provenance": oa_skill.get("provenance", "unverified"),
            "reported_metadata": {key: oa_skill.get(key) for key in ("tier", "verifier", "source")},
            "term": None, "complete": False}
    if oa_skill.get("rules") != RULES:
        return {**base, "status": "incomplete", "headline": "Unsupported rule contract",
                "detail": "The loaded rules do not match the ordinary-purchase example."}
    acquired, sold = date.fromisoformat(gain["acquire_date"]), date.fromisoformat(gain["sell_date"])
    if sold < acquired:
        raise ValueError("sale precedes acquisition")
    # ponytail: Leap-day acquisitions need a verified calendar boundary before classification.
    if (acquired.month, acquired.day) == (2, 29):
        return {**base, "status": "incomplete", "headline": "Holding period remains unresolved",
                "detail": "The ordinary calendar boundary for a 29 February acquisition is not verified here."}
    boundary = (acquired.year + 1, acquired.month, acquired.day)
    term = "long-term" if (sold.year, sold.month, sold.day) > boundary else "short-term"
    amount = gain["gain"]
    outcome = "no gain or loss" if amount == 0 else f"{money(amount.copy_abs())} {'gain' if amount > 0 else 'loss'}"
    detail = "Uses the ordinary-purchase calendar holding period. No tax rate or tax liability is calculated."
    if amount < 0:
        detail += (" This individual lot loss is not a deduction by itself. After annual capital-gain netting,"
                   " an individual's net loss deduction is generally limited to USD 3,000"
                   " (USD 1,500 if married filing separately); unused losses may carry forward.")
    return {**base, "term": term, "complete": True, "status": "info",
            "headline": f"{term.capitalize()}: {outcome}", "detail": detail}
