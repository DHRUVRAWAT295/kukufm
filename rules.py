"""Decisions made in code, not by the model: which commission, what the next step is, what to ask for."""
from datetime import date, timedelta

import config


def commission(amount):
    if amount is None:
        return None
    if amount <= config.DISTRICT_LIMIT:
        return "District Consumer Disputes Redressal Commission"
    if amount <= config.STATE_LIMIT:
        return "State Consumer Disputes Redressal Commission"
    return "National Consumer Disputes Redressal Commission"


def platform_step(case, today):
    """complain_first -> the platform hasn't been told yet
       wait           -> told, but its one-month period is still running
       send_notice    -> the one-month period has passed (or the date is unknown)"""
    if not case.get("complained_to_platform"):
        return {"step": "complain_first"}
    if case.get("complaint_date"):
        due = date.fromisoformat(case["complaint_date"]) + timedelta(days=config.PLATFORM_REDRESS_DAYS)
        if today < due:
            return {"step": "wait", "until": due.isoformat()}
    return {"step": "send_notice"}


RELIEF = {
    "defective": "replace the product or refund the full price",
    "wrong_item": "deliver the correct product or refund the full price",
    "not_delivered": "refund the full price",
    "refund_not_paid": "pay the refund",
    "other": "refund the full price",
}


def relief(case):
    return RELIEF.get(case.get("problem_type") or "other", RELIEF["other"])


PROBLEM_SENTENCE = {
    "defective": "The product turned out to be defective.",
    "wrong_item": "I received a different product from the one I ordered.",
    "not_delivered": "The product was never delivered to me.",
    "refund_not_paid": "The refund promised to me has not been paid.",
    "other": "The order was not fulfilled as promised.",
}
