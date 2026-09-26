from datetime import datetime

from shiftloop.agents.staffing import StaffingAgent
from shiftloop.models import StaffingChange
from shiftloop.state import FactoryState

T0 = datetime(2026, 10, 1, 6, 0)


def _absent(state, worker_id):
    state.apply_staffing(StaffingChange(time=T0, worker=worker_id, change="absent"))


def _types(events):
    return sorted((e.type, e.station or e.zone) for e in events)


def test_initial_shift_only_reports_the_expiring_qualification():
    state = FactoryState.create()
    events = StaffingAgent().tick(state)
    assert _types(events) == [("qualification_expiring", "S20")]
    assert events[0].severity.value == "low"


def test_absence_creates_uncovered_station_with_cover_suggestions():
    state, agent = FactoryState.create(), StaffingAgent()
    agent.tick(state)
    _absent(state, state.station_occupant("S12").id)
    events = agent.tick(state)
    ev = next(e for e in events if e.type == "station_uncovered")
    assert ev.station == "S12" and ev.zone == "B" and ev.severity.value == "high"
    assert ev.data["candidates"], "should suggest qualified cover"
    assert ev.agent == "staffing"


def test_conditions_are_not_re_emitted_while_they_persist():
    state, agent = FactoryState.create(), StaffingAgent()
    _absent(state, state.station_occupant("S12").id)
    first = agent.tick(state)
    assert any(e.type == "station_uncovered" for e in first)
    assert agent.tick(state) == []


def test_covering_the_station_clears_the_condition():
    state, agent = FactoryState.create(), StaffingAgent()
    _absent(state, state.station_occupant("S12").id)
    ev = next(e for e in agent.tick(state) if e.type == "station_uncovered")
    state.assign(ev.data["candidates"][0]["worker_id"], "S12")
    cleared = agent.tick(state)
    assert [(e.type, e.cleared) for e in cleared] == [("station_uncovered", True)]


def test_missing_fire_warden_in_zone_is_high_severity():
    state, agent = FactoryState.create(), StaffingAgent()
    agent.tick(state)
    warden_b = state.fire_wardens("B")[0]
    _absent(state, warden_b.id)
    events = agent.tick(state)
    gap = next(e for e in events if e.type == "fire_warden_gap")
    assert gap.zone == "B" and gap.severity.value == "high"
    assert gap.data["donors"], "should suggest a warden from a zone with a spare"


def test_missing_first_aider_is_medium():
    state, agent = FactoryState.create(), StaffingAgent()
    agent.tick(state)
    for w in state.first_aiders("D"):
        _absent(state, w.id)
    gap = next(e for e in agent.tick(state) if e.type == "first_aider_gap")
    assert gap.zone == "D" and gap.severity.value == "medium"


def test_trainee_at_station_is_medium_and_untrained_is_high():
    state, agent = FactoryState.create(), StaffingAgent()
    agent.tick(state)
    op = state.station_occupant("S09")
    op.qualifications["S09"] = 1
    ev = next(e for e in agent.tick(state) if e.type == "untrained_at_station")
    assert ev.station == "S09" and ev.severity.value == "medium"
    op.qualifications["S09"] = 0
    ev = next(e for e in agent.tick(state) if e.type == "untrained_at_station")
    assert ev.severity.value == "high", "severity escalation is re-emitted"


def test_trainee_at_safety_critical_station_is_high():
    state, agent = FactoryState.create(), StaffingAgent()
    agent.tick(state)
    state.station_occupant("S18").qualifications["S18"] = 1
    ev = next(e for e in agent.tick(state) if e.type == "untrained_at_station")
    assert ev.severity.value == "high"


def test_working_time_limits():
    state, agent = FactoryState.create(), StaffingAgent()
    agent.tick(state)
    w = state.station_occupant("S05")
    w.hours_worked = 9.6
    ev = next(e for e in agent.tick(state) if e.type == "working_time_limit")
    assert ev.severity.value == "medium"
    w.hours_worked = 10.1
    ev = next(e for e in agent.tick(state) if e.type == "working_time_limit")
    assert ev.severity.value == "high"
