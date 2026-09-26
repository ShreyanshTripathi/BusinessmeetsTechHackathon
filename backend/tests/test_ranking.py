"""Priority tiers, the banded score, aging, slot stability and priority over time."""
from datetime import datetime, time, timedelta

from shiftloop.central.engine import CentralIntelligence
from shiftloop.models import Event, Severity
from shiftloop.oversight import oversight_report
from shiftloop.plant import Plant
from shiftloop.state import FactoryState


def ev(state, agent, type_, zone, station=None, severity="high", data=None, key=None, confidence=1.0):
    return Event(id=state.next_id("evt"), agent=agent, time=state.now, zone=zone, station=station, type=type_,
                 severity=Severity(severity), confidence=confidence, key=key or f"{agent}:{type_}:{station or zone}",
                 data=data or {}, evidence=[f"{type_} evidence"])


def minutes(state, central, n):
    for _ in range(n):
        state.advance(timedelta(minutes=1))
        central.rerank(state)


def by_type(central, state):
    return {central.events_for(i.id)[0].type: i for i in state.incidents.values()}


def test_tiers_are_strict_and_each_owns_a_score_band():
    state, central = FactoryState.create(), CentralIntelligence(attention_budget=10)
    central.ingest(state, [
        ev(state, "staffing", "working_time_limit", "D", "S20", "high", {"worker_id": "W001"}),
        ev(state, "assembly", "defect_pattern", "B", "S09", "high", {"count": 3, "spread_risk": True}),
        ev(state, "assembly", "slowdown", "A", "S03", "medium", {"slower_pct": 12}),
        ev(state, "safety", "ppe_missing", "C", None, "medium", key="safety:C:ppe"),
    ])
    incs = by_type(central, state)
    assert [incs[t].tier for t in ("ppe_missing", "slowdown", "defect_pattern", "working_time_limit")] == [0, 1, 2, 3]
    for inc in incs.values():
        assert (3 - inc.tier) * 25 <= inc.score <= (4 - inc.tier) * 25
    ranked = [central.events_for(i.id)[0].type for i in central.open_incidents(state)]
    assert ranked == ["ppe_missing", "slowdown", "defect_pattern", "working_time_limit"]


def test_fire_warden_gap_outranks_a_stopped_line_and_safety_stop_takes_the_top():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "station_stopped", "B", "S12"),
                           ev(state, "staffing", "fire_warden_gap", "A", None, "high", {"donors": []},
                              key="staffing:warden:A")])
    central.ingest(state, [ev(state, "safety", "gas_alarm", "D", None, "critical",
                              {"value": 60, "hard_rule": "safety_stop"}, key="safety:D:gas")])
    ranked = [central.events_for(i.id)[0].type for i in central.open_incidents(state)]
    assert ranked == ["gas_alarm", "fire_warden_gap", "station_stopped"]
    assert central.open_incidents(state)[0].score == 100


def test_score_parts_follow_the_formula():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "staffing", "cover_risk", "C", "S13", "medium",
                              {"model": "staffing_model"}, confidence=0.85)])
    inc = central.open_incidents(state)[0]
    assert inc.score_parts == {"severity": 20, "impact": 0.0, "ml": 17.0, "aging": 0, "hard_rule": 0, "total": 37.0}
    assert inc.score == round(25 * 37 / 120, 1)  # tier 3 band: 0-25


def test_stopped_station_reason_states_the_line_loss():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "station_stopped", "B", "S12")])
    minutes(state, central, 1)
    state.downtime_min["S12"] = 7
    central.rerank(state)
    inc = central.open_incidents(state)[0]
    assert inc.tier == 1 and inc.priority_cause == "station_stopped"
    assert inc.priority_reason == "S12 stopped: line losing ~1 car/min, 7 min down so far"


def test_tool_failure_counts_down_into_the_line_stoppage_tier():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "predicted_tool_failure", "B", "S12", "high", {"eta_min": 40},
                              key="assembly:S12:torque")])
    inc = central.open_incidents(state)[0]
    assert inc.tier == 3 and "next break" in inc.priority_reason
    minutes(state, central, 26)
    assert inc.tier == 1 and "~14 min" in inc.priority_reason
    assert [p.change for p in inc.history if p.change != "score"] == ["opened", "tier_up"]
    assert inc.trend == "rising"


