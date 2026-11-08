import os
from openai import OpenAI

client = OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=os.environ["GEMINI_API_KEY"])
for model in client.models.list():
    if "flash" in model.id:
        print(model.id)