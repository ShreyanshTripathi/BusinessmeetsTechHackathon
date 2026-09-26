from datetime import timedelta

from shiftloop.agents.safety import SafetyAgent
from shiftloop.models import SensorReading, VisionDetection
from shiftloop.state import FactoryState


def sensor(state, sensor_id, value):
    s = state.layout.sensors[sensor_id]
    return SensorReading(time=state.now, sensor=sensor_id, zone=s.zone, station=s.station,
                         sensor_kind=s.kind, value=value)


def cam(state, zone, label, conf=0.9, purpose="fire"):
    return VisionDetection(time=state.now, camera=f"CAM-{purpose.upper()}-{zone}", zone=zone, label=label,
                           confidence=conf)


def feed(agent, state, readings, minutes=1):
    events = []
    for r in readings:
        r = r.model_copy(update={"time": state.now})
        state.record(r)
        events += agent.handle(r, state)
        state.advance(timedelta(minutes=minutes))
    return events


def test_normal_sensor_values_raise_nothing():
    state, agent = FactoryState.create(), SafetyAgent()
    readings = [sensor(state, f"SMK-{z}", 0.3) for z in "ABCD"] + [sensor(state, "BT-S18", 31.0)]
    assert feed(agent, state, readings) == []


def test_camera_smoke_alone_is_possible_fire_needing_verification():
    state, agent = FactoryState.create(), SafetyAgent()
    events = feed(agent, state, [cam(state, "C", "smoke", conf=0.7)])
    assert [(e.type, e.severity.value, e.zone) for e in events] == [("possible_fire", "high", "C")]
    assert events[0].data["needs_verification"]


def test_camera_plus_smoke_sensor_confirms_fire_and_requests_emergency():
    state, agent = FactoryState.create(), SafetyAgent()
    feed(agent, state, [cam(state, "C", "smoke", conf=0.7)])
    events = feed(agent, state, [sensor(state, "SMK-C", 2.5)])
    ev = next(e for e in events if e.type == "fire_confirmed")
    assert ev.severity.value == "critical"
    assert ev.data["emergency"] and ev.data["hard_rule"] == "safety_stop"
    assert any("SMK-C" in line for line in ev.evidence)


def test_smoke_sensor_over_critical_threshold_alone_confirms_fire():
    state, agent = FactoryState.create(), SafetyAgent()
    events = feed(agent, state, [sensor(state, "SMK-B", 4.5)])
    assert [(e.type, e.severity.value) for e in events] == [("fire_confirmed", "critical")]


def test_very_confident_camera_alone_confirms_fire():
    state, agent = FactoryState.create(), SafetyAgent()
    events = feed(agent, state, [cam(state, "A", "fire", conf=0.93)])
    assert [e.type for e in events] == ["fire_confirmed"]


def test_battery_overheating_and_fast_rise():
    state, agent = FactoryState.create(), SafetyAgent()
    rising = [sensor(state, "BT-S18", t) for t in (32, 34.5, 37, 39.5, 42)]
    events = feed(agent, state, rising)
    ev = next(e for e in events if e.type == "battery_overheating")
    assert ev.station == "S18" and ev.severity.value == "high"
    assert "rising" in " ".join(ev.evidence)
    events = feed(agent, state, [sensor(state, "BT-S18", 61)])
    ev = next(e for e in events if e.type == "battery_overheating")
    assert ev.severity.value == "critical" and ev.data["hard_rule"] == "safety_stop"


def test_gas_alarm_is_critical():
    state, agent = FactoryState.create(), SafetyAgent()
    events = feed(agent, state, [sensor(state, "GAS-D", 120)])
    assert [(e.type, e.severity.value) for e in events] == [("gas_alarm", "critical")]


def test_blocked_exit_is_high_and_clears_when_no_longer_seen():
    state, agent = FactoryState.create(), SafetyAgent()
    events = feed(agent, state, [cam(state, "B", "exit_blocked", purpose="exit")])
    assert [(e.type, e.severity.value) for e in events] == [("exit_blocked", "high")]
    state.advance(timedelta(minutes=10))
    assert [(e.type, e.cleared) for e in agent.tick(state)] == [("exit_blocked", True)]


def test_missing_ppe_is_medium_and_zone_level_only():
    state, agent = FactoryState.create(), SafetyAgent()
    events = feed(agent, state, [cam(state, "A", "ppe_missing", purpose="ppe")])
    assert [(e.type, e.severity.value, e.zone, e.station) for e in events] == [("ppe_missing", "medium", "A", None)]
    assert "worker" not in events[0].data


def test_fire_clears_when_sensors_normal_and_camera_quiet():
    state, agent = FactoryState.create(), SafetyAgent()
    feed(agent, state, [sensor(state, "SMK-C", 4.5)])
    state.advance(timedelta(minutes=6))
    events = feed(agent, state, [sensor(state, "SMK-C", 0.2)])
    assert [(e.type, e.cleared) for e in events] == [("fire_confirmed", True)]
