"""Loads provisions.json. Only entries with "verified": true are ever shown to the model or allowed by the validator."""
import json
from pathlib import Path

PATH = Path(__file__).parent / "provisions.json"


def load_provisions(verified_only=True):
    items = json.loads(PATH.read_text(encoding="utf-8"))
    return [p for p in items if p["verified"] or not verified_only]


def provisions_for_prompt(provisions):
    return "\n".join(f'- cite exactly as "{p["cite"]}": {p["plain"]} (use when: {p["use_when"]})'
                     for p in provisions)


def allowed_numbers(provisions):
    """Section numbers of the Act and rule numbers that may appear in any output."""
    sections = {p["number"] for p in provisions if p["kind"] == "section"}
    rules = {p["number"] for p in provisions if p["kind"] == "rule"}
    return sections, rules
