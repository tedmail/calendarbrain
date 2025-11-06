import os, requests
import msal
from fastapi import HTTPException

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
MS_TENANT_ID = os.getenv("MS_TENANT_ID", "common")

TOKENS_MS = {}  # trocar por DB/Redis

SCOPES = ["offline_access", "User.Read", "Calendars.ReadWrite"]
AUTHORITY = f"https://login.microsoftonline.com/{MS_TENANT_ID}"

class MSClient:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def _app(self):
        return msal.ConfidentialClientApplication(
            MS_CLIENT_ID,
            authority=AUTHORITY,
            client_credential=MS_CLIENT_SECRET
        )

    def auth_url(self):
        app = self._app()
        return app.get_authorization_request_url(
            scopes=SCOPES,
            redirect_uri=f"{BASE_URL}/ms/callback",
            state=self.user_id,
            prompt="consent"
        )

    def fetch_token(self, callback_params: dict):
        app = self._app()
        code = callback_params.get("code")
        if not code:
            raise HTTPException(400, "Missing auth code from Microsoft.")
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPES,
            redirect_uri=f"{BASE_URL}/ms/callback"
        )
        if "access_token" not in result:
            raise HTTPException(400, f"MS OAuth error: {result}")
        TOKENS_MS[self.user_id] = result

    def _token(self):
        if self.user_id not in TOKENS_MS:
            raise HTTPException(401, "Microsoft não autenticado.")
        return TOKENS_MS[self.user_id]["access_token"]

    def _headers(self):
        return {"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"}

    def freebusy(self, time_min: str, time_max: str):
        url = "https://graph.microsoft.com/v1.0/me/calendarView"
        params = {"startDateTime": time_min, "endDateTime": time_max}
        r = requests.get(url, headers=self._headers(), params=params, timeout=60)
        if r.status_code >= 400:
            raise HTTPException(400, f"MS freebusy error: {r.text}")
        busy = []
        for ev in r.json().get("value", []):
            busy.append({"start": ev["start"]["dateTime"], "end": ev["end"]["dateTime"]})
        return busy

    def create_event(self, subject, start, end, attendees, location, body, timezone, teams=True):
        url = "https://graph.microsoft.com/v1.0/me/events"
        event = {
            "subject": subject,
            "start": {"dateTime": start.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": timezone},
            "location": {"displayName": location or ""},
            "attendees": [{"emailAddress": {"address": e}, "type": "required"} for e in attendees],
            "body": {"contentType": "HTML", "content": body}
        }
        if teams:
            event["isOnlineMeeting"] = True
            event["onlineMeetingProvider"] = "teamsForBusiness"
        r = requests.post(url, headers=self._headers(), json=event, timeout=60)
        if r.status_code >= 400:
            raise HTTPException(400, f"MS create event error: {r.text}")
        return r.json()
