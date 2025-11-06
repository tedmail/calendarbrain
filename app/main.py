import os, json, datetime as dt
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from .providers.google_client import GoogleClient
from .providers.ms_client import MSClient
from .rules import DEFAULT_RULES, apply_rules_to_slots, pick_calendar_for_event
from .unifier import merge_busy_windows, find_free_slots
from .templates import make_invite_description
from .nlp import parse_nl

load_dotenv()

TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")

app = FastAPI(title="Calendar Brain", version="0.2.0")

@app.get("/", response_class=HTMLResponse)
def root():
    return open("index.html","r",encoding="utf-8").read()

# --- Google OAuth ---
@app.get("/oauth/start")
def oauth_start(user_id: str = "default"):
    gc = GoogleClient(user_id=user_id)
    return RedirectResponse(gc.auth_url())

@app.get("/oauth/callback")
def oauth_callback(request: Request):
    params = dict(request.query_params)
    state = params.get("state", "default")
    gc = GoogleClient(user_id=state)
    gc.fetch_token(str(request.url))
    return {"ok": True, "provider": "google", "user_id": state}

# --- Microsoft OAuth ---
@app.get("/ms/start")
def ms_start(user_id: str = "default"):
    mc = MSClient(user_id=user_id)
    return RedirectResponse(mc.auth_url())

@app.get("/ms/callback")
def ms_callback(request: Request):
    params = dict(request.query_params)
    state = params.get("state", "default")
    mc = MSClient(user_id=state)
    mc.fetch_token(params)
    return {"ok": True, "provider": "microsoft", "user_id": state}

# ---------- Models ----------
class UnifiedRequest(BaseModel):
    user_id: str = "default"
    duration_min: int = 30
    days_ahead: int = 7
    work_start: str = "09:00"
    work_end: str = "18:00"

class NLCreate(BaseModel):
    user_id: str = "default"
    text: str

# ---------- NLP ----------
@app.post("/nlp/parse")
def nlp_parse(req: NLCreate):
    return {"parsed": parse_nl(req.text)}

# ---------- Slots unificados ----------
@app.post("/unified/free_slots")
def unified_free_slots(req: UnifiedRequest):
    gc = GoogleClient(req.user_id)
    mc = MSClient(req.user_id)

    now = dt.datetime.now(dt.timezone.utc)
    time_min = now.isoformat()
    time_max = (now + dt.timedelta(days=req.days_ahead)).isoformat()

    g_busy = gc.freebusy(time_min, time_max)
    m_busy = mc.freebusy(time_min, time_max)

    merged_busy = merge_busy_windows(g_busy + m_busy)
    slots = find_free_slots(
        merged_busy,
        days_ahead=req.days_ahead,
        work_start=req.work_start,
        work_end=req.work_end,
        duration_min=req.duration_min,
        timezone=TIMEZONE
    )
    ruled = apply_rules_to_slots(slots, DEFAULT_RULES, timezone=TIMEZONE)
    return {"suggested": ruled[:5]}

# ---------- Criação unificada a partir de NL ----------
@app.post("/unified/create_from_nl")
def unified_create_from_nl(req: NLCreate):
    parsed = parse_nl(req.text)
    start_dt = dt.datetime.fromisoformat(f"{parsed['date']}T{parsed['time']}:00")
    end_dt = start_dt + dt.timedelta(minutes=int(parsed.get('duration_min', 60)))

    target = pick_calendar_for_event(parsed, DEFAULT_RULES)

    description = make_invite_description(
        priority=parsed.get('priority', 'media'),
        notes='Created by Calendar Brain',
        agenda_items=['Objetivo', 'Contexto', 'Próximos passos']
    )

    if target == "google":
        gc = GoogleClient(req.user_id)
        ev = gc.create_event(
            summary=parsed['title'],
            start=start_dt, end=end_dt,
            attendees=parsed.get('attendees', []),
            location=parsed.get('location'),
            description=description,
            timezone=TIMEZONE,
            meet=True
        )
        return {"ok": True, "provider": "google", "htmlLink": ev.get("htmlLink"), "id": ev.get("id")}
    else:
        mc = MSClient(req.user_id)
        ev = mc.create_event(
            subject=parsed['title'],
            start=start_dt, end=end_dt,
            attendees=parsed.get('attendees', []),
            location=parsed.get('location'),
            body=description,
            timezone=TIMEZONE,
            teams=True
        )
        return {"ok": True, "provider": "microsoft", "webLink": ev.get("webLink"), "id": ev.get("id")}

# ---------- Briefings ----------
@app.post("/briefing/daily")
def daily_briefing(req: UnifiedRequest):
    slots_resp = unified_free_slots(req)
    return {"message": "Briefing do dia gerado", "slots": slots_resp["suggested"]}

@app.post("/briefing/tomorrow")
def tomorrow_briefing(req: UnifiedRequest):
    slots_resp = unified_free_slots(req)
    return {"message": "Planejamento de amanhã gerado", "slots": slots_resp["suggested"]}
