"""Fire & Safety agent: fire/smoke (sensor + camera fusion), battery overheating, gas, heat, exits and PPE.

Safety conditions carry `hard_rule="safety_stop"`; the central agent always ranks them first and
recommends stopping the zone. PPE and exit detections are zone-level only: no identity is stored.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta

from ..factory import ZONE_ORDER
from ..models import Event, SensorReading, VisionDetection
from ..state import FactoryState
from .base import BaseAgent

VISION_TTL = timedelta(minutes=5)
CAMERA_POSSIBLE = 0.6
CAMERA_CONFIRMED = 0.85
BATTERY_RISE_PER_MIN = 2.0


class SafetyAgent(BaseAgent):
    name = "safety"

    def __init__(self) -> None:
        super().__init__()
        self.vision: dict[str, dict[str, VisionDetection]] = defaultdict(dict)  # zone -> label -> latest
        self.battery: dict[str, deque] = defaultdict(lambda: deque(maxlen=5))

    def handle(self, reading, state: FactoryState) -> list[Event]:
        if isinstance(reading, SensorReading):
            if reading.sensor_kind == "battery_temp":
                self.battery[reading.sensor].append((reading.time, reading.value))
            return self._sync(state, self._zone_conditions(reading.zone, state), scope=f"{reading.zone}:")
        if isinstance(reading, VisionDetection) and reading.label in {"fire", "smoke", "exit_blocked", "ppe_missing"}:
            self.vision[reading.zone][reading.label] = reading
            return self._sync(state, self._zone_conditions(reading.zone, state), scope=f"{reading.zone}:")
        return []

    def tick(self, state: FactoryState) -> list[Event]:
        out = []
        for zone in ZONE_ORDER:
            out += self._sync(state, self._zone_conditions(zone, state), scope=f"{zone}:")
        return out

    # ------------------------------------------------------------------

    def _seen(self, zone: str, label: str, state: FactoryState) -> VisionDetection | None:
        det = self.vision[zone].get(label)
        if det is None or state.now - det.time > VISION_TTL:
            return None
        return det

    def _sensor(self, zone: str, kind: str, state: FactoryState):
        for sid, s in state.layout.sensors.items():
            if s.zone == zone and s.kind == kind and s.station is None:
                return s, state.last_sensor.get(sid)
        return None, None

    def _zone_conditions(self, zone: str, state: FactoryState) -> list[Event]:
        conds: list[Event] = []
        people = state.zone_headcount(zone)

        # --- fire / smoke: fuse the zone smoke sensor with the fire camera
        smoke_sensor, smoke = self._sensor(zone, "smoke", state)
        smoke_val = smoke.value if smoke else 0.0
        cams = [d for d in (self._seen(zone, "fire", state), self._seen(zone, "smoke", state)) if d]
        cam = max(cams, key=lambda d: d.confidence) if cams else None
        cam_conf = cam.confidence if cam else 0.0
        evidence = []
        if cam and cam_conf >= CAMERA_POSSIBLE:
            evidence.append(f"{cam.camera}: {cam.label} detected ({cam_conf:.0%})")
        if smoke_val >= smoke_sensor.warn:
            evidence.append(f"{smoke_sensor.id}: {smoke_val:.1f} {smoke_sensor.unit} (alarm at {smoke_sensor.crit})")
        confirmed = (smoke_val >= smoke_sensor.crit or cam_conf >= CAMERA_CONFIRMED
                     or (cam_conf >= CAMERA_POSSIBLE and smoke_val >= smoke_sensor.warn))
        possible = cam_conf >= CAMERA_POSSIBLE or smoke_val >= smoke_sensor.warn
        if confirmed:
            conds.append(self.condition(
                state, key=f"{zone}:fire", type="fire_confirmed", zone=zone, severity="critical",
                confidence=max(0.9, cam_conf), evidence=evidence + [f"{people} people in zone {zone}"],
                suggested_action=f"STOP zone {zone}, evacuate, fire wardens respond",
                data={"emergency": True, "hard_rule": "safety_stop", "people_in_zone": people}))
        elif possible:
            conds.append(self.condition(
                state, key=f"{zone}:fire", type="possible_fire", zone=zone, severity="high",
                confidence=max(cam_conf, 0.6), evidence=evidence,
                suggested_action=f"Fire warden verifies zone {zone} now",
                data={"needs_verification": True}))

        # --- battery fitting station temperature
        for sid, s in state.layout.sensors.items():
            if s.zone != zone or s.kind != "battery_temp":
                continue
            hist = self.battery[sid]
            if not hist:
                continue
            value = hist[-1][1]
            rate = 0.0
            if len(hist) >= 2:
                minutes = (hist[-1][0] - hist[0][0]).total_seconds() / 60
                rate = (hist[-1][1] - hist[0][1]) / minutes if minutes > 0 else 0.0
            rising = rate >= BATTERY_RISE_PER_MIN
            if value >= s.crit or value >= s.warn or rising:
                critical = value >= s.crit
                ev = [f"{sid}: battery pack at {value:.1f}°C (critical at {s.crit:.0f}°C)"]
                if rising:
                    ev.append(f"temperature rising {rate:.1f}°C/min")
                conds.append(self.condition(
                    state, key=f"{zone}:battery:{s.station}", type="battery_overheating", zone=zone,
                    station=s.station, severity="critical" if critical else "high", evidence=ev,
                    suggested_action="STOP station, isolate pack, thermal-runaway procedure" if critical
                    else "Pause battery fitting, check pack and cooling",
                    data={"temp_c": value, "rate_c_per_min": round(rate, 2),
                          **({"hard_rule": "safety_stop"} if critical else {})}))

        # --- gas and heat
        for kind, type_, label in (("gas", "gas_alarm", "CO"), ("heat", "high_heat", "temperature")):
            sensor, r = self._sensor(zone, kind, state)
            if not r or r.value < sensor.warn:
                continue
            critical = r.value >= sensor.crit
            conds.append(self.condition(
                state, key=f"{zone}:{kind}", type=type_, zone=zone, severity="critical" if critical else "high",
                evidence=[f"{sensor.id}: {label} {r.value:.0f} {sensor.unit} (alarm at {sensor.crit:.0f})"],
                suggested_action=f"STOP zone {zone} and ventilate" if critical else "Check source, prepare to stop",
                data={"value": r.value, **({"hard_rule": "safety_stop"} if critical else {})}))

        # --- exits and PPE (zone level, no identities)
        exit_det = self._seen(zone, "exit_blocked", state)
        if exit_det:
            conds.append(self.condition(
                state, key=f"{zone}:exit", type="exit_blocked", zone=zone, severity="high",
                confidence=exit_det.confidence, evidence=[f"{exit_det.camera}: emergency exit blocked"],
                suggested_action="Clear the exit route now"))
        ppe_det = self._seen(zone, "ppe_missing", state)
        if ppe_det:
            conds.append(self.condition(
                state, key=f"{zone}:ppe", type="ppe_missing", zone=zone, severity="medium",
                confidence=ppe_det.confidence, evidence=[f"{ppe_det.camera}: protective equipment missing in zone"],
                suggested_action="Team lead reminds the zone at the next opportunity"))
        return conds
