"""
The notice is a fixed template filled by code. The model writes only the facts paragraph.
Every legal reference in the template comes from a verified entry in provisions.json.
"""
import config
from case import inr, pretty_date
from rules import PROBLEM_SENTENCE, commission, relief


def display_fields(case):
    return {
        "order_date": pretty_date(case.get("order_date")),
        "delivery_date": pretty_date(case.get("delivery_date")),
        "complaint_date": pretty_date(case.get("complaint_date")),
        "amount_paid": inr(case["amount_paid"]) if case.get("amount_paid") else None,
    }


def _known(value):
    return value and str(value).lower() != "unknown"


def fallback_facts(case):
    """Used if the model is unavailable or its paragraph fails validation."""
    d = display_fields(case)
    parts = [f"On {d['order_date'] or 'a date I will confirm'}, I ordered {case.get('product') or 'a product'} "
             f"from {case.get('platform') or 'your platform'}"]
    if _known(case.get("seller")):
        parts[0] += f", sold by {case['seller']}"
    ref = case.get("order_id") if _known(case.get("order_id")) else case.get("invoice_number")
    if _known(ref):
        parts[0] += f" (order/invoice reference {ref})"
    parts[0] += f", and paid {d['amount_paid'] or 'the full price'}."
    parts.append(PROBLEM_SENTENCE.get(case.get("problem_type") or "other"))
    if case.get("complained_to_platform"):
        when = f" on {d['complaint_date']}" if d["complaint_date"] else ""
        resp = f" The response I received was: {case['platform_response']}." if _known(case.get("platform_response")) else ""
        parts.append(f"I complained to {case.get('platform') or 'the platform'}{when}, but the matter has not been resolved.{resp}")
    return " ".join(parts)


def build_notice(case, facts_paragraph, today):
    d = display_fields(case)
    seller_known = _known(case.get("seller"))
    platform = case.get("platform") or "the e-commerce platform"
    ref = case.get("order_id") if _known(case.get("order_id")) else case.get("invoice_number")
    place = ", ".join(x for x in [case.get("user_district"), case.get("user_state")] if _known(x))

    to_lines = []
    if seller_known:
        to_lines.append(f"{len(to_lines) + 1}. {case['seller']} (seller of the product)")
    to_lines.append(f"{len(to_lines) + 1}. The Grievance Officer, {platform}")

    platform_para = ""
    if case.get("complained_to_platform"):
        platform_para = (
            f"Under Rule 4(5) of the Consumer Protection (E-Commerce) Rules, 2020, the grievance officer of "
            f"{platform} was required to acknowledge my complaint within 48 hours and resolve it within one "
            f"month. This has not happened.\n\n")

    enclosures = case.get("evidence") or ["Invoice", "Order confirmation"]
    lines = [
        "LEGAL NOTICE",
        "",
        f"Date: {today.strftime('%d %B %Y').lstrip('0')}",
        "",
        f"From: {case.get('complainant_name')}",
        f"{case.get('complainant_address')}",
        "",
        "To:",
        *to_lines,
        "",
        f"Subject: Unresolved consumer complaint about {case.get('product') or 'my order'}"
        + (f" (reference {ref})" if _known(ref) else ""),
        "",
        "Sir/Madam,",
        "",
        facts_paragraph,
        "",
        platform_para
        + f"I therefore call upon you to {relief(case)} of {d['amount_paid'] or 'the amount paid'} within "
          f"{config.NOTICE_REPLY_DAYS} days of receiving this notice. If you fail to do so, I will file a complaint "
          f"before the {commission(case.get('amount_paid')) or 'appropriate Consumer Commission'}"
          + (f", {place}" if place else "")
          + ", under the Consumer Protection Act, 2019, seeking this relief along with compensation and "
            "costs, without further notice to you.",
        "",
        "Enclosures: " + "; ".join(e[:1].upper() + e[1:] for e in enclosures),
        "",
        "Yours faithfully,",
        "",
        f"{case.get('complainant_name')}",
    ]
    return "\n".join(lines)
