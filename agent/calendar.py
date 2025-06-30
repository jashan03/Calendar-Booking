import os
import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from agent.oauth_utils import get_google_flow
from agent.token_store import stored_token


# Allow HTTP (for local dev)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'

def get_auth_url():
    """Generate the Google OAuth URL for user authorization."""
    flow = get_google_flow()
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url

def save_token_from_code(auth_response_url):
    """Exchange the authorization code for access tokens and store them in session_state."""
    flow = get_google_flow()
    flow.fetch_token(authorization_response=auth_response_url)
    creds = flow.credentials
    st.session_state["token"] = creds.to_json()

def get_calendar_service(token: str = None):
    print("🔍 Inside get_calendar_service(token)")
    token = token or stored_token.get("token")  # fallback if not explicitly passed
    print("🧪 Token used:", token)

    if not token:
        raise ValueError("❌ No token found! User must authenticate first.")

    creds = Credentials.from_authorized_user_info(
        json.loads(token),
        ["https://www.googleapis.com/auth/calendar.events"]
    )
    return build("calendar", "v3", credentials=creds)


def check_availability(token: str):
    service = get_calendar_service(token)
    print("📅 Checking calendar availability...")  # 🔍 DEBUG
    print("🧪 Token in backend memory:", stored_token.get("token"))  # 🔍 DEBUG
    service = get_calendar_service(token)
    now = datetime.now(timezone.utc).isoformat()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        timeMax=tomorrow,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    return events_result.get('items', [])

def book_event(summary, start_time, end_time, token: str):
    service = get_calendar_service(token)
 
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Kolkata'},
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event.get('htmlLink')
