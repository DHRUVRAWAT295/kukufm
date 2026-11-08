"""The case file: which fields exist, how model output is cleaned, and which questions to ask next."""
from datetime import date, datetime

PROBLEM_TYPES = {"defective", "wrong_item", "not_delivered", "refund_not_paid", "other"}

FIELDS = {
    "in_scope": "bool", "problem_type": "enum", "product": "str", "platform": "str",
    "seller": "str", "order_id": "str", "invoice_number": "str",
    "order_date": "date", "delivery_date": "date", "amount_paid": "int",
    "complained_to_platform": "bool", "complaint_date": "date", "platform_response": "str",
    "relief_wanted": "str", "evidence": "list", "user_district": "str", "user_state": "str",
    "complainant_name": "str", "complainant_address": "str", "fraud_suspected": "bool",
}

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y"]

# Follow-up questions. Code decides WHICH to ask; wording is fixed so it is predictable and free.
QUESTIONS = {
    "problem_type": "What went wrong? Was the item defective, was the wrong item delivered, did it never arrive, or was a refund promised but not paid?",
    "product": "What did you buy?",
    "platform": "Which website or app did you buy it from?",
    "order_date": "On what date did you place the order? (for example 15/03/2026)",
    "amount_paid": "How much did you pay, in rupees?",
    "evidence": "What proof do you have? For example the invoice, order confirmation email, chat screenshots or photos of the product.",
    "complained_to_platform": "Have you already complained to the platform or seller? If yes, what did they say?",
    "complaint_date": "On what date did you complain to them?",
    "user_location": "Which district and state do you live in?",
    "complainant_name": "What is your full name?",
    "complainant_address": "What is your postal address? It goes at the top of the notice.",
    "seller": "What is the seller's name? It's usually printed on the invoice. Say 'not sure' if you can't find it.",
    "order_id": "What is the order ID or invoice number?",
}


def empty_case():
    return {k: None for k in FIELDS}


def _date(value, today):
    if isinstance(value, date):
        d = value
    else:
        for fmt in DATE_FORMATS:
            try:
                d = datetime.strptime(str(value).strip(), fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"unreadable date {value!r}")
    if d > today:
        raise ValueError(f"date {d} is in the future")
    return d.isoformat()


def _int(value):
    if isinstance(value, bool):
        raise ValueError("bool is not an amount")
    n = int(float(str(value).replace(",", "").replace("₹", "").replace("Rs", "").strip()))
    if n <= 0:
        raise ValueError("amount must be positive")
    return n


def _bool(value):
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"true", "yes", "y"}:
        return True
    if s in {"false", "no", "n"}:
        return False
    raise ValueError(f"not a yes/no value {value!r}")


def normalise(field, value, today):
    kind = FIELDS[field]
    if kind == "date":
        return _date(value, today)
    if kind == "int":
        return _int(value)
    if kind == "bool":
        return _bool(value)
    if kind == "enum":
        v = str(value).strip().lower()
        if v not in PROBLEM_TYPES:
            raise ValueError(f"unknown problem type {value!r}")
        return v
    if kind == "list":
        if not isinstance(value, list):
            value = [value]
        return [str(v).strip()[:80] for v in value if str(v).strip()]
    s = str(value).strip()
    if not s:
        raise ValueError("empty")
    return s[:300]


def merge(case, updates, today):
    """Write model output into the case after checking each value. Returns rejected values for the log."""
    rejected = {}
    for field, value in (updates or {}).items():
        if field not in FIELDS or value is None or value == "":
            continue
        try:
            clean = normalise(field, value, today)
        except (ValueError, TypeError) as e:
            rejected[field] = f"{value!r}: {e}"
            continue
        if field == "evidence" and case["evidence"]:
            clean = sorted(set(case["evidence"]) | set(clean))
        case[field] = clean
    return rejected


def intake_missing(case):
    order = ["problem_type", "product", "platform", "order_date", "amount_paid", "evidence",
             "complained_to_platform"]
    missing = [f for f in order if case[f] is None]
    if case["complained_to_platform"] and case["complaint_date"] is None:
        missing.append("complaint_date")
    if case["user_district"] is None:
        missing.append("user_location")
    return missing


def notice_missing(case):
    missing = [f for f in ["complainant_name", "complainant_address", "seller"] if case[f] is None]
    if case["order_id"] is None and case["invoice_number"] is None:
        missing.append("order_id")
    return missing


def inr(n):
    """22000 -> 'Rs 22,000' in Indian grouping, using the rupee sign."""
    s = str(int(n))
    if len(s) <= 3:
        return "₹" + s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups) + "," + tail


def pretty_date(iso):
    return date.fromisoformat(iso).strftime("%d %B %Y").lstrip("0") if iso else None
