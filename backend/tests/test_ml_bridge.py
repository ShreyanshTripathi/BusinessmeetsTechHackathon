"""The ML models from ml/ feed the specialised agents; Claude (or a template) explains each prediction."""
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest

from shiftloop.actions import decide
from shiftloop.agents.assembly import AssemblyAgent
from shiftloop.agents.staffing import StaffingAgent
from shiftloop.central.engine import CentralIntelligence
from shiftloop.ml_bridge import MLBridge, assembly_rows, staffing_rows
from shiftloop.models import Event, Severity, StaffingChange
from shiftloop.plant import Plant
from shiftloop.state import FactoryState


@pytest.fixture(scope="module")
def bridge():
    b = MLBridge.load()
    assert b.available, b.status
    return b


# ------------------------------------------------------------------ loading


def test_bridge_loads_all_three_models(bridge):
    assert bridge.status == {"staffing": "loaded", "assembly": "loaded", "safety": "loaded"}


def test_missing_models_leave_agents_rule_only(tmp_path: Path):
    b = MLBridge.load(ml_dir=tmp_path)
    assert not b.available
    assert set(b.status.values()) == {"unavailable"}
    assert b.staffing_forecast(FactoryState.create()) == []
    assert b.assembly_forecast(FactoryState.create()) == []


# ------------------------------------------------------------------ features from live state


def test_staffing_rows_describe_staffed_stations_from_the_roster():
    state = FactoryState.create()
    absent = state.station_occupant("S12")
    state.apply_staffing(StaffingChange(time=state.now, worker=absent.id, change="absent"))
    state.station_occupant("S09").qualifications["S09"] = 1
    rows = {r["station"]: r for r in staffing_rows(state)}
    assert "S12" not in rows  # already a live gap, handled by the rules
    assert rows["S09"]["operator_level"] == 1 and rows["S09"]["zone"] == "B"
    assert rows["S09"]["zone_trainees"] == 1 and rows["S09"]["crew_trainees"] == 1
    assert rows["S09"]["shift"] == "early" and rows["S09"]["day_of_week"] == "Thursday"
    assert rows["S18"]["safety_critical"] == 1
    floaters_b = [w for w in state.present() if w.role == "floater" and w.home_zone == "B"]
    assert rows["S09"]["zone_floaters"] == len(floaters_b)


def test_assembly_rows_scale_zone_headcount_and_buffer():
    state = FactoryState.create()
    rows = assembly_rows(state, reference={"no_of_workers": 57, "wip": 1000, "smv": 22.0, "over_time": 4000,
                                           "targeted_productivity": 0.8, "no_of_style_change": 0,
                                           "department": "sewing", "day": "Thursday", "team": 6})
    assert [r["zone"] for r in rows] == ["A", "B", "C", "D"]
    full = rows[0]["features"]["no_of_workers"]
    state.apply_staffing(StaffingChange(time=state.now, worker=state.station_occupant("S02").id, change="absent"))
    state.layout.stations["S03"].status = "stopped"
    fewer = assembly_rows(state, reference=rows[0]["features"] | {"no_of_workers": 57, "wip": 1000})[0]["features"]
    assert fewer["no_of_workers"] < full
    assert fewer["wip"] < rows[0]["features"]["wip"]


# ------------------------------------------------------------------ agents with a fake forecaster


class FakeForecaster:
    available = True

    def __init__(self):
        self.staffing: list[dict] = []
        self.assembly: list[dict] = []

    def staffing_forecast(self, state):
        return self.staffing

    def assembly_forecast(self, state):
        return self.assembly


def ml_event(agent, type_, zone, station, risk, severity="medium"):
    return {"agent": agent, "type": type_, "zone": zone, "station": station, "severity": severity,
            "confidence": risk, "evidence": [f"{risk:.0%} risk"], "suggested_action": "do it",
            "data": {"risk": risk, "model": f"{agent}_model", "drivers": [], "explanation": "because"}}


def test_staffing_agent_emits_forecasts_as_conditions_and_clears_them():
    state, fake = FactoryState.create(), FakeForecaster()
    agent = StaffingAgent(forecaster=fake)
    agent.tick(state)
    fake.staffing = [ml_event("staffing", "cover_risk", "B", "S09", 0.8)]
    state.advance(timedelta(minutes=60))
    ev = next(e for e in agent.tick(state) if e.type == "cover_risk")
    assert ev.station == "S09" and ev.data["model"] == "staffing_model" and ev.key == "staffing:forecast:S09"
    fake.staffing = []
    state.advance(timedelta(minutes=60))
    assert [(e.type, e.cleared) for e in agent.tick(state)] == [("cover_risk", True)]


def test_staffing_forecast_runs_hourly_not_every_minute():
    state, fake = FactoryState.create(), FakeForecaster()
    calls = []
    fake.staffing_forecast = lambda s: calls.append(s.now) or []
    agent = StaffingAgent(forecaster=fake)
    for _ in range(61):
        agent.tick(state)
        state.advance(timedelta(minutes=1))
    assert len(calls) == 2  # 06:00 and 07:00


def test_forecast_severity_is_capped_below_live_problems():
    state, fake = FactoryState.create(), FakeForecaster()
    fake.staffing = [ml_event("staffing", "cover_risk", "C", "S18", 0.9, severity="high")]
    ev = next(e for e in StaffingAgent(forecaster=fake).tick(state) if e.type == "cover_risk")
    assert ev.severity == Severity.medium


