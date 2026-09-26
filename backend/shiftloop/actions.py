"""What happens when the supervisor decides: apply changes, open escalations, log everything."""
from __future__ import annotations

from datetime import timedelta

from .central.engine import CentralIntelligence
from .models import Assignment, Decision, Escalation, Incident
from .state import FactoryState

REMINDER_AFTER = timedelta(minutes=10)

# Impact assumptions (documented so the numbers can be challenged and replaced with plant data)
UNPLANNED_REPAIR_MIN = 25  # typical unplanned tool failure: diagnosis + repair while the line waits
PLANNED_SWAP_MIN = 5  # swap during a break or a gap
FAST_COVER_SAVED_MIN = 8  # time saved finding qualified cover vs. walking the floor
IDLE_KWH_PER_MIN = 1.5  # section energy drawn while stopped but not in standby
REWORK_CARS_PER_DEFECT = 2  # cars caught in-station instead of at end-of-line rework


def _apply(state: FactoryState, incident: Incident, a: Assignment) -> str:
    w = state.workers[a.worker]
    if a.kind == "station" and a.to_station:
        displaced = state.assign(w.id, a.to_station)
        note = f"; {state.workers[displaced].name} freed" if displaced else ""
        return f"{w.name} → {a.to_station}{note}"
    if a.kind == "relocate" and a.to_zone:
        state.move_zone(w.id, a.to_zone)
        if w.role == "maintenance":
            w.busy_with = incident.id
        return f"{w.name} → zone {a.to_zone} ({a.task})"
    w.busy_with = incident.id
    return f"{w.name}: {a.task}"


def _count_impact(state: FactoryState, central: CentralIntelligence, incident: Incident) -> None:
    types = {e.type: e for e in central.events_for(incident.id)}
    saved = 0.0
    if "predicted_tool_failure" in types and "station_stopped" not in types:
        saved += UNPLANNED_REPAIR_MIN - PLANNED_SWAP_MIN
    if "station_uncovered" in types:
        saved += FAST_COVER_SAVED_MIN
    if "defect_pattern" in types:
        state.impact["rework_avoided_cars"] += types["defect_pattern"].data.get("count", 1) * REWORK_CARS_PER_DEFECT
    state.impact["downtime_avoided_min"] += saved
    state.impact["energy_saved_kwh"] += saved * IDLE_KWH_PER_MIN


def decide(state: FactoryState, central: CentralIntelligence, incident_id: str, decision: str, reason: str = "",
           assignments: list[dict] | None = None) -> Decision:
    incident = state.incidents[incident_id]
    rec = incident.recommendation
    applied: list[str] = []
    if decision in ("accept", "modify"):
        chosen = rec.assignments if decision == "accept" or assignments is None else [
            Assignment(worker=a["worker"], worker_name=state.workers[a["worker"]].name,
                       kind=a.get("kind", "station" if a.get("to_station") else "relocate"),
                       to_station=a.get("to_station"), to_zone=a.get("to_zone"),
                       task=a.get("task", "supervisor's choice"), reason=reason)
            for a in assignments]
        applied = [_apply(state, incident, a) for a in chosen]
        for team in rec.escalations:
            message = incident.title if rec.summary == incident.title else f"{incident.title}: {rec.summary}"
            esc = Escalation(id=state.next_id("esc"), time=state.now, team=team, incident_id=incident.id,
                             message=message)
            state.escalations[esc.id] = esc
            applied.append(f"called {team}")
        incident.status = "accepted"
        _count_impact(state, central, incident)
    elif decision == "dismiss":
        incident.status = "dismissed"
    else:
        raise ValueError(f"unknown decision {decision!r}")
    d = Decision(id=state.next_id("dec"), time=state.now, incident_id=incident.id, incident_title=incident.title,
                 recommended=rec.summary if rec else "", decision=decision, reason=reason, applied=applied,
                 agents=sorted(incident.agents))
    state.decisions.append(d)
    central.rerank(state)
    return d


def acknowledge_escalation(state: FactoryState, escalation_id: str) -> Escalation:
    esc = state.escalations[escalation_id]
    esc.acknowledged_at = state.now
    return esc


def check_escalations(state: FactoryState) -> list[str]:
    """Remind about escalations nobody confirmed. Returns the ids that got a reminder."""
    reminded = []
    for esc in state.escalations.values():
        if esc.acknowledged_at is not None:
            continue
        incident = state.incidents.get(esc.incident_id)
        if incident is not None and incident.status in ("resolved", "dismissed"):
            continue
        since = esc.last_reminder or esc.time
        if state.now - since >= REMINDER_AFTER:
            esc.reminders += 1
            esc.last_reminder = state.now
            waited = int((state.now - esc.time).total_seconds() // 60)
            state.notify("warning", f"No confirmation from {esc.team} after {waited} min",
                         esc.message, esc.incident_id)
            reminded.append(esc.id)
    return reminded


def release_resolved(state: FactoryState) -> None:
    for w in state.workers.values():
        if w.busy_with:
            inc = state.incidents.get(w.busy_with)
            if inc is not None and inc.status in ("resolved", "dismissed"):
                w.busy_with = None


def all_clear(state: FactoryState) -> dict:
    """Supervisor ends the emergency. Returns the restart plan."""
    em = state.emergency
    if em is None:
        raise ValueError("no emergency in progress")
    minutes = int((state.now - em.started).total_seconds() // 60)
    cars = round(minutes * 60 / state.layout.takt_s)
    people = [w for w in state.present() if w.zone == em.zone]
    steps = [
        f"Fire wardens confirm zone {em.zone} is safe and exits are clear",
        f"{len(people)} people return to their stations in zone {em.zone}",
        f"Restart zone {em.zone} first, then bring the upstream zone back to normal speed",
        f"Recover {cars} cars: about {minutes} min of extra running; check working-time limits before overtime",
        "Record the event for EHS and hand it over to the next shift",
    ]
    incident = state.incidents.get(em.incident_id)
    if incident is not None and incident.status in ("open", "accepted"):
        incident.status = "resolved"
        incident.visibility = "held"
    state.decisions.append(Decision(
        id=state.next_id("dec"), time=state.now, incident_id=em.incident_id, incident_title=em.reason,
        recommended=f"All clear for zone {em.zone} and restart", decision="accept", applied=steps,
        agents=["safety"]))
    state.emergency = None
    state.notify("info", f"All clear in zone {em.zone}", f"Restart plan: recover {cars} cars", em.incident_id)
    return {"zone": em.zone, "duration_min": minutes, "cars_to_recover": cars, "steps": steps}
