"""The shared picture of the section: layout, people, live readings and everything the agents produced."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .factory import SHIFT_DATE, build_layout, build_roster, zone_of
from .models import (
    Decision,
    Escalation,
    Event,
    Incident,
    Layout,
    Notification,
    Proposal,
    SensorReading,
    StaffingChange,
    StationReading,
    VisionDetection,
    Worker,
)

SHIFT_START = datetime.combine(SHIFT_DATE, datetime.min.time()).replace(hour=6)
SHIFT_HOURS = 8.0


@dataclass
class Emergency:
    zone: str
    started: datetime
    reason: str
    incident_id: str
    accounted: set[str] = field(default_factory=set)  # worker ids checked in at the assembly point


@dataclass
class FactoryState:
    layout: Layout
    workers: dict[str, Worker]
    now: datetime = SHIFT_START
    signals: int = 0
    events: list[Event] = field(default_factory=list)
    incidents: dict[str, Incident] = field(default_factory=dict)
    decisions: list[Decision] = field(default_factory=list)
    notifications: list[Notification] = field(default_factory=list)
    escalations: dict[str, Escalation] = field(default_factory=dict)
    proposals: dict[str, Proposal] = field(default_factory=dict)
    emergency: Emergency | None = None
    # live readings
    last_station: dict[str, StationReading] = field(default_factory=dict)
    last_sensor: dict[str, SensorReading] = field(default_factory=dict)
    recent_vision: deque = field(default_factory=lambda: deque(maxlen=200))
    # shift KPIs
    cars_built: float = 0.0
    downtime_min: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    defects: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    impact: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @classmethod
    def create(cls, seed: int = 42) -> "FactoryState":
        layout = build_layout()
        return cls(layout=layout, workers=build_roster(layout, seed=seed))

    # ------------------------------------------------------------------ ids & clock

    def next_id(self, prefix: str) -> str:
        self._counters[prefix] += 1
        return f"{prefix}_{self._counters[prefix]:04d}"

    def advance(self, dt: timedelta) -> None:
        hours = dt.total_seconds() / 3600
        for w in self.workers.values():
            if w.status == "present":
                w.hours_worked += hours
        self.now += dt

    @property
    def shift_elapsed_h(self) -> float:
        return (self.now - SHIFT_START).total_seconds() / 3600

    # ------------------------------------------------------------------ people queries

    def present(self) -> list[Worker]:
        return [w for w in self.workers.values() if w.status == "present"]

    def station_occupant(self, station_id: str) -> Worker | None:
        return next((w for w in self.present() if w.station == station_id), None)

    def zone_headcount(self, zone: str) -> int:
        return sum(1 for w in self.present() if w.zone == zone)

    def fire_wardens(self, zone: str) -> list[Worker]:
        return [w for w in self.present() if w.fire_warden and w.zone == zone]

    def first_aiders(self, zone: str) -> list[Worker]:
        return [w for w in self.present() if w.first_aider and w.zone == zone]

    # ------------------------------------------------------------------ people changes

    def assign(self, worker_id: str, station_id: str) -> str | None:
        """Put a worker on a station. Returns the id of the worker who was displaced, if any."""
        previous = self.station_occupant(station_id)
        displaced = None
        if previous is not None and previous.id != worker_id:
            previous.station = None
            displaced = previous.id
        w = self.workers[worker_id]
        w.station = station_id
        w.zone = zone_of(station_id)
        w.status = "present"
        return displaced

    def move_zone(self, worker_id: str, zone: str) -> None:
        w = self.workers[worker_id]
        w.station = None
        w.zone = zone

    def apply_staffing(self, change: StaffingChange) -> None:
        w = self.workers[change.worker]
        if change.change == "absent":
            w.status = "absent"
            w.station = None
        elif change.change == "present":
            w.status = "present"
        elif change.change == "break":
            w.status = "break"
        elif change.change == "assign" and change.station:
            self.assign(w.id, change.station)
        elif change.change == "unassign":
            w.station = None
        elif change.change == "move_zone" and change.zone:
            self.move_zone(w.id, change.zone)

    # ------------------------------------------------------------------ readings

    def record(self, reading) -> None:
        self.signals += 1
        if isinstance(reading, StationReading):
            self.last_station[reading.station] = reading
            self.layout.stations[reading.station].status = reading.status
        elif isinstance(reading, SensorReading):
            self.last_sensor[reading.sensor] = reading
        elif isinstance(reading, VisionDetection):
            self.recent_vision.append(reading)
            if reading.label == "defect" and reading.confidence >= 0.5:
                self.defects[reading.station] += 1
        elif isinstance(reading, StaffingChange):
            self.apply_staffing(reading)

    def notify(self, level: str, title: str, body: str = "", incident_id: str | None = None) -> Notification:
        n = Notification(id=self.next_id("ntf"), time=self.now, level=level, title=title, body=body,
                         incident_id=incident_id)
        self.notifications.append(n)
        return n
