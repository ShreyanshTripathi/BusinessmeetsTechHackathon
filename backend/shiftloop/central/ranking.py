"""Urgency score for incidents. Safety always comes first; the rest is line impact, spread risk and confidence."""
from __future__ import annotations

from ..models import Event, Incident
from .fusion import LIVE_SAFETY_TYPES

SEVERITY_POINTS = {"info": 0, "low": 10, "medium": 30, "high": 60, "critical": 100}
SAFETY_BONUS = 1000  # hard rule: any live safety hazard outranks every other incident
QUALITY_SPREAD_BONUS = 200


def score(incident: Incident, events: list[Event]) -> float:
    s = SEVERITY_POINTS[incident.severity.value]
    types = {e.type for e in events}
    if types & LIVE_SAFETY_TYPES:
        s += SAFETY_BONUS  # reports of past near misses matter, but do not outrank a live line problem
    if any(e.data.get("spread_risk") for e in events):
        s += QUALITY_SPREAD_BONUS
    if "station_stopped" in types:
        s += 40  # a stopped station stops the moving line
    if "station_uncovered" in types:
        s += 35
    for e in events:
        if e.type == "part_shortage" and e.data.get("minutes_left", 99) < 10:
            s += 30
        if e.type == "predicted_tool_failure" and (e.data.get("eta_min") or 999) <= 60:
            s += 20
    s += 10 * (len(set(incident.agents)) - 1)  # connected findings across functions matter more
    s += 10 * incident.confidence
    return round(s, 1)
