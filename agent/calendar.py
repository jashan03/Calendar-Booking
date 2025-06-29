# agent/calendar.py

import os
import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Allow HTTP during local development (Streamlit cloud uses HTTPS anyway)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Scopes required for calendar access
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_auth_url():
    """Generate the Google OAuth URL for user authorization."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url

def save_token_from_code(auth_response_url):
    """Exchange the authorization code for access tokens and store them in memory."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
            }
        },
        scopes=SCOPES,
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
    )
    flow.fetch_token(authorization_response=auth_response_url)
    creds = flow.credentials
    # Save token to session state
    st.session_state['token'] = creds.to_json()

def get_calendar_service():
    """Build the calendar service using session-stored credentials."""
    token_data = st.session_state.get("token")
    if not token_data:
        raise FileNotFoundError("Missing token. User needs to authorize.")

    creds = Credentials.from_authorized_user_info(json.loads(token_data), SCOPES)
    return build('calendar', 'v3', credentials=creds)

def check_availability():
    """Check events scheduled between now and tomorrow."""
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
    """Book an event in the calendar."""
    service = get_calendar_service()
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Kolkata'},
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event.get('htmlLink')
