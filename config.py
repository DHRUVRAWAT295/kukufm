"""
All settings in one place. To swap the model, change LLM_PROVIDER (and optionally LLM_MODEL)
as environment variables or Streamlit secrets. No other file needs to change.

Every provider here speaks the OpenAI-compatible chat API, so the same client works for all.
Model names change often: check the provider's current free models before running.
"""
import os

PRESETS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash",
        "key_env": "GEMINI_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
    },
    "openai": {
        "base_url": None,
        "model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
}

PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
_preset = PRESETS.get(PROVIDER, PRESETS["gemini"])
MODEL = os.getenv("LLM_MODEL") or _preset["model"]
BASE_URL = os.getenv("LLM_BASE_URL") or _preset["base_url"]
API_KEY = os.getenv("LLM_API_KEY") or os.getenv(_preset["key_env"])

# Business settings (assumptions, stated in the solution doc)
DISTRICT_LIMIT = 50_00_000        # Rs 50 lakh, Jurisdiction Rules 2021
STATE_LIMIT = 2_00_00_000         # Rs 2 crore
LIMITATION_YEARS = 2              # CPA 2019 s.69(1)
WARN_DAYS_BEFORE_LIMIT = 60
PLATFORM_REDRESS_DAYS = 30        # "one month" under E-Commerce Rules 4(5), approximated as 30 days
NOTICE_REPLY_DAYS = 15            # deadline we give the seller in the notice (our choice, not a legal rule)
MAX_QUESTIONS_PER_TURN = 3
MAX_ASKS_PER_FIELD = 2
