"""One function the rest of the code calls: LLM.complete(system, user, json_mode)."""
import json
import re
import time

import config

RETRY_WAITS = [15, 30, 60]   # seconds to wait after a 429 (free-tier rate limit) before retrying


class LLMError(Exception):
    pass


class LLM:
    def __init__(self, model=None, base_url=None, api_key=None):
        self.model = model or config.MODEL
        self.base_url = base_url or config.BASE_URL
        self.api_key = api_key or config.API_KEY

    @property
    def name(self):
        return f"{config.PROVIDER} / {self.model}"

    def complete(self, system, user, json_mode=False):
        """Calls the model; on a rate-limit error waits and retries a few times."""
        for wait in RETRY_WAITS + [None]:
            try:
                return self._complete_once(system, user, json_mode)
            except LLMError as e:
                if wait is None or "429" not in str(e):
                    raise
                print(f"   rate limited, waiting {wait}s and retrying...", flush=True)
                time.sleep(wait)

    def _complete_once(self, system, user, json_mode=False):
        if not self.api_key:
            raise LLMError("No API key set. Add it as an environment variable or Streamlit secret.")
        from openai import OpenAI
        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            try:
                resp = client.chat.completions.create(
                    model=self.model, messages=messages, temperature=0, **kwargs)
            except Exception:
                if not json_mode:
                    raise
                # some providers reject response_format; the prompt still asks for JSON only
                resp = client.chat.completions.create(model=self.model, messages=messages, temperature=0)
            return resp.choices[0].message.content or ""
        except Exception as e:
            raise LLMError(str(e)) from e


def parse_json(text):
    """Pull the first JSON object out of a model reply (handles ``` fences and stray text)."""
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start:end + 1])
