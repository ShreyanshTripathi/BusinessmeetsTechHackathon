"""End-to-end: simulator → agents → central intelligence, following the demo shift."""
from datetime import datetime, time

import pytest

from shiftloop.models import VisionDetection
from shiftloop.plant import Plant


def at(plant, hh, mm):
    target = datetime.combine(plant.state.now.date(), time(hh, mm))
    plant.run_until(target)


def open_types(plant):
    return {(e.type, e.station or e.zone) for i in plant.central.open_incidents(plant.state)
            for e in plant.central.events_for(i.id)}


def accept_all(plant, predicate=lambda inc: True):
    for inc in list(plant.central.open_incidents(plant.state)):
        if predicate(inc):
            plant.decide(inc.id, "accept")


# ------------------------------------------------------------------ quiet shift


def test_quiet_shift_generates_signals_but_no_urgent_incidents():
    plant = Plant(scenario="quiet")
    plant.step(60)
    assert plant.state.signals > 60 * 30
    urgent = [i for i in plant.central.open_incidents(plant.state) if i.severity.rank >= 3]
    assert urgent == [], [i.title for i in urgent]
    assert plant.state.cars_built == pytest.approx(60, abs=1)


def test_quiet_shifts_raise_no_tool_failure_false_alarms():
    for seed in (1, 3, 42):  # seeds whose torque noise used to trip the drift check
        plant = Plant(scenario="quiet", seed=seed)
        at(plant, 14, 0)
        assert not [e for e in plant.state.events if e.type == "predicted_tool_failure"], seed


def test_same_seed_gives_same_shift():
    a, b = Plant(scenario="demo", seed=1), Plant(scenario="demo", seed=1)
    a.step(120)
    b.step(120)
    assert [i.title for i in a.state.incidents.values()] == [i.title for i in b.state.incidents.values()]


# ------------------------------------------------------------------ demo story


def test_0600_absences_show_uncovered_station_and_warden_gap():
    plant = Plant(scenario="demo")
    plant.step(1)
    types = open_types(plant)
    assert ("station_uncovered", "S12") in types
    assert ("fire_warden_gap", "B") in types
    active = [i for i in plant.central.open_incidents(plant.state) if i.visibility == "active"]
    assert len(active) <= 3


def test_uncovered_station_stops_the_line_until_covered():
    plant = Plant(scenario="demo")
    plant.step(5)
    assert plant.state.cars_built == 0
    accept_all(plant, lambda i: "S12" in i.stations)
    plant.step(5)
    assert plant.state.cars_built >= 4


def test_tool_wear_at_s12_is_predicted_before_the_break():
    plant = Plant(scenario="demo")
    plant.step(1)
    accept_all(plant)
    at(plant, 9, 25)
    tool = [i for i in plant.state.incidents.values()
            if any(e.type == "predicted_tool_failure" for e in plant.central.events_for(i.id))]
    assert tool, "tool wear should be predicted"
    assert tool[0].opened.time() < time(9, 30)


def test_accepting_planned_swap_avoids_the_stop():
    plant = Plant(scenario="demo")
    plant.step(1)
    accept_all(plant)
    at(plant, 9, 25)
    accept_all(plant, lambda i: "S12" in i.stations)
    at(plant, 10, 10)
    stops = [e for e in plant.state.events if e.type == "station_stopped" and e.station == "S12"]
    assert stops == []
    assert plant.state.impact["downtime_avoided_min"] > 0


def test_ignoring_the_prediction_leads_to_a_stop():
    plant = Plant(scenario="demo")
    plant.step(1)
    accept_all(plant, lambda i: "S12" in i.stations or i.zone == "B")
    at(plant, 10, 10)
    stops = [e for e in plant.state.events if e.type == "station_stopped" and e.station == "S12"]
    assert stops, "an ignored worn tool should fail"


def test_trainee_and_defects_at_s09_merge_into_one_incident():
    plant = Plant(scenario="demo")
    plant.step(1)
    accept_all(plant)
    at(plant, 10, 0)
    s09 = [i for i in plant.state.incidents.values() if "S09" in i.stations and i.status == "open"]
    assert s09
    agents = set(s09[0].agents)
    assert agents == {"assembly", "staffing"}
    assert "trainee" in (s09[0].likely_cause or "").lower()


def test_smoke_at_battery_station_triggers_emergency_in_zone_c():
    plant = Plant(scenario="demo")
    plant.step(1)
    accept_all(plant)
    at(plant, 10, 20)
    assert plant.state.emergency is not None and plant.state.emergency.zone == "C"
    top = plant.central.open_incidents(plant.state)[0]
    assert top.category == "safety" and top.recommendation.action == "emergency"


def test_emergency_stops_output_and_all_clear_gives_restart_plan():
    plant = Plant(scenario="demo")
    plant.step(1)
    accept_all(plant)
    at(plant, 9, 25)
    accept_all(plant)  # includes the planned tool swap at S12
    at(plant, 10, 20)
    built = plant.state.cars_built
    plant.step(5)
    assert plant.state.cars_built == built
    at(plant, 10, 27)
    plan = plant.all_clear()
    assert plan["zone"] == "C" and plan["cars_to_recover"] > 0
    plant.step(3)
    assert plant.state.cars_built > built


def test_external_vision_detection_flows_through_the_pipeline():
    plant = Plant(scenario="quiet")
    for _ in range(3):
        plant.ingest(VisionDetection(time=plant.state.now, camera="CAM-QC-S05", zone="A", station="S05",
                                     label="defect", confidence=0.9, detail="scratch"))
        plant.step(1)
    assert ("defect_pattern", "S05") in open_types(plant)


def test_accepting_every_recommendation_all_shift_never_opens_a_new_gap():
    plant = Plant(scenario="demo")
    end = datetime.combine(plant.state.now.date(), time(13, 0))
    while plant.state.now < end:
        plant.step(5)
        for inc in list(plant.central.open_incidents(plant.state)):
            before = {s for s in plant.state.layout.stations if plant.state.station_occupant(s) is None}
            plant.decide(inc.id, "accept")
            after = {s for s in plant.state.layout.stations if plant.state.station_occupant(s) is None}
            assert after <= before, (inc.title, after - before)
        if plant.state.emergency and plant.state.now.time() >= time(10, 27):
            plant.all_clear()


def test_borderline_qc_call_goes_to_expert_queue():
    from shiftloop.api.snapshot import snapshot
    plant = Plant(scenario="demo")
    at(plant, 11, 40)
    queue = snapshot(plant, {}, "offline")["expert_queue"]
    assert [q["station"] for q in queue] == ["S03"] and queue[0]["confidence"] < 0.5
