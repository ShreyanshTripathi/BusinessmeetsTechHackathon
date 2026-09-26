from datetime import datetime, timedelta

from shiftloop.central.engine import CentralIntelligence
from shiftloop.models import Event, Severity
from shiftloop.state import FactoryState

T0 = datetime(2026, 10, 1, 6, 0)


def ev(state, agent, type_, zone, station=None, severity="high", data=None, key=None, cleared=False, evidence=None):
    return Event(id=state.next_id("evt"), agent=agent, time=state.now, zone=zone, station=station, type=type_,
                 severity=Severity(severity), key=key or f"{agent}:{type_}:{station or zone}", cleared=cleared,
                 data=data or {}, evidence=evidence or [f"{type_} evidence"])


def test_single_event_opens_an_incident_with_a_recommendation():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "station_stopped", "B", "S12")])
    inc = central.open_incidents(state)[0]
    assert inc.stations == ["S12"] and inc.category == "production"
    assert inc.recommendation is not None
    assert "maintenance" in inc.recommendation.escalations
    assert inc.recommendation.assignments, "should name a maintenance technician"


def test_events_at_same_station_merge_into_one_incident():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "defect_pattern", "B", "S09", "medium", {"count": 2, "spread_risk": False})])
    state.advance(timedelta(minutes=3))
    central.ingest(state, [ev(state, "staffing", "untrained_at_station", "B", "S09", "medium", {"level": 1, "candidates": []})])
    incs = central.open_incidents(state)
    assert len(incs) == 1
    assert sorted(incs[0].agents) == ["assembly", "staffing"]
    assert "trainee" in (incs[0].likely_cause or "").lower() or "method" in (incs[0].likely_cause or "").lower()


def test_tool_drift_plus_defects_points_to_the_tool_not_the_operator():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [
        ev(state, "assembly", "predicted_tool_failure", "B", "S12", "high", {"eta_min": 40}),
        ev(state, "assembly", "defect_pattern", "B", "S12", "medium", {"count": 2, "spread_risk": False}),
    ])
    inc = central.open_incidents(state)[0]
    assert "tool" in inc.likely_cause.lower()


def test_new_finding_at_station_with_ongoing_incident_merges_even_much_later():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "staffing", "untrained_at_station", "B", "S09", "medium", {"level": 1, "candidates": []})])
    state.advance(timedelta(minutes=45))
    central.ingest(state, [ev(state, "assembly", "defect_pattern", "B", "S09", "medium", {"count": 2, "spread_risk": False})])
    assert len(central.open_incidents(state)) == 1


def test_events_after_incident_resolved_open_a_new_incident():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "part_shortage", "B", "S10", "medium", {"part": "bolts", "minutes_left": 20})])
    central.ingest(state, [ev(state, "assembly", "part_shortage", "B", "S10", "medium", cleared=True)])
    central.ingest(state, [ev(state, "assembly", "slowdown", "B", "S10", "medium", key="assembly:slow:S10")])
    assert len(central.open_incidents(state)) == 1
    assert len(state.incidents) == 2


def test_new_finding_reopens_an_accepted_incident():
    from shiftloop.actions import decide
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "staffing", "untrained_at_station", "B", "S09", "medium", {"level": 1, "candidates": []})])
    inc = central.open_incidents(state)[0]
    decide(state, central, inc.id, "accept")
    central.ingest(state, [ev(state, "assembly", "defect_pattern", "B", "S09", "medium", {"count": 2, "spread_risk": False})])
    assert inc.status == "open"


def test_safety_events_merge_by_zone():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "safety", "possible_fire", "C", None, "high", {"needs_verification": True}, key="safety:C:fire")])
    central.ingest(state, [ev(state, "safety", "battery_overheating", "C", "S18", "high", {"temp_c": 44}, key="safety:C:battery:S18")])
    incs = central.open_incidents(state)
    assert len(incs) == 1 and incs[0].category == "safety"


def test_safety_always_ranks_first_and_attention_budget_is_three():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [
        ev(state, "assembly", "station_stopped", "A", "S02"),
        ev(state, "assembly", "part_shortage", "B", "S10", "high", {"part": "bolts", "minutes_left": 5}),
        ev(state, "staffing", "station_uncovered", "D", "S20", "high", {"candidates": []}),
        ev(state, "assembly", "slowdown", "D", "S23", "medium"),
        ev(state, "safety", "ppe_missing", "C", None, "medium", key="safety:C:ppe"),
    ])
    incs = central.open_incidents(state)
    assert incs[0].category == "safety"
    active = [i for i in incs if i.visibility == "active"]
    held = [i for i in incs if i.visibility == "held"]
    assert len(active) == 3 and len(held) == 2
    assert all(a.score >= h.score for a in active for h in held)


