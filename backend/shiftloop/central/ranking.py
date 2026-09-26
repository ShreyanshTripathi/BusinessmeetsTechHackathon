"""Priority of incidents: a strict tier first, then a transparent score within the tier.

Tiers (non-negotiable order):
  0 Safety / human life   live hazards, fire warden gaps, anything under the safety-stop hard rule
  1 Line stoppage         a station stopped, starved, uncovered or below takt, or about to stop (<= 15 min)
  2 Quality spill         defect patterns, trainees without sign-off at safety-critical stations, near-miss reports
  3 Shift hygiene         forecasts, cover planning, working-time and certification housekeeping

Each tier owns a 25-point band of the 0-100 score (tier 0: 75-100 ... tier 3: 0-25), so sorting by score always
respects the tiers. Within the band: severity weight + impact + ML risk x 20 + aging, scaled onto the band.
"""
from __future__ import annotations

from datetime import datetime

from ..models import Event, Incident
from ..state import FactoryState
from .fusion import LIVE_SAFETY_TYPES, REPORT_TYPES, TITLES

TIER_LABELS = ["Safety", "Line stoppage", "Quality spill", "Shift hygiene"]
BAND = 25

SEVERITY_WEIGHT = {"info": 0, "low": 10, "medium": 20, "high": 40, "critical": 60}
IMPACT_MAX = 20  # a fully stopped line, a spreading defect, or 10+ people exposed to a hazard
ML_WEIGHT = 20  # model risk (0-1) x 20
AGING_PER_MIN, AGING_MAX = 2, 20  # while active and waiting for a decision
HARD_RULE_BONUS = 100  # safety stop: top of the safety band
RAW_MAX = max(SEVERITY_WEIGHT.values()) + IMPACT_MAX + ML_WEIGHT + AGING_MAX

IMMINENT_MIN = 15  # a tool failure or part shortage this close counts as a line stoppage
BLOCKED_TYPES = {"station_stopped", "station_starved", "station_uncovered"}
DEFECTS_FOR_FULL_IMPACT = 4
REWORK_COST_FACTOR = 10  # a bad car caught at end of line costs ~10x more than one fixed in station


def _minutes(since: datetime, now: datetime) -> float:
    return (now - since).total_seconds() / 60


def minutes_left(e: Event, now: datetime) -> float | None:
    """Time until a predicted tool failure or part run-out, counted down since the prediction."""
    left = e.data.get("eta_min") if e.type == "predicted_tool_failure" else e.data.get("minutes_left")
    return None if left is None else max(0.0, left - _minutes(e.time, now))


def event_tier(e: Event, state: FactoryState) -> int:
    t = e.type
    if t in LIVE_SAFETY_TYPES or t == "fire_warden_gap" or e.data.get("hard_rule") == "safety_stop":
        return 0
    if t in BLOCKED_TYPES or t == "slowdown":
        return 1
    if t in ("predicted_tool_failure", "part_shortage"):
        left = minutes_left(e, state.now)
        return 1 if left is not None and left <= IMMINENT_MIN else 3
    if t == "defect_pattern" or t in REPORT_TYPES:
        return 2
    if t == "untrained_at_station" and e.station and state.layout.stations[e.station].safety_critical:
        return 2
    return 3


def _impact(e: Event, tier: int, state: FactoryState) -> float:
    """0-20: people exposed (safety), share of line output lost (stoppage), escape risk (quality)."""
    if tier == 0:
        return IMPACT_MAX * min(1.0, state.zone_headcount(e.zone) / 10)
    if tier == 1:
        if e.type in BLOCKED_TYPES:
            return IMPACT_MAX  # a serial line: one blocked station stops all output
        if e.type == "slowdown":
            slower = e.data.get("slower_pct", 0) / 100
            return IMPACT_MAX * min(1.0, slower / (1 + slower))  # share of cars lost at the slower pace
        return IMPACT_MAX * (1 - minutes_left(e, state.now) / IMMINENT_MIN)  # closer failure: more urgent
    if tier == 2:
        if e.type == "defect_pattern":
            if e.data.get("spread_risk"):
                return IMPACT_MAX
            return IMPACT_MAX * min(1.0, e.data.get("count", 1) / DEFECTS_FOR_FULL_IMPACT)
        if e.type == "untrained_at_station":
            return IMPACT_MAX / 2
    return 0.0


def _reason(e: Event, tier: int, state: FactoryState) -> str:
    """One short line a supervisor can read in two seconds: what, and what it costs."""
    where = e.station or f"zone {e.zone}"
    label = TITLES.get(e.type, e.type.replace("_", " ")).format(zone=e.zone, station=where)
    if tier == 0:
        return f"{label}: {state.zone_headcount(e.zone)} people in zone {e.zone}"
    if tier == 1:
        per_min = 60 / state.layout.takt_s
        if e.type in BLOCKED_TYPES:
            down = state.downtime_min.get(e.station, 0)
            return f"{label}: line losing ~{per_min:.0f} car/min, {down:.0f} min down so far"
        if e.type == "slowdown":
            return f"{label}: {e.data.get('slower_pct', 0):.0f}% slower, losing output every cycle"
        what = "tool expected to fail" if e.type == "predicted_tool_failure" else "parts run out"
        return f"{where}: {what} in ~{minutes_left(e, state.now):.0f} min, then the line stops"
    if e.type == "defect_pattern":
        n = e.data.get("count", 1)
        return f"{n} defects at {where} in 30 min: escapes cost ~{REWORK_COST_FACTOR}x at end-of-line rework"
    if e.type in ("predicted_tool_failure", "part_shortage"):
        left = minutes_left(e, state.now)
        what = "tool may fail" if e.type == "predicted_tool_failure" else "parts run out"
        return f"{where}: {what} in ~{left:.0f} min, plan it for the next break" if left is not None else label
    if e.data.get("model"):
        risk = next((line for line in e.evidence if not line.startswith("Report:")), "")  # the model's statement
        if e.type in REPORT_TYPES:
            return f"{label}; {risk}"
        if risk:
            return risk[0].upper() + risk[1:]
    return label


def assess(incident: Incident, events: list[Event], state: FactoryState, aging_min: float) -> dict:
    """Tier, score (0-100), the points behind it and a one-line reason."""
    tiers = {e.id: event_tier(e, state) for e in events}
    hard_rule = incident.recommendation is not None and incident.recommendation.hard_rule == "safety_stop"
    tier = 0 if hard_rule else min(tiers.values())
    lead_events = [e for e in events if tiers[e.id] == tier] or events
    impacts = {e.id: _impact(e, tier, state) for e in lead_events}
    lead = max(lead_events, key=lambda e: (impacts[e.id], e.severity.rank))
    parts = {
        "severity": SEVERITY_WEIGHT[incident.severity.value],
        "impact": round(impacts[lead.id], 1),
        "ml": round(ML_WEIGHT * max((e.confidence for e in events if e.data.get("model")), default=0.0), 1),
        "aging": min(AGING_MAX, AGING_PER_MIN * int(aging_min)),
        "hard_rule": HARD_RULE_BONUS if hard_rule else 0,
    }
    total = sum(parts.values())
    score = (3 - tier) * BAND + BAND * min(total, RAW_MAX) / RAW_MAX
    return {"tier": tier, "score": round(score, 1), "parts": {**parts, "total": round(total, 1)},
            "reason": _reason(lead, tier, state), "cause": lead.type}
