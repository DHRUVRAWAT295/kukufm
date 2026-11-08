# Refund help for online orders

A chat assistant for one problem: someone in India bought something online, it was defective, wrong, or never delivered, and the refund hasn't come. It builds the case from their story, tells them where they stand, and drafts a legal notice to the seller and platform.

## Run it

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then paste your free API key
streamlit run app.py
```

Offline tests (no key needed): `python tests/test_offline.py`
Real runs that produce the raw-outputs folder: `python run_tests.py`

**Deploy free:** push to GitHub, create an app on Streamlit Community Cloud pointing at `app.py`, and paste the secrets in the app settings.

**Swap the model:** set `LLM_PROVIDER` to `gemini`, `groq` or `openai` (and optionally `LLM_MODEL`). Nothing else changes. Model names change often, so check the provider's current free models.

## How it works

| Step | Done by | File |
|---|---|---|
| Read the story into a case file | LLM, JSON only | `prompts.py`, `bot.py` |
| Check each extracted value (dates, amounts, yes/no) | Code | `case.py` |
| Stop or warn: amount, time limit, scam, scope, no proof | Code | `alerts.py` |
| Which questions to ask next | Code (fixed wording) | `case.py` |
| Which commission, next step, what to ask for | Code | `rules.py` |
| Plain-language explanation | LLM, verified provisions only | `prompts.py` |
| Notice | Code template; LLM writes only the facts paragraph | `notice.py` |
| Remove invented law, cases, amounts, years | Code | `validator.py` |

About 3 model calls per conversation turn at most, typically 4 to 6 per full case.

## Avoiding invented law

1. `provisions.json` holds hand-checked provisions. Only entries marked `"verified": true` are shown to the model or allowed in output. Two entries are marked `false` until checked against the bare act.
2. The model may mention a law only by copying a citation string from that list.
3. `validator.py` drops any sentence citing a section, rule, Act or court case outside the list, or containing an amount or year not in the case file. Every removal is logged.
4. All legal statements in the notice come from the code template, not the model.

## Known limits

- English text only.
- The two-year limit is counted from the order date (conservative); the legal start date may be later.
- Scam detection: keywords only warn; a stop needs the model's flag, which can be wrong both ways.
- Fixed follow-up questions can feel repetitive.
- The validator works on patterns: a law described without a number or name (e.g. "a consumer law says…") gets through.
- The E-Commerce Rules were amended in 2026; re-check Rule 4(5) before relying on it.
