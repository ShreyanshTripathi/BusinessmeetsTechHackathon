import random
from datetime import datetime, timedelta

from shiftloop.agents.assembly import AssemblyAgent
from shiftloop.models import StationReading, VisionDetection
from shiftloop.state import FactoryState

T0 = datetime(2026, 10, 1, 6, 0)


def reading(state, station="S12", cycle=60.0, torque=25.0, status="running", stock=None, rate=None):
    return StationReading(time=state.now, station=station, zone=state.layout.stations[station].zone,
                          cycle_time_s=cycle, torque_nm=torque, status=status,
                          stock=stock or {"bolts": 400}, consumption_per_min=rate or {"bolts": 4.0})


def feed(agent, state, readings):
    events = []
    for r in readings:
        r = r.model_copy(update={"time": state.now})  # stamp on arrival, as the simulator does
        state.record(r)
        events += agent.handle(r, state)
        state.advance(timedelta(minutes=1))
    return events


def test_normal_operation_raises_nothing():
    state, agent = FactoryState.create(), AssemblyAgent()
    rng = random.Random(3)
    events = feed(agent, state, [reading(state, cycle=60 + rng.gauss(0, 2), torque=25 + rng.gauss(0, 0.3))
                                 for _ in range(60)])
    assert events == []


def test_stopped_station_is_high_and_clears_on_restart():
    state, agent = FactoryState.create(), AssemblyAgent()
    events = feed(agent, state, [reading(state, status="stopped")])
    assert [(e.type, e.severity.value) for e in events] == [("station_stopped", "high")]
    events = feed(agent, state, [reading(state, status="running")])
    assert [(e.type, e.cleared) for e in events] == [("station_stopped", True)]


def test_starved_station_is_medium():
    state, agent = FactoryState.create(), AssemblyAgent()
    events = feed(agent, state, [reading(state, status="starved")])
    assert [(e.type, e.severity.value) for e in events] == [("station_starved", "medium")]


def test_sustained_slowdown_is_reported_as_real():
    state, agent = FactoryState.create(), AssemblyAgent()
    rng = random.Random(4)
    normal = [reading(state, cycle=60 + rng.gauss(0, 2)) for _ in range(20)]
    feed(agent, state, normal)
    slow = [reading(state, cycle=69 + rng.gauss(0, 2)) for _ in range(12)]
    events = feed(agent, state, slow)
    ev = next(e for e in events if e.type == "slowdown")
    assert ev.severity.value == "medium"
    assert "real" in ev.evidence[0]


def test_torque_drift_predicts_tool_failure_with_eta():
    state, agent = FactoryState.create(), AssemblyAgent()
    rng = random.Random(5)
    feed(agent, state, [reading(state, torque=25 + rng.gauss(0, 0.3)) for _ in range(40)])
    drifting = [reading(state, torque=25 + rng.gauss(0, 0.3 + 0.08 * i)) for i in range(30)]
    events = feed(agent, state, drifting)
    ev = next(e for e in events if e.type == "predicted_tool_failure")
    assert ev.station == "S12"
    assert ev.data["eta_min"] is not None and ev.data["eta_min"] > 0
    assert ev.severity.value in {"medium", "high"}
    assert any("torque" in line for line in ev.evidence)


def test_part_running_out_is_flagged_with_minutes_left():
    state, agent = FactoryState.create(), AssemblyAgent()
    events = feed(agent, state, [reading(state, stock={"brackets": 80}, rate={"brackets": 4.0})])
    ev = next(e for e in events if e.type == "part_shortage")
    assert ev.data["part"] == "brackets" and ev.data["minutes_left"] == 20
    assert ev.severity.value == "medium"
    events = feed(agent, state, [reading(state, stock={"brackets": 30}, rate={"brackets": 4.0})])
    assert next(e for e in events if e.type == "part_shortage").severity.value == "high"


def vision(state, station="S09", label="defect", conf=0.9):
    return VisionDetection(time=state.now, camera=f"CAM-QC-{station}", zone=state.layout.stations[station].zone,
                           station=station, label=label, confidence=conf, detail="loose fastener")


def test_repeated_defects_become_a_pattern_and_three_mean_spread_risk():
    state, agent = FactoryState.create(), AssemblyAgent()
    assert feed(agent, state, [vision(state)]) == []
    events = feed(agent, state, [vision(state)])
    ev = next(e for e in events if e.type == "defect_pattern")
    assert ev.severity.value == "medium" and not ev.data["spread_risk"]
    events = feed(agent, state, [vision(state)])
    ev = next(e for e in events if e.type == "defect_pattern")
    assert ev.severity.value == "high" and ev.data["spread_risk"]


def test_defect_pattern_clears_after_window_passes():
    state, agent = FactoryState.create(), AssemblyAgent()
    feed(agent, state, [vision(state), vision(state)])
    state.advance(timedelta(minutes=45))
    events = agent.tick(state)
    assert [(e.type, e.cleared) for e in events] == [("defect_pattern", True)]


def test_low_confidence_inspection_goes_to_expert_queue():
    state, agent = FactoryState.create(), AssemblyAgent()
    events = feed(agent, state, [vision(state, conf=0.45)])
    assert [(e.type, e.severity.value) for e in events] == [("inspection_unsure", "low")]
    assert state.defects["S09"] == 0  # unconfirmed detections do not count as defects
    assert state.recent_vision[-1].confidence == 0.45  # but the detection is kept for the expert


def test_ok_detections_are_ignored():
    state, agent = FactoryState.create(), AssemblyAgent()
    assert feed(agent, state, [vision(state, label="ok")]) == []


def test_halted_station_is_a_supervisor_stop_not_a_fault():
    state, agent = FactoryState.create(), AssemblyAgent()
    assert feed(agent, state, [reading(state, status="halted")]) == []
