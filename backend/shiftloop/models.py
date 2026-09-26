"""Domain models shared by the simulator, agents, central intelligence and API."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

    @property
    def rank(self) -> int:
        return ["info", "low", "medium", "high", "critical"].index(self.value)


# --------------------------------------------------------------------------- layout


class Zone(BaseModel):
    id: str
    name: str
    order: int
    exits: list[str]
    assembly_point: str


class Station(BaseModel):
    id: str
    zone: str
    name: str
    safety_critical: bool = False
    takt_s: float = 60.0
    status: Literal["running", "stopped", "starved", "slowed", "halted"] = "running"


class Sensor(BaseModel):
    id: str
    zone: str
    station: str | None = None
    kind: Literal["smoke", "heat", "gas", "battery_temp"]
    unit: str
    warn: float
    crit: float


class Camera(BaseModel):
    id: str
    zone: str
    station: str | None = None
    purpose: Literal["quality", "fire", "ppe", "exit"]


class Layout(BaseModel):
    zones: list[Zone]
    stations: dict[str, Station]
    sensors: dict[str, Sensor]
    cameras: dict[str, Camera]

    def zone(self, zone_id: str) -> Zone:
        return next(z for z in self.zones if z.id == zone_id)


# --------------------------------------------------------------------------- people


class Worker(BaseModel):
    id: str
    name: str
    role: Literal["operator", "floater", "maintenance", "team_lead"]
    home_zone: str
    zone: str
    station: str | None = None
    qualifications: dict[str, int] = Field(default_factory=dict)  # 0 untrained, 1 trainee, 2 qualified, 3 trainer
    qual_expiry: dict[str, date] = Field(default_factory=dict)
    fire_warden: bool = False
    first_aider: bool = False
    status: Literal["present", "absent", "break"] = "present"
    hours_worked: float = 0.0
    busy_with: str | None = None  # incident/escalation id a maintenance tech or floater is working on
    languages: list[str] = Field(default_factory=lambda: ["de"])

    def level(self, station_id: str, on: date | None = None) -> int:
        """Effective qualification level; an expired qualification counts as untrained."""
        level = self.qualifications.get(station_id, 0)
        expiry = self.qual_expiry.get(station_id)
        if on is not None and expiry is not None and expiry < on:
            return 0
        return level


# --------------------------------------------------------------------------- raw readings (signals)


class StationReading(BaseModel):
    kind: Literal["station"] = "station"
    time: datetime
    station: str
    zone: str
    cycle_time_s: float
    torque_nm: float | None = None
    status: Literal["running", "stopped", "starved", "slowed", "halted"] = "running"
    stock: dict[str, int] = Field(default_factory=dict)  # part -> units at the station
    consumption_per_min: dict[str, float] = Field(default_factory=dict)


class SensorReading(BaseModel):
    kind: Literal["sensor"] = "sensor"
    time: datetime
    sensor: str
    zone: str
    station: str | None = None
    sensor_kind: Literal["smoke", "heat", "gas", "battery_temp"]
    value: float


class VisionDetection(BaseModel):
    kind: Literal["vision"] = "vision"
    time: datetime
    camera: str
    zone: str
    station: str | None = None
    label: Literal["ok", "defect", "fire", "smoke", "ppe_missing", "exit_blocked"]
    confidence: float
    detail: str = ""
    image_ref: str | None = None


class StaffingChange(BaseModel):
    kind: Literal["staffing"] = "staffing"
    time: datetime
    worker: str
    change: Literal["absent", "present", "break", "assign", "unassign", "move_zone"]
    station: str | None = None
    zone: str | None = None


Reading = Annotated[
    Union[StationReading, SensorReading, VisionDetection, StaffingChange],
    Field(discriminator="kind"),
]


# --------------------------------------------------------------------------- agent output


class Event(BaseModel):
    id: str
    agent: Literal["staffing", "assembly", "safety"]
    time: datetime
    zone: str
    station: str | None = None
    type: str
    severity: Severity
    confidence: float = 1.0
    evidence: list[str] = Field(default_factory=list)
    suggested_action: str = ""
    key: str = ""  # stable condition key; the same key is not re-emitted while the condition persists
    cleared: bool = False  # True when the agent reports the condition is gone
    data: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- central output


class Assignment(BaseModel):
    worker: str
    worker_name: str
    kind: Literal["station", "relocate", "task"] = "station"  # take over a station / move zone / temporary task
    to_station: str | None = None
    to_zone: str | None = None
    task: str
    reason: str


class Recommendation(BaseModel):
    action: Literal["keep_running", "slow", "reroute", "stop", "emergency"]
    scope: Literal["station", "zone", "section"] = "station"
    target: str  # station or zone id
    summary: str
    steps: list[str] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)  # team names to call, e.g. "maintenance"
    hard_rule: str | None = None  # set when a non-negotiable safety/quality rule produced the action


class Incident(BaseModel):
    id: str
    title: str
    zone: str
    stations: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    event_keys: list[str] = Field(default_factory=list)
    severity: Severity
    category: Literal["safety", "quality", "production", "staffing"]
    confidence: float = 1.0
    opened: datetime
    updated: datetime
    score: float = 0.0
    status: Literal["open", "accepted", "dismissed", "resolved"] = "open"
    visibility: Literal["active", "held"] = "held"
    likely_cause: str | None = None
    evidence: list[str] = Field(default_factory=list)
    recommendation: Recommendation | None = None


class Decision(BaseModel):
    id: str
    time: datetime
    incident_id: str
    incident_title: str
    recommended: str
    decision: Literal["accept", "modify", "dismiss"]
    reason: str = ""
    applied: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)
    decided_by: str = "supervisor"


class Notification(BaseModel):
    id: str
    time: datetime
    level: Literal["critical", "warning", "info"]
    title: str
    body: str = ""
    incident_id: str | None = None
    acknowledged: bool = False


class Escalation(BaseModel):
    id: str
    time: datetime
    team: str
    incident_id: str
    message: str
    acknowledged_at: datetime | None = None
    reminders: int = 0
    last_reminder: datetime | None = None


class Proposal(BaseModel):
    """An action suggested by the chat copilot. Nothing changes until the supervisor confirms it."""

    id: str
    kind: Literal["assign", "incident_decision"]
    description: str
    params: dict[str, Any]
    status: Literal["pending", "confirmed", "rejected"] = "pending"
