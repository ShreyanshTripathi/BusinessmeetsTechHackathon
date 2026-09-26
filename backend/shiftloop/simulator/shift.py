"""Synthetic shift: sensor, station, camera and roster signals, with an optional scripted demo story.

Every minute of simulated time produces one reading per station, per sensor and per camera.
Scenario scripts change the generators (tool wear, smoke, defects, absences) at given times, and
react to supervisor decisions (a planned tool swap removes the wear; an ignored one fails).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Callable

from ..models import SensorReading, StaffingChange, StationReading, VisionDetection
from ..state import FactoryState

TORQUE_NM, TORQUE_SD = 25.0, 0.3
STOCK_FULL, STOCK_REORDER = 240, 60
WEAR_DOUBLES_MIN = 30  # tool wear: torque spread grows by one baseline every 30 min
WEAR_FAILS_MIN = 90  # an ignored worn tool fails after 90 min


@dataclass
class ShiftSimulator:
    state: FactoryState
    seed: int = 42
    scenario: str = "demo"
    rng: random.Random = field(init=False)
    wear_start: dict[str, datetime] = field(default_factory=dict)
    failed: set[str] = field(default_factory=set)
    repair_at: dict[str, datetime] = field(default_factory=dict)
    defect_rate: dict[str, float] = field(default_factory=dict)
    stock: dict[str, int] = field(default_factory=dict)
    no_replenish_until: dict[str, datetime] = field(default_factory=dict)
    smoke: dict[str, float] = field(default_factory=dict)
    heat: dict[str, float] = field(default_factory=dict)
    gas: dict[str, float] = field(default_factory=dict)
    battery_target: float = 31.0
    battery_temp: float = 31.0
    camera_events: dict[str, tuple[str, float]] = field(default_factory=dict)  # camera -> (label, confidence)
    script: list[tuple[time, Callable[[], list]]] = field(default_factory=list)
    _done: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.stock = {sid: STOCK_FULL - self.rng.randrange(0, 120) for sid in self.state.layout.stations}
        if self.scenario == "demo":
            self.script = demo_script(self)

    # ------------------------------------------------------------------ helpers for scripts

    def at(self, hh: int, mm: int) -> datetime:
        return datetime.combine(self.state.now.date(), time(hh, mm))

    def staffing(self, worker_id: str, change: str, station: str | None = None) -> StaffingChange:
        return StaffingChange(time=self.state.now, worker=worker_id, change=change, station=station)

    # ------------------------------------------------------------------ reactions to decisions

    def schedule_repair(self, station: str, at: datetime) -> None:
        self.repair_at[station] = at

    def stop_defects(self, station: str) -> None:
        self.defect_rate.pop(station, None)

    def replenish(self, station: str) -> None:
        self.no_replenish_until.pop(station, None)
        self.stock[station] = STOCK_FULL

    # ------------------------------------------------------------------ generation

    def generate(self) -> list:
        now, st, rng = self.state.now, self.state, self.rng
        out: list = []
        for i, (at, action) in enumerate(self.script):
            if i not in self._done and now.time() >= at:
                self._done.add(i)
                out += action() or []

        for sid, when in list(self.repair_at.items()):
            if now >= when:
                self.wear_start.pop(sid, None)
                self.failed.discard(sid)
                del self.repair_at[sid]

        emergency_zone = st.emergency.zone if st.emergency else None
        pending_staffing = {c.worker: c for c in out if isinstance(c, StaffingChange)}
        readings: list = []
        for sid, station in st.layout.stations.items():
            occupant = self._occupant_after(sid, pending_staffing)
            torque_sd = TORQUE_SD
            if sid in self.wear_start:
                minutes = (now - self.wear_start[sid]).total_seconds() / 60
                torque_sd = TORQUE_SD * (1 + minutes / WEAR_DOUBLES_MIN)
                if minutes >= WEAR_FAILS_MIN and sid not in self.repair_at:
                    self.failed.add(sid)
            if station.zone == emergency_zone:
                status = "halted"
            elif sid in self.failed:
                status = "stopped"
            elif occupant is None:
                status = "starved"
            else:
                status = "running"
            running = status == "running"
            if running:
                self.stock[sid] -= 1
            blocked = sid in self.no_replenish_until and now < self.no_replenish_until[sid]
            if self.stock[sid] < STOCK_REORDER and not blocked:
                self.stock[sid] = STOCK_FULL
            cycle = station.takt_s + rng.gauss(0, 2) if running else 0.0
            readings.append(StationReading(
                time=now, station=sid, zone=station.zone, cycle_time_s=round(cycle, 1),
                torque_nm=round(TORQUE_NM + rng.gauss(0, torque_sd), 2) if running else None, status=status,
                stock={"fasteners": max(self.stock[sid], 0)}, consumption_per_min={"fasteners": 1.0}))

            label, conf = "ok", 0.97
            rate = self.defect_rate.get(sid, 0.0)
            if running and rng.random() < rate:
                label, conf = "defect", round(rng.uniform(0.75, 0.95), 2)
            readings.append(VisionDetection(time=now, camera=f"CAM-QC-{sid}", zone=station.zone, station=sid,
                                            label=label, confidence=conf,
                                            detail="loose fastener" if label == "defect" else ""))

        for sid, sensor in st.layout.sensors.items():
            z = sensor.zone
            if sensor.kind == "smoke":
                value = self.smoke.get(z, 0.2) + rng.gauss(0, 0.05)
            elif sensor.kind == "heat":
                value = self.heat.get(z, 24.0) + rng.gauss(0, 0.5)
            elif sensor.kind == "gas":
                value = self.gas.get(z, 5.0) + rng.gauss(0, 1.0)
            else:
                step = 2.5 if self.battery_target > self.battery_temp else -2.0
                if abs(self.battery_target - self.battery_temp) > abs(step):
                    self.battery_temp += step
                else:
                    self.battery_temp = self.battery_target
                value = self.battery_temp + rng.gauss(0, 0.2)
            readings.append(SensorReading(time=now, sensor=sid, zone=z, station=sensor.station,
                                          sensor_kind=sensor.kind, value=round(max(value, 0.0), 2)))

        for cid, cam in st.layout.cameras.items():
            if cam.purpose == "quality":
                continue
            label, conf = self.camera_events.get(cid, ("ok", 0.97))
            readings.append(VisionDetection(time=now, camera=cid, zone=cam.zone, label=label, confidence=conf))
        return out + readings

    def _occupant_after(self, sid: str, pending: dict[str, StaffingChange]):
        occupant = self.state.station_occupant(sid)
        if occupant is not None and occupant.id in pending and pending[occupant.id].change == "absent":
            occupant = None
        for change in pending.values():
            if change.change == "assign" and change.station == sid:
                occupant = self.state.workers[change.worker]
        return occupant

    # ------------------------------------------------------------------ line model

    def account(self) -> None:
        """One minute of output: the section is a serial line, so any stopped station stops it."""
        st = self.state
        blocked = [sid for sid, s in st.layout.stations.items() if s.status in ("stopped", "starved", "halted")]
        for sid in blocked:
            if st.layout.stations[sid].status != "halted":
                st.downtime_min[sid] += 1
        if st.emergency:
            st.downtime_min[f"Zone {st.emergency.zone} emergency"] += 1
        if not blocked:
            st.cars_built += 60 / st.layout.takt_s


def demo_script(sim: ShiftSimulator) -> list[tuple[time, Callable[[], list]]]:
    st = sim.state
    workers = st.workers

    def absences():
        s12 = st.station_occupant("S12")
        warden_b = next(w for w in workers.values() if w.fire_warden and w.home_zone == "B")
        floater_d = next(w for w in workers.values() if w.role == "floater" and w.home_zone == "D")
        return [sim.staffing(w.id, "absent") for w in (s12, warden_b, floater_d)]

    def tool_wear():
        sim.wear_start["S12"] = st.now
        return []

    def trainee_at_s09():
        sick = st.station_occupant("S09")
        free = [w for w in st.present() if w.role == "floater" and w.station is None and not w.busy_with]
        if not free:
            return []
        trainee = min(free, key=lambda w: w.qualifications.get("S09", 0))
        trainee.qualifications["S09"] = 1
        changes = [sim.staffing(trainee.id, "assign", "S09")]
        if sick is not None:
            changes.insert(0, sim.staffing(sick.id, "absent"))
        return changes

    def defects_start():
        sim.defect_rate["S09"] = 0.45
        return []

    def defects_stop():
        sim.stop_defects("S09")
        return []

    def battery_heats():
        sim.battery_target = 47.0
        return []

    def smoke_on_camera():
        sim.camera_events["CAM-FIRE-C"] = ("smoke", 0.72)
        return []

    def smoke_sensor():
        sim.smoke["C"] = 2.6
        return []

    def fire_out():
        sim.smoke.pop("C", None)
        sim.camera_events.pop("CAM-FIRE-C", None)
        sim.battery_target = 31.0
        return []

    def unsure_defect_s03():
        # a borderline call the QC model is not sure about: goes to the expert review queue
        return [VisionDetection(time=st.now, camera="CAM-QC-S03", zone=st.layout.stations["S03"].zone, station="S03",
                                label="defect", confidence=0.42, detail="possible paint scratch")]

    def shortage_s22():
        sim.stock["S22"] = 40
        sim.no_replenish_until["S22"] = sim.at(11, 45)
        return []

    def ppe(on: bool):
        def f():
            if on:
                sim.camera_events["CAM-PPE-A"] = ("ppe_missing", 0.81)
            else:
                sim.camera_events.pop("CAM-PPE-A", None)
            return []
        return f

    def exit_blocked(on: bool):
        def f():
            if on:
                sim.camera_events["CAM-EXIT-D"] = ("exit_blocked", 0.88)
            else:
                sim.camera_events.pop("CAM-EXIT-D", None)
            return []
        return f

    return [
        (time(6, 0), absences),
        (time(8, 30), tool_wear),
        (time(9, 0), trainee_at_s09),
        (time(9, 40), defects_start),
        (time(10, 30), defects_stop),
        (time(10, 12), battery_heats),
        (time(10, 15), smoke_on_camera),
        (time(10, 16), smoke_sensor),
        (time(10, 25), fire_out),
        (time(11, 0), shortage_s22),
        (time(11, 20), ppe(True)),
        (time(11, 26), ppe(False)),
        (time(11, 35), unsure_defect_s03),
        (time(11, 45), exit_blocked(True)),
        (time(12, 5), exit_blocked(False)),
    ]

