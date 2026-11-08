"""Streamlit chat app. Run locally:  streamlit run app.py"""
import json
import os

import streamlit as st

# Copy Streamlit secrets into environment variables BEFORE config.py is imported,
# so the same code works locally (secrets.toml) and on Streamlit Cloud.
try:
    for key, value in st.secrets.items():
        if isinstance(value, str):
            os.environ.setdefault(key, value)
except Exception:
    pass  # no secrets file: fall back to real environment variables

from bot import Bot
from llm import LLM

st.set_page_config(page_title="Refund help for online orders", page_icon="🧾")


def new_session():
    st.session_state.bot = Bot(LLM())
    st.session_state.chat = []


if "bot" not in st.session_state:
    new_session()
bot = st.session_state.bot

ALERT_BOX = {"stop": st.error, "warning": st.warning}

# ---------- sidebar: the case file, visible at all times ----------
with st.sidebar:
    st.subheader("Your case file")
    st.caption("Built from what you've told me. Check it's right.")
    st.json({k: v for k, v in bot.case.items() if v is not None}, expanded=True)
    if bot.notice:
        st.download_button("Download notice", bot.notice, file_name="legal_notice.txt")
    st.download_button("Download conversation log", json.dumps(bot.export_log(), indent=2, ensure_ascii=False),
                       file_name="conversation_log.json")
    if st.button("Start over"):
        new_session()
        st.rerun()
    st.caption(f"Model: {bot.llm.name}")

# ---------- main ----------
st.title("Refund help for online orders")
st.write("Bought something online that was defective, wrong, or never arrived, and the refund hasn't come? "
         "Tell me what happened in your own words. I'll work out where you stand and draft a legal notice "
         "you can send to the seller.")
st.caption("Legal information, not legal advice. English only for now.")

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for a in msg.get("alerts", []):
            ALERT_BOX[a["level"]](f"**{a['title']}.** {a['message']}")

if prompt := st.chat_input("Describe your problem"):
    st.session_state.chat.append({"role": "user", "content": prompt})
    with st.spinner("Reading your message"):
        result = bot.handle(prompt)
    st.session_state.chat.append({"role": "assistant", "content": result["reply"],
                                  "alerts": result["new_alerts"]})
    st.rerun()
