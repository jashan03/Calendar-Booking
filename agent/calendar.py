# agent/calendar.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import os
from datetime import datetime, timedelta, timezone

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json'

def get_calendar_service():
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError("Missing token.json. User needs to authorize.")

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    from googleapiclient.discovery import build
    return build('calendar', 'v3', credentials=creds)

def get_auth_url():
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri="http://localhost:8501"
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url

def save_token_from_code(authorization_response_url):
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri="http://localhost:8501"
    )
    flow.fetch_token(authorization_response=authorization_response_url)
    creds = flow.credentials
    with open(TOKEN_PATH, "w") as token_file:
        token_file.write(creds.to_json())


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