def test_fire_confirmed_recommends_emergency_with_headcount_and_wardens():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "safety", "fire_confirmed", "C", None, "critical",
                              {"emergency": True, "hard_rule": "safety_stop"}, key="safety:C:fire")])
    inc = central.open_incidents(state)[0]
    rec = inc.recommendation
    assert rec.action == "emergency" and rec.scope == "zone" and rec.target == "C"
    assert rec.hard_rule == "safety_stop"
    text = " ".join(rec.steps)
    assert "people" in text and "warden" in text.lower()
    assert any("slow" in s.lower() and "zone B" in s for s in rec.steps), "upstream zone should slow"
    assert state.emergency is not None and state.emergency.zone == "C"
    assert any(n.level == "critical" for n in state.notifications)


def test_defect_with_spread_risk_triggers_quality_stop_rule():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "defect_pattern", "B", "S09", "high", {"count": 3, "spread_risk": True})])
    rec = central.open_incidents(state)[0].recommendation
    assert rec.action == "stop" and rec.hard_rule == "quality_spread"


def test_uncovered_station_recommends_best_candidate():
    state, central = FactoryState.create(), CentralIntelligence()
    cand = {"worker_id": "W026", "name": "X", "zone": "B", "score": 40, "reason": "qualified on S12, free",
            "level": 3, "current_station": None}
    central.ingest(state, [ev(state, "staffing", "station_uncovered", "B", "S12", "high", {"candidates": [cand]})])
    rec = central.open_incidents(state)[0].recommendation
    assert rec.assignments[0].worker == "W026" and rec.assignments[0].to_station == "S12"


def test_fire_warden_gap_recommends_moving_a_donor():
    state, central = FactoryState.create(), CentralIntelligence()
    donor = state.fire_wardens("A")[0]
    d = {"worker_id": donor.id, "name": donor.name, "zone": "A", "score": 7, "reason": "fire warden",
         "level": 0, "current_station": donor.station}
    central.ingest(state, [ev(state, "staffing", "fire_warden_gap", "B", None, "high", {"donors": [d]}, key="staffing:warden:B")])
    rec = central.open_incidents(state)[0].recommendation
    moves = {a.worker: a for a in rec.assignments}
    assert moves[donor.id].to_zone == "B"
    # the donor's station gets a backfill
    assert any(a.to_station == donor.station for a in rec.assignments if a.worker != donor.id)


def test_cleared_events_resolve_incident_when_nothing_is_left():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "station_stopped", "B", "S12", key="assembly:S12:status")])
    central.ingest(state, [ev(state, "assembly", "station_stopped", "B", "S12", key="assembly:S12:status", cleared=True)])
    assert central.open_incidents(state) == []
    assert list(state.incidents.values())[0].status == "resolved"


def test_signals_held_back_counts_everything_not_shown():
    state, central = FactoryState.create(), CentralIntelligence()
    state.signals = 400
    central.ingest(state, [ev(state, "assembly", "station_stopped", "B", "S12")])
    summary = central.attention_summary(state)
    assert summary["signals"] == 400 and summary["active"] == 1
    assert summary["held_back"] == 399


def test_low_severity_incidents_never_take_an_inbox_slot():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "staffing", "qualification_expiring", "D", "S20", "low")])
    assert central.open_incidents(state)[0].visibility == "held"


def test_alerts_carry_a_code_and_a_spoken_phrase():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "safety", "possible_fire", "C", None, "high", {"needs_verification": True}, key="safety:C:fire")])
    central.ingest(state, [ev(state, "safety", "battery_overheating", "C", "S18", "critical", {"temp_c": 61}, key="safety:C:battery:S18")])
    n = state.notifications[-1]
    assert n.level == "critical" and n.code == "S-C18"
    assert n.spoken.startswith("Battery overheating at station 18 and possible fire")
    assert "+" not in n.spoken and n.spoken.endswith(".")
    inc = central.open_incidents(state)[0]
    assert inc.likely_cause == "Battery pack overheating at S18 is the likely source of the smoke"


def test_zone_wide_alert_code_has_no_station():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "staffing", "fire_warden_gap", "B", None, "high", {"donors": []}, key="staffing:warden:B")])
    assert state.notifications[-1].code == "W-B"
