"""
Escalation alerts. Plain Python on purpose: the model never decides whether to escalate.

  stop    -> outside this tool's scope; no notice is drafted
  warning -> continue, but the user must see this

Sources: CPA 2019 s.69 (time limit), Jurisdiction Rules 2021 (Rs 50 lakh),
MHA cyber fraud helpline 1930 and cybercrime.gov.in.
"""
import re
from dataclasses import dataclass, asdict
from datetime import date

import config

# Fraud is two-tier. People often say "fraud" or "scam" about an ordinary late refund,
# so a keyword alone only WARNS. A stop needs the model's fraud_suspected flag, which is
# asked only for real scam signs (fake seller, OTP/UPI PIN trick, unauthorised debit).
FRAUD_WORDS = [
    r"\bfraud\w*", r"\bscam\w*", r"\bfake (?:seller|website|site|app|call|link|page)",
    r"\bphishing\b", r"\botp\b", r"\bupi pin\b", r"\bhacked\b",
    r"\bunauthori[sz]ed (?:payment|transaction|debit)", r"\b(?:deducted|debited) without",
]


@dataclass
class Alert:
    level: str
    code: str
    title: str
    message: str

    def to_dict(self):
        return asdict(self)


def _add_years(d, years):
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def check_scope(case):
    if case.get("in_scope") is False:
        return [Alert("stop", "OUT_OF_SCOPE", "This is outside what I can help with",
                      "I only help with things bought online that were defective, wrong, not delivered "
                      "or not refunded. For other legal problems, your District Legal Services Authority "
                      "offers free legal help.")]
    return []


def check_fraud(case, story):
    if case.get("fraud_suspected"):
        return [Alert("stop", "POSSIBLE_CRIME", "This looks like fraud, not a refund dispute",
                      "If money was taken through a scam, call your bank first so it can try to freeze "
                      "the payment, then call the cyber fraud helpline 1930 and file a complaint at "
                      "cybercrime.gov.in. Please also speak to a lawyer. This tool handles only ordinary "
                      "refund disputes.")]
    text = (story or "").lower()
    if any(re.search(p, text) for p in FRAUD_WORDS):
        return [Alert("warning", "FRAUD_WORDS", "Check: is this a scam?",
                      "You used words like 'fraud' or 'scam'. If someone tricked you into paying "
                      "(a fake seller, a request for your OTP or UPI PIN, money taken without permission), "
                      "stop here: call your bank, then 1930, and report at cybercrime.gov.in. If it's an "
                      "ordinary refund problem with a real platform, carry on.")]
    return []


def check_amount(case):
    amount = case.get("amount_paid")
    if amount and amount > config.DISTRICT_LIMIT:
        return [Alert("stop", "AMOUNT_ABOVE_SCOPE", "Amount above ₹50 lakh",
                      "Cases above ₹50 lakh go to the State or National Commission and are outside what "
                      "this tool covers. Please speak to a consumer lawyer or your District Legal "
                      "Services Authority.")]
    return []


def check_limitation(case, today):
    # Conservative: count from the ORDER date. The legal start date (cause of action) may be
    # later, e.g. when the refund was refused. Stated as an assumption in the doc.
    if not case.get("order_date"):
        return []
    start = date.fromisoformat(case["order_date"])
    deadline = _add_years(start, config.LIMITATION_YEARS)
    if today > deadline:
        return [Alert("stop", "PAST_TIME_LIMIT", "This may be past the two-year time limit",
                      f"You ordered on {start:%d %b %Y}, so the usual deadline was {deadline:%d %b %Y}. "
                      "A late complaint is accepted only if the commission agrees there was sufficient "
                      "cause for the delay. Please speak to a lawyer before going further.")]
    days_left = (deadline - today).days
    if days_left <= config.WARN_DAYS_BEFORE_LIMIT:
        return [Alert("warning", "TIME_LIMIT_CLOSE", "The time limit is close",
                      f"About {days_left} days remain before {deadline:%d %b %Y}. Act quickly.")]
    return []


def check_evidence(case):
    if case.get("evidence") == []:
        return [Alert("warning", "NO_EVIDENCE", "You have no proof yet",
                      "Without an invoice, order email or screenshots your case will be hard to prove. "
                      "Check your email and the app's order history for the invoice before sending a notice.")]
    return []


def check_alerts(case, story="", today=None):
    today = today or date.today()
    alerts = (check_scope(case) + check_fraud(case, story) + check_amount(case)
              + check_limitation(case, today) + check_evidence(case))
    return sorted(alerts, key=lambda a: a.level != "stop")


def has_stop(alerts):
    return any(a.level == "stop" for a in alerts)
