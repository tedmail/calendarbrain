import datetime as dt
from typing import List, Dict

DEFAULT_RULES = {
    "meeting_windows": [("10:30", "12:00"), ("14:00", "17:30")],
    "focus_blocks": [("09:00", "10:30"), ("16:00", "18:00")],
    "buffer_min": 15,
    "max_meetings_per_day": 4,
    "avoid_friday_after": "15:00",
    "vips": ["Pedro Silva"],
    "priority_first": ["cliente", "estrategia"],
}

def _parse_time(s): return dt.time.fromisoformat(s)

def _in_window(t: dt.time, start: str, end: str):
    return _parse_time(start) <= t <= _parse_time(end)

def apply_rules_to_slots(slots: List[Dict], rules: Dict, timezone: str):
    filtered = []
    for s in slots:
        start = dt.datetime.fromisoformat(s["start"])
        t = start.time()

        # Sexta após 15:00
        if start.weekday() == 4 and t >= _parse_time(rules["avoid_friday_after"]):
            continue

        # Deve cair numa janela de reunião
        ok = False
        for w in rules["meeting_windows"]:
            if _in_window(t, w[0], w[1]):
                ok = True
                break
        if not ok:
            continue

        filtered.append(s)
    return filtered

def pick_calendar_for_event(parsed, rules):
    attendees = parsed.get("attendees", [])
    if any(a.lower().endswith((".microsoft.com", ".outlook.com", ".office.com")) for a in attendees):
        return "microsoft"
    return "google"
