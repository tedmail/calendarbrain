import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from fastapi import HTTPException

GOOGLE_CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "client_secret.json")
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"]
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

TOKENS = {}  # trocar por DB/Redis em produção

class GoogleClient:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def _flow(self):
        return Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRETS_FILE,
            scopes=GOOGLE_SCOPES,
            redirect_uri=f"{BASE_URL}/oauth/callback",
            state=self.user_id
        )

    def auth_url(self):
        flow = self._flow()
        auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
        return auth_url

    def fetch_token(self, authorization_response: str):
        flow = self._flow()
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials
        TOKENS[self.user_id] = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }

    def _service(self):
        if self.user_id not in TOKENS:
            raise HTTPException(401, "Google não autenticado.")
        creds = Credentials.from_authorized_user_info(TOKENS[self.user_id])
        return build("calendar", "v3", credentials=creds)

    def freebusy(self, time_min: str, time_max: str):
        svc = self._service()
        fb = svc.freebusy().query(body={
            "timeMin": time_min, "timeMax": time_max,
            "items": [{"id": "primary"}]
        }).execute()
        return fb["calendars"]["primary"]["busy"]

    def create_event(self, summary, start, end, attendees, location, description, timezone, meet=True):
        svc = self._service()
        event = {
            "summary": summary,
            "start": {"dateTime": start.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": timezone},
            "attendees": [{"email": e} for e in attendees],
            "location": location or "",
            "description": description
        }
        if meet:
            event["conferenceData"] = {"createRequest": {"requestId": f"meet-{int(start.timestamp())}"}}
        created = svc.events().insert(calendarId="primary", body=event, conferenceDataVersion=1).execute()
        return created
