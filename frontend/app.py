# frontend/app.py
import streamlit as st
import requests
import sys
import os

# Add parent directory to sys.path so "agent" becomes importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.calendar import get_auth_url, get_calendar_service, save_token_from_code

st.title("📅 AI Calendar Booking Assistant")

# ✅ Utility to get full redirect URL (since st.request.url doesn't exist)
def get_current_url():
    headers = st.context.headers
    protocol = headers.get("X-Forwarded-Proto", "http")
    host = headers.get("Host", "localhost:8501")

    # Build query string properly with a '?'
    query_dict = st.query_params
    query_string = "&".join(f"{k}={v}" for k, v in query_dict.items())

    return f"{protocol}://{host}/?{query_string}"  # ✅ add '?' before query params

# ✅ Handle redirect from Google
if "code" in st.query_params:
    try:
        full_url = get_current_url()  # Get full URL with code param
        save_token_from_code(full_url)
        st.success("✅ Google Calendar connected successfully!")
        st.query_params.clear()  # Remove ?code=... from URL
    except Exception as e:
        st.error(f"❌ Failed to save token: {e}")
        st.stop()

# ✅ Check if token exists
token_missing = False
try:
    get_calendar_service()
except FileNotFoundError:
    token_missing = True

if token_missing:
    st.warning("Please connect your Google Calendar to proceed.")
    if st.button("Connect Google Calendar"):
        auth_url = get_auth_url()
        st.markdown(f"[Authorize here]({auth_url})", unsafe_allow_html=True)
    st.stop()

# ✅ Chat UI
if "history" not in st.session_state:
    st.session_state.history = []

user_input = st.text_input("Ask something...")

if st.button("Send") and user_input:
    st.session_state.history.append(("You", user_input))
    res = requests.post("http://localhost:8080/chat", json={"message": user_input})
    bot_reply = res.json().get("response", "Error")
    st.session_state.history.append(("Bot", bot_reply))

for sender, msg in st.session_state.history:
    st.write(f"**{sender}:** {msg}")
