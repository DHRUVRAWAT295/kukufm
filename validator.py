"""
Checks model-written text before the user sees it. Any sentence that
  - cites a section or rule not in the verified list,
  - names an Act/Rules other than the consumer-protection ones we verified,
  - cites a court case,
  - or contains a rupee amount or year that isn't in the case file
is removed, and the problem is logged. This is our main defence against invented law.
"""
import re
from datetime import date

import config
from provisions import allowed_numbers

SECTION_RE = re.compile(r"\b(?:section|sec\.|u/s|s\.)\s*(\d+[A-Z]?)", re.I)
RULE_RE = re.compile(r"\brule\s+(\d+)", re.I)
ACT_RE = re.compile(r"\b(Act|Rules|Code|Sanhita|Regulations),?\s+(\d{4})")
CASE_RE = re.compile(r"\b[A-Z][\w.&]*(?:\s[A-Z][\w.&]*)*\s+(?:v\.|vs\.?|versus)\s+[A-Z]")
AMOUNT_RE = re.compile(r"(?:₹|\brs\.?|\binr)\s*([\d,]+(?:\.\d+)?)\s*(lakh|crore)?", re.I)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
ALLOWED_ACTS = {("Act", "2019"), ("Rules", "2020"), ("Rules", "2021")}


def _amount(num, unit):
    n = float(num.replace(",", ""))
    if unit and unit.lower() == "lakh":
        n *= 1_00_000
    elif unit and unit.lower() == "crore":
        n *= 1_00_00_000
    return int(n)


def find_problems(sentence, case, provisions, allow_citations=True, today=None):
    today = today or date.today()
    sections, rules = allowed_numbers(provisions)
    problems = []
    for m in SECTION_RE.finditer(sentence):
        if not allow_citations or m.group(1) not in sections:
            problems.append(f"section not allowed: {m.group(0)}")
    for m in RULE_RE.finditer(sentence):
        if not allow_citations or m.group(1) not in rules:
            problems.append(f"rule not allowed: {m.group(0)}")
    for m in ACT_RE.finditer(sentence):
        window = sentence[max(0, m.start() - 160):m.end()]
        ok = (m.group(1), m.group(2)) in ALLOWED_ACTS and "Consumer Protection" in window
        if not allow_citations or not ok:
            problems.append(f"law not allowed: ...{window[-60:]}")
    for m in CASE_RE.finditer(sentence):
        problems.append(f"court case cited: {m.group(0)}")
    allowed_amounts = {case.get("amount_paid"), config.DISTRICT_LIMIT, config.STATE_LIMIT}
    for m in AMOUNT_RE.finditer(sentence):
        if _amount(m.group(1), m.group(2)) not in allowed_amounts:
            problems.append(f"amount not in case file: {m.group(0)}")
    allowed_years = {today.year, 2019, 2020, 2021}
    allowed_years |= {int(case[f][:4]) for f in ("order_date", "delivery_date", "complaint_date") if case.get(f)}
    for m in YEAR_RE.finditer(sentence):
        if int(m.group(1)) not in allowed_years:
            problems.append(f"year not in case file: {m.group(1)}")
    return problems


ABBREVIATIONS = {"v.", "vs.", "rs.", "no.", "sec.", "s.", "u/s.", "mr.", "mrs.", "ms.", "dr.", "st.", "ltd.", "pvt.", "co."}


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    sentences = []
    for p in parts:
        if sentences and sentences[-1].split()[-1].lower() in ABBREVIATIONS:
            sentences[-1] += " " + p
        else:
            sentences.append(p)
    return [s for s in sentences if s]


def validate_and_clean(text, case, provisions, allow_citations=True, today=None):
    """Returns (clean_text, problems). Problem sentences are dropped, not edited."""
    sentences = split_sentences(text)
    kept, problems = [], []
    for s in sentences:
        p = find_problems(s, case, provisions, allow_citations, today)
        if p:
            problems.append({"sentence": s, "problems": p})
        else:
            kept.append(s)
    return " ".join(kept).strip(), problems
