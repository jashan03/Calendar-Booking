import streamlit as st
import requests
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to sys.path so "agent" becomes importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.calendar import get_auth_url, get_calendar_service, save_token_from_code

st.set_page_config(page_title="AI Calendar Assistant", page_icon="📅")
st.title("📅 AI Calendar Booking Assistant")

# ✅ Backend URL constant
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")


# ✅ 1. Check required environment variables
required_env_vars = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"]
missing_keys = [k for k in required_env_vars if not os.getenv(k)]
if missing_keys:
    st.error(f"❌ Missing required environment variables: {', '.join(missing_keys)}")
    st.stop()

# ✅ 2. Utility: Get full redirect URL including query params
def get_current_url():
    headers = st.context.headers
    protocol = headers.get("X-Forwarded-Proto", "http")
    host = headers.get("Host", "localhost:8501")

    query_dict = st.query_params
    query_string = "&".join(f"{k}={v}" for k, v in query_dict.items())

    return f"{protocol}://{host}/?{query_string}" if query_string else f"{protocol}://{host}/"

# ✅ 3. Handle Google OAuth redirect with ?code=...
if "code" in st.query_params:
    try:
        full_url = get_current_url()
        save_token_from_code(full_url)
        # st.session_state["token"] is now set by save_token_from_code

        res = requests.post(
            f"{BACKEND_URL}/chat/token",
            json={"token": st.session_state["token"]} # Pass the actual token string from session state
        )

        if res.ok:
            st.success("✅ Google Calendar connected successfully!")
            st.session_state["token_ready"] = True
            # Clear the query parameters to prevent re-running this block on refresh
            st.query_params.clear() # This clears the URL parameters
            st.rerun() # Use st.rerun() instead of st.experimental_rerun() for a full re-run
        else:
            st.error("❌ Failed to store token in backend.")
            st.stop()
    except Exception as e:
        st.error(f"❌ Failed to save token: {e}")
        st.stop()

# ✅ 4. Check if Google token is available
if "token" not in st.session_state or not st.session_state.get("token_ready"):
    st.warning("Please connect your Google Calendar to continue.")
    if st.button("Connect Google Calendar"):
        auth_url = get_auth_url()
        st.markdown(f"[Click here to authorize Google Calendar]({auth_url})", unsafe_allow_html=True)
    st.stop()

# ✅ 5. Now that token is present, safely call get_calendar_service()
# Retrieve the token from session_state before passing it
current_token = st.session_state.get("token")
if not current_token:
    st.error("Authentication token is missing. Please re-authenticate.")
    st.stop()

try:
    # Pass the retrieved token to the function
    get_calendar_service(current_token)
except Exception as e:
    st.error(f"❌ Calendar service initialization error: {e}")
    st.stop()

# ✅ 6. Chat Interface
if "history" not in st.session_state:
    st.session_state.history = []

user_input = st.text_input("Ask something (e.g. 'Am I free tomorrow?' or 'Book a meeting at 3 PM and specify date'): ")

if st.button("Send") and user_input:
    st.session_state.history.append(("You", user_input))

    try:
        # ✅ Send user message to backend
        res = requests.post(
            f"{BACKEND_URL}/chat",
            json={
                "message": user_input,
                "token": st.session_state.get("token")
            }
        )

        bot_reply = res.json().get("response", "Error: No response from backend.")
    except Exception as e:
        bot_reply = f"❌ Failed to contact backend: {e}"

    st.session_state.history.append(("Bot", bot_reply))

# ✅ 7. Show chat history
for sender, msg in st.session_state.history:
    st.write(f"**{sender}:** {msg}")