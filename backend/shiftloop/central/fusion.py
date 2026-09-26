"""Merge related events into incidents and explain what connects them."""
from __future__ import annotations

from datetime import timedelta

from ..models import Event, Incident

SAFETY_ZONE_WINDOW = timedelta(minutes=30)

LIVE_SAFETY_TYPES = {"fire_confirmed", "possible_fire", "battery_overheating", "gas_alarm", "high_heat",
                     "exit_blocked", "ppe_missing"}
REPORT_TYPES = {"near_miss_rated", "near_miss_unsure"}  # something that already happened, rated by the safety model
SAFETY_TYPES = LIVE_SAFETY_TYPES | REPORT_TYPES
QUALITY_TYPES = {"defect_pattern", "inspection_unsure"}
STAFFING_TYPES = {"station_uncovered", "untrained_at_station", "fire_warden_gap", "first_aider_gap",
                  "working_time_limit", "qualification_expiring", "cover_risk"}

CATEGORY_ORDER = ["safety", "quality", "production", "staffing"]


def category_of(event: Event) -> str:
    if event.type in SAFETY_TYPES:
        return "safety"
    if event.type in QUALITY_TYPES:
        return "quality"
    if event.type in STAFFING_TYPES:
        return "staffing"
    return "production"


def merged_category(events: list[Event]) -> str:
    cats = {category_of(e) for e in events}
    return next(c for c in CATEGORY_ORDER if c in cats)


def belongs_to(event: Event, incident: Incident, events: list[Event]) -> bool:
    """Should `event` join `incident` (whose active events are `events`)?"""
    if event.key in incident.event_keys:
        return True
    if event.type in REPORT_TYPES:
        return False  # each report is its own case
    age = event.time - incident.updated
    if category_of(event) == "safety":
        return (incident.category == "safety" and incident.zone == event.zone and age <= SAFETY_ZONE_WINDOW
                and not any(k.startswith("safety:report:") for k in incident.event_keys))
    # a live incident means its conditions are still ongoing, so new findings at the station are connected
    if event.station and event.station in incident.stations:
        return incident.category != "safety"
    return False


def likely_cause(events: list[Event]) -> str | None:
    types = {e.type for e in events}
    station = next((e.station for e in events if e.station), None)
    if "battery_overheating" in types and types & {"possible_fire", "fire_confirmed"}:
        return "Battery pack overheating at S18 is the likely source of the smoke"
    if "predicted_tool_failure" in types and "defect_pattern" in types:
        return f"Defects started with torque drift at {station}: likely the tool, not the operator"
    if "untrained_at_station" in types and "defect_pattern" in types:
        return f"A trainee runs {station} and tool data is normal: likely method/training, not the machine"
    if "untrained_at_station" in types and "slowdown" in types:
        return f"Slowdown at {station} matches a trainee's pace: pair with a qualified buddy"
    if "station_uncovered" in types and types & {"station_stopped", "station_starved", "slowdown"}:
        return f"{station} is not staffed"
    if "part_shortage" in types and types & {"station_starved", "slowdown"}:
        return f"Parts are running out at {station}"
    if "predicted_tool_failure" in types and "station_stopped" in types:
        return f"The worn tool at {station} has failed"
    return None


TITLES = {
    "fire_confirmed": "Fire confirmed in zone {zone}",
    "possible_fire": "Possible fire in zone {zone}",
    "battery_overheating": "Battery overheating at {station}",
    "gas_alarm": "Gas alarm in zone {zone}",
    "high_heat": "High heat in zone {zone}",
    "exit_blocked": "Emergency exit blocked in zone {zone}",
    "ppe_missing": "Protective equipment missing in zone {zone}",
    "defect_pattern": "Repeated defects at {station}",
    "inspection_unsure": "Inspection needs expert review at {station}",
    "predicted_tool_failure": "Tool failure predicted at {station}",
    "station_stopped": "{station} stopped",
    "station_starved": "{station} waiting for parts or cars",
    "slowdown": "{station} running slower than takt",
    "part_shortage": "Parts running out at {station}",
    "station_uncovered": "{station} has no operator",
    "untrained_at_station": "Trainee without sign-off at {station}",
    "fire_warden_gap": "No fire warden in zone {zone}",
    "first_aider_gap": "No first aider in zone {zone}",
    "working_time_limit": "Working-time limit approaching",
    "qualification_expiring": "Qualification expiring at {station}",
    "cover_risk": "{station} may lose qualified cover this shift",
    "output_target_risk": "Zone {zone} may miss its output target",
    "near_miss_rated": "Near-miss report at {station}",
    "near_miss_unsure": "Near-miss report needs an expert rating at {station}",
}


def title_for(events: list[Event]) -> str:
    lead = max(events, key=lambda e: (category_of(e) == "safety", e.severity.rank))
    title = TITLES.get(lead.type, lead.type.replace("_", " ")).format(zone=lead.zone, station=lead.station or lead.zone)
    extra = {e.type for e in events if e.type != lead.type}
    if extra:
        title += " + " + ", ".join(sorted(t.replace("_", " ") for t in extra))
    return title
