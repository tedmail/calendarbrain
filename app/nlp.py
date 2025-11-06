import os, json, datetime as dt, requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "Você é um parser de agenda. Extraia deste texto um JSON com:\n"
    "- title (string curta)\n"
    "- date (YYYY-MM-DD no fuso America/Sao_Paulo; se disser 'amanhã', calcule)\n"
    "- time (HH:MM 24h)\n"
    "- duration_min (int)\n"
    "- attendees (array de emails)\n"
    "- location (string opcional)\n"
    "- priority (alta, media, baixa)\n"
    "Responda SOMENTE com JSON válido."
)

def _naive(text: str):
    today = dt.date.today().isoformat()
    return {
        "title": text[:40],
        "date": today,
        "time": "15:00",
        "duration_min": 60,
        "attendees": [],
        "location": "",
        "priority": "media"
    }

def parse_nl(text: str):
    if not OPENAI_API_KEY:
        return _naive(text)
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    try:
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception:
        return _naive(text)
