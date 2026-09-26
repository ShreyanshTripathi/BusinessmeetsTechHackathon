from datetime import timedelta

import pytest

from shiftloop.actions import (
    acknowledge_escalation,
    all_clear,
    check_escalations,
    decide,
    release_resolved,
)
from shiftloop.central.engine import CentralIntelligence
from shiftloop.models import Event, Severity, StaffingChange
from shiftloop.state import FactoryState


def ev(state, agent, type_, zone, station=None, severity="high", data=None, key=None):
    return Event(id=state.next_id("evt"), agent=agent, time=state.now, zone=zone, station=station, type=type_,
                 severity=Severity(severity), key=key or f"{agent}:{type_}:{station or zone}", data=data or {},
                 evidence=[f"{type_} evidence"])


@pytest.fixture
def uncovered():
    state, central = FactoryState.create(), CentralIntelligence()
    absent = state.station_occupant("S12")
    state.apply_staffing(StaffingChange(time=state.now, worker=absent.id, change="absent"))
    central.ingest(state, [ev(state, "staffing", "station_uncovered", "B", "S12", data={"candidates": []})])
    return state, central, central.open_incidents(state)[0]


def test_accept_applies_assignment_and_logs_decision(uncovered):
    state, central, inc = uncovered
    worker_id = inc.recommendation.assignments[0].worker
    d = decide(state, central, inc.id, "accept")
    assert state.station_occupant("S12").id == worker_id
    assert inc.status == "accepted"
    assert d.decision == "accept" and d.applied and state.decisions == [d]
    assert d.agents == ["staffing"]


def test_dismiss_changes_nothing_but_records_reason(uncovered):
    state, central, inc = uncovered
    d = decide(state, central, inc.id, "dismiss", reason="team lead covers it")
    assert state.station_occupant("S12") is None
    assert inc.status == "dismissed" and d.reason == "team lead covers it" and d.applied == []


def test_modify_applies_supervisor_choice_instead(uncovered):
    state, central, inc = uncovered
    other = next(w for w in state.workers.values()
                 if w.role == "floater" and w.home_zone == "B" and w.id != inc.recommendation.assignments[0].worker)
    d = decide(state, central, inc.id, "modify", reason="prefer this person",
               assignments=[{"worker": other.id, "to_station": "S12"}])
    assert state.station_occupant("S12").id == other.id
    assert d.decision == "modify"


def test_unknown_incident_raises():
    state, central = FactoryState.create(), CentralIntelligence()
    with pytest.raises(KeyError):
        decide(state, central, "inc_9999", "accept")


def _stopped(state, central):
    central.ingest(state, [ev(state, "assembly", "station_stopped", "B", "S12", key="assembly:S12:status")])
    return central.open_incidents(state)[0]


def test_accept_creates_escalation_and_marks_technician_busy():
    state, central = FactoryState.create(), CentralIntelligence()
    inc = _stopped(state, central)
    decide(state, central, inc.id, "accept")
    esc = next(e for e in state.escalations.values() if e.team == "maintenance")
    assert esc.acknowledged_at is None and esc.incident_id == inc.id
    tech = state.workers[inc.recommendation.assignments[0].worker]
    assert tech.busy_with == inc.id


def test_unacknowledged_escalation_sends_reminders_until_acknowledged():
    state, central = FactoryState.create(), CentralIntelligence()
    inc = _stopped(state, central)
    decide(state, central, inc.id, "accept")
    esc = next(iter(state.escalations.values()))
    state.advance(timedelta(minutes=5))
    assert check_escalations(state) == []
    state.advance(timedelta(minutes=6))
    reminded = check_escalations(state)
    assert reminded == [esc.id] and esc.reminders == 1
    assert any("maintenance" in n.title.lower() and n.level == "warning" for n in state.notifications)
    acknowledge_escalation(state, esc.id)
    state.advance(timedelta(minutes=30))
    assert check_escalations(state) == []


def test_resolved_incident_frees_busy_workers():
    state, central = FactoryState.create(), CentralIntelligence()
    inc = _stopped(state, central)
    decide(state, central, inc.id, "accept")
    tech_id = inc.recommendation.assignments[0].worker
    central.ingest(state, [ev(state, "assembly", "station_stopped", "B", "S12", key="assembly:S12:status")
                           .model_copy(update={"cleared": True})])
    release_resolved(state)
    assert state.workers[tech_id].busy_with is None


def test_planned_tool_swap_counts_avoided_downtime():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "predicted_tool_failure", "B", "S12", data={"eta_min": 200})])
    inc = central.open_incidents(state)[0]
    decide(state, central, inc.id, "accept")
    assert state.impact["downtime_avoided_min"] > 0


def test_all_clear_ends_emergency_and_returns_restart_plan():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "safety", "fire_confirmed", "C", None, "critical",
                              {"emergency": True, "hard_rule": "safety_stop"}, key="safety:C:fire")])
    assert state.emergency is not None
    state.advance(timedelta(minutes=10))
    plan = all_clear(state)
    assert state.emergency is None
    assert plan["zone"] == "C" and plan["duration_min"] == 10
    assert plan["cars_to_recover"] == 10  # 10 minutes at 60 s takt
    assert any("zone C" in s for s in plan["steps"])
    assert state.decisions[-1].decision == "accept" and "all clear" in state.decisions[-1].recommended.lower()


def test_all_clear_without_emergency_raises():
    with pytest.raises(ValueError):
        all_clear(FactoryState.create())


def _uncovered(state):
    return {s for s in state.layout.stations if state.station_occupant(s) is None}


def test_accepting_a_recommendation_never_opens_a_new_gap():
    """Moving someone off their own station must come with a backfill, or not happen."""
    state, central = FactoryState.create(), CentralIntelligence()
    # nobody free: every floater is busy, so cover would have to come from another station
    for w in state.workers.values():
        if w.role == "floater":
            w.busy_with = "elsewhere"
    s09 = state.station_occupant("S09")
    s09.qualifications["S09"] = 1
    central.ingest(state, [ev(state, "staffing", "untrained_at_station", "B", "S09", "medium",
                              {"level": 1, "candidates": []})])
    before = _uncovered(state)
    decide(state, central, central.open_incidents(state)[0].id, "accept")
    assert _uncovered(state) <= before


def test_cover_from_another_station_brings_a_backfill():
    state, central = FactoryState.create(), CentralIntelligence()
    absent = state.station_occupant("S12")
    state.apply_staffing(StaffingChange(time=state.now, worker=absent.id, change="absent"))
    # the only free people are not qualified on S12, but can backfill elsewhere
    for w in state.workers.values():
        if w.role == "floater" and w.qualifications.get("S12", 0) >= 2:
            w.busy_with = "elsewhere"
    central.ingest(state, [ev(state, "staffing", "station_uncovered", "B", "S12", data={"candidates": []})])
    inc = central.open_incidents(state)[0]
    decide(state, central, inc.id, "accept")
    assert _uncovered(state) <= {"S12"}


def test_escalation_message_does_not_repeat_the_title():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "predicted_tool_failure", "B", "S12", data={"eta_min": 200})])
    inc = central.open_incidents(state)[0]
    decide(state, central, inc.id, "accept")
    msg = next(iter(state.escalations.values())).message
    assert msg.count(inc.title) == 1
