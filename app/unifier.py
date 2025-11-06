import datetime as dt
from typing import List, Dict

def merge_busy_windows(busy: List[Dict]):
    intervals = [(dt.datetime.fromisoformat(b["start"]), dt.datetime.fromisoformat(b["end"])) for b in busy]
    intervals.sort(key=lambda x: x[0])
    merged = []
    for s, e in intervals:
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)
    return [{"start": s.isoformat(), "end": e.isoformat()} for s, e in merged]

def find_free_slots(merged_busy: List[Dict], days_ahead: int, work_start: str, work_end: str, duration_min: int, timezone: str):
    tznow = dt.datetime.now().astimezone()
    free = []
    for d in range(days_ahead + 1):
        day = (tznow + dt.timedelta(days=d)).date()
        ws = dt.datetime.combine(day, dt.time.fromisoformat(work_start), tzinfo=tznow.tzinfo)
        we = dt.datetime.combine(day, dt.time.fromisoformat(work_end), tzinfo=tznow.tzinfo)

        cursor = ws
        for b in merged_busy:
            bs = dt.datetime.fromisoformat(b["start"]).astimezone(tznow.tzinfo)
            be = dt.datetime.fromisoformat(b["end"]).astimezone(tznow.tzinfo)
            if be <= ws or bs >= we:
                continue
            if bs > cursor:
                gap = (bs - cursor).total_seconds() / 60
                if gap >= duration_min + 15:  # 15min buffer embutido
                    free.append({"start": cursor.isoformat(), "end": bs.isoformat()})
            cursor = max(cursor, be)
        if we > cursor:
            gap = (we - cursor).total_seconds() / 60
            if gap >= duration_min + 15:
                free.append({"start": cursor.isoformat(), "end": we.isoformat()})
    return free