def test_unacted_active_incident_ages_until_the_cap_and_accepting_resets_it():
    plant = Plant(scenario="quiet")
    state, central = plant.state, plant.central
    central.ingest(state, [ev(state, "assembly", "part_shortage", "D", "S22", "medium",
                              {"part": "fasteners", "minutes_left": 25, "units": 25})])
    inc = central.open_incidents(state)[0]
    start = inc.score
    minutes(state, central, 5)
    assert inc.waiting_min == 5 and inc.score_parts["aging"] == 10 and inc.score > start
    minutes(state, central, 20)
    assert inc.score_parts["aging"] == 20  # capped
    plant.decide(inc.id, "accept")
    assert inc.status == "accepted" and inc.waiting_since is None and inc.visibility == "held"
    assert inc.history[-1].change == "accepted"


def test_active_slots_do_not_flicker_between_close_scores():
    state, central = FactoryState.create(), CentralIntelligence(attention_budget=1)
    central.ingest(state, [ev(state, "assembly", "slowdown", "A", "S03", "medium", {"slower_pct": 10})])
    first = central.open_incidents(state)[0]
    assert first.visibility == "active"
    central.ingest(state, [ev(state, "assembly", "slowdown", "B", "S08", "medium", {"slower_pct": 14})])
    second = next(i for i in state.incidents.values() if i.id != first.id)
    assert second.score > first.score and second.score - first.score < 5
    assert first.visibility == "active" and second.visibility == "held"
    # a higher tier always takes the slot
    central.ingest(state, [ev(state, "safety", "exit_blocked", "D", None, "high", key="safety:D:exit")])
    assert [i.visibility for i in (first, second)] == ["held", "held"]


def test_held_incident_is_promoted_when_it_deteriorates():
    state, central = FactoryState.create(), CentralIntelligence(attention_budget=1)
    central.ingest(state, [ev(state, "assembly", "slowdown", "A", "S03", "medium", {"slower_pct": 10})])
    shortage = lambda sev, left: ev(state, "assembly", "part_shortage", "D", "S22", sev,
                                    {"part": "fasteners", "minutes_left": left}, key="assembly:S22:stock:fasteners")
    central.ingest(state, [shortage("medium", 25)])
    parts = next(i for i in state.incidents.values() if "S22" in i.stations)
    assert parts.tier == 3 and parts.visibility == "held"
    minutes(state, central, 1)
    central.ingest(state, [shortage("high", 2)])  # stock nearly gone: the agent re-emits at higher severity
    assert parts.tier == 1 and parts.visibility == "active"
    assert [p.change for p in parts.history] == ["opened", "tier_up"]
    slow = next(i for i in state.incidents.values() if "S03" in i.stations)
    assert slow.visibility == "held" and slow.history[-1].change == "demoted"


def test_safety_claims_the_slot_even_at_medium_severity():
    state, central = FactoryState.create(), CentralIntelligence(attention_budget=1)
    central.ingest(state, [ev(state, "assembly", "station_stopped", "A", "S02")])
    central.ingest(state, [ev(state, "safety", "high_heat", "C", None, "medium", key="safety:C:heat")])
    assert [(i.tier, i.visibility) for i in central.open_incidents(state)] == [(0, "active"), (1, "held")]


def test_demo_shift_priority_history_is_reproducible_and_timed_in_oversight():
    def run():
        plant = Plant(scenario="demo", seed=7)
        plant.step(1)
        for inc in list(plant.central.open_incidents(plant.state)):
            plant.decide(inc.id, "accept")
        plant.run_until(datetime.combine(plant.state.now.date(), time(10, 20)))
        return plant
    a, b = run(), run()
    history = lambda p: [(i.id, h.time, h.change, h.score) for i in p.state.incidents.values() for h in i.history]
    assert history(a) == history(b)
    report = oversight_report(a.state, a.central)["priority"]
    assert report["decisions_timed"] > 0 and report["avg_minutes_active_to_decision"] is not None
    assert report["counts"].get("tier_up", 0) >= 1  # the worn tool at S12 counts down into tier 1
