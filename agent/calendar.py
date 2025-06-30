import os
import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from agent.oauth_utils import get_google_flow  
from agent.token_store import stored_token

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def get_auth_url():
    """Generate the Google OAuth URL for user authorization."""
    flow = get_google_flow()
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url

def save_token_from_code(auth_response_url):
    """Exchange the authorization code for access tokens and store them in memory."""
    flow = get_google_flow()
    flow.fetch_token(authorization_response=auth_response_url)
    creds = flow.credentials
    st.session_state['token'] = creds.to_json()

def get_calendar_service():
    token_data = stored_token.get("token")
    if not token_data:
        raise FileNotFoundError("Missing token. User needs to authorize.")
    creds = Credentials.from_authorized_user_info(json.loads(token_data), ["https://www.googleapis.com/auth/calendar"])
    return build('calendar', 'v3', credentials=creds)

def check_availability():
    service = get_calendar_service()
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

def book_event(summary, start_time, end_time):
    service = get_calendar_service()
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Kolkata'},
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event.get('htmlLink')