def test_assembly_agent_emits_zone_forecasts_every_30_minutes():
    state, fake = FactoryState.create(), FakeForecaster()
    fake.assembly = [ml_event("assembly", "output_target_risk", "B", None, 0.85, severity="high")]
    agent = AssemblyAgent(forecaster=fake)
    ev = agent.tick(state)[0]
    assert ev.type == "output_target_risk" and ev.zone == "B" and ev.key == "assembly:forecast:B"
    assert ev.severity == Severity.medium
    state.advance(timedelta(minutes=10))
    assert agent.tick(state) == []


# ------------------------------------------------------------------ central: predictions on incidents, ranking


def test_incident_carries_the_models_prediction_and_explanation():
    state, central = FactoryState.create(), CentralIntelligence()
    e = Event(id="evt_1", agent="staffing", time=state.now, zone="B", station="S09", type="cover_risk",
              severity=Severity.medium, confidence=0.8, evidence=["80% risk"], key="staffing:forecast:S09",
              data={"risk": 0.8, "model": "staffing_model", "drivers": [{"feature": "operator_level", "value": 1,
                                                                          "typical": 2, "effect": 0.4}],
                    "explanation": "S09 is run by a trainee."})
    central.ingest(state, [e])
    inc = central.open_incidents(state)[0]
    assert inc.predictions == [{"event_id": "evt_1", "model": "staffing_model", "risk": 0.8,
                                "explanation": "S09 is run by a trainee.", "drivers": e.data["drivers"]}]
    assert inc.recommendation.steps  # cover risk has concrete steps


def test_near_miss_report_is_safety_but_does_not_outrank_a_stopped_line():
    state, central = FactoryState.create(), CentralIntelligence()
    near = Event(id="evt_1", agent="safety", time=state.now, zone="C", station="S17", type="near_miss_rated",
                 severity=Severity.high, key="safety:report:1", evidence=["potential severity: high (70%)"],
                 data={"model": "safety_model", "drivers": [], "explanation": "x"})
    stop = Event(id="evt_2", agent="assembly", time=state.now, zone="A", station="S02", type="station_stopped",
                 severity=Severity.high, key="assembly:S02:status", evidence=["stopped"])
    central.ingest(state, [near, stop])
    incs = {i.stations[0]: i for i in central.open_incidents(state)}
    assert incs["S17"].category == "safety"
    assert incs["S02"].score > incs["S17"].score
    steps = " ".join(incs["S17"].recommendation.steps).lower()
    assert "engineer" in steps and "blame" in steps


# ------------------------------------------------------------------ end to end with the real models


def test_plant_with_ml_raises_cover_risk_with_explanations():
    plant = Plant(scenario="demo", ml=True)
    plant.step(1)
    for inc in list(plant.central.open_incidents(plant.state)):
        plant.decide(inc.id, "accept")
    plant.run_until(datetime.combine(plant.state.now.date(), time(9, 5)))  # trainee at S09 since 09:00
    covers = [e for e in plant.state.events if e.type == "cover_risk" and not e.cleared]
    assert covers, "the staffing forest should flag at least one station"
    assert all(e.data["drivers"] and e.data["explanation"] for e in covers)
    assert any(e.station == "S09" for e in covers), "the trainee station should be among the risks"


def test_near_miss_report_goes_through_the_safety_model():
    plant = Plant(scenario="quiet", ml=True)
    ev = plant.report_near_miss("The hoist chain slipped while lifting the battery pack and it dropped.",
                                zone="C", station="S18")
    assert ev.agent == "safety" and ev.type in {"near_miss_rated", "near_miss_unsure"}
    assert ev.data["model"] == "safety_model" and "explanation" in ev.data
    assert any(i.stations == ["S18"] for i in plant.central.open_incidents(plant.state))


def test_demo_shift_includes_a_near_miss_report():
    plant = Plant(scenario="demo", ml=True)
    plant.run_until(datetime.combine(plant.state.now.date(), time(11, 15)))
    assert any(e.type.startswith("near_miss") for e in plant.state.events)


def test_plant_without_ml_behaves_as_before():
    plant = Plant(scenario="demo")
    plant.step(90)
    assert not any(e.data.get("model") for e in plant.state.events)


def test_explanations_endpoint_logic_uses_template_offline(bridge):
    plant = Plant(scenario="quiet", ml=True)
    ev = plant.report_near_miss("Worker slipped on oil near the press, no injury.", zone="A", station="S02")
    inc = next(i for i in plant.central.open_incidents(plant.state) if ev.id in i.event_ids)
    out = plant.explain_incident(inc.id, client=None)
    assert out and out[0]["mode"] == "offline" and out[0]["model"] == "safety_model"


def test_forecasts_under_80_percent_stay_out_of_the_inbox():
    state, fake, central = FactoryState.create(), FakeForecaster(), CentralIntelligence()
    fake.staffing = [ml_event("staffing", "cover_risk", "C", "S13", 0.64)]
    events = [e for e in StaffingAgent(forecaster=fake).tick(state) if e.type == "cover_risk"]
    assert events[0].severity == Severity.low
    central.ingest(state, events)
    assert central.open_incidents(state)[0].visibility == "held"
