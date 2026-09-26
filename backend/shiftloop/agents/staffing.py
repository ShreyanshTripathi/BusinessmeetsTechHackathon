"""Staffing agent: station cover, qualifications, safety-role coverage and working-time limits.

It checks qualifications and legal limits only. It never scores how well individuals perform.
"""
from __future__ import annotations

from datetime import timedelta

from ..factory import ZONE_ORDER
from ..matching import cover_candidates, warden_donors
from ..models import Event
from ..state import FactoryState
from .base import BaseAgent

FORECAST_EVERY = timedelta(minutes=60)
EXPIRY_WARNING_DAYS = 7
HOURS_WARN = 9.5
HOURS_MAX = 10.0


class StaffingAgent(BaseAgent):
    name = "staffing"

    def __init__(self, forecaster=None) -> None:
        super().__init__()
        self.forecaster = forecaster  # ml_bridge.MLBridge: random-forest cover-risk forecast
        self._forecast: list[dict] = []
        self._forecast_at = None

    def tick(self, state: FactoryState) -> list[Event]:
        conds = self._conditions(state)
        if self.forecaster is not None:
            if self._forecast_at is None or state.now - self._forecast_at >= FORECAST_EVERY:
                self._forecast = self.forecaster.staffing_forecast(state)
                self._forecast_at = state.now
            conds += [self.forecast_condition(state, ml, key=f"forecast:{ml['station']}") for ml in self._forecast]
        return self._sync(state, conds)

    def _conditions(self, state: FactoryState) -> list[Event]:
        conds: list[Event] = []
        today = state.now.date()
        for sid, station in state.layout.stations.items():
            occupant = state.station_occupant(sid)
            if occupant is None:
                cands = cover_candidates(state, sid)
                conds.append(self.condition(
                    state, key=f"uncovered:{sid}", type="station_uncovered", zone=station.zone, station=sid,
                    severity="high",
                    evidence=[f"No one present at {sid} ({station.name})"],
                    suggested_action=f"Assign {cands[0].name}" if cands else "No free qualified cover; move someone",
                    data={"candidates": [c.as_dict() for c in cands[:3]]}))
                continue
            level = occupant.level(sid, on=today)
            if level < 2:
                severity = "high" if level == 0 or station.safety_critical else "medium"
                label = "untrained" if level == 0 else "a trainee"
                cands = cover_candidates(state, sid)
                conds.append(self.condition(
                    state, key=f"untrained:{sid}", type="untrained_at_station", zone=station.zone, station=sid,
                    severity=severity,
                    evidence=[f"{sid} ({station.name}) is run by {label} (level {level})"],
                    suggested_action="Pair with a qualified buddy or swap",
                    data={"worker_id": occupant.id, "level": level, "candidates": [c.as_dict() for c in cands[:3]]}))
            expiry = occupant.qual_expiry.get(sid)
            if expiry is not None and today <= expiry <= today + timedelta(days=EXPIRY_WARNING_DAYS):
                conds.append(self.condition(
                    state, key=f"expiring:{sid}:{occupant.id}", type="qualification_expiring", zone=station.zone,
                    station=sid, severity="low",
                    evidence=[f"Qualification for {sid} expires {expiry.isoformat()}"],
                    suggested_action="Schedule re-certification",
                    data={"worker_id": occupant.id, "expires": expiry.isoformat()}))

        for zone in ZONE_ORDER:
            if not state.fire_wardens(zone):
                donors = warden_donors(state, zone)
                conds.append(self.condition(
                    state, key=f"warden:{zone}", type="fire_warden_gap", zone=zone, severity="high",
                    evidence=[f"Zone {zone} has no trained fire warden present"],
                    suggested_action=f"Move {donors[0].name} to zone {zone}" if donors else "Call in a fire warden",
                    data={"donors": [d.as_dict() for d in donors]}))
            if not state.first_aiders(zone):
                conds.append(self.condition(
                    state, key=f"firstaid:{zone}", type="first_aider_gap", zone=zone, severity="medium",
                    evidence=[f"Zone {zone} has no first aider present"],
                    suggested_action="Nearest first aider covers two zones; inform team"))

        for w in state.present():
            if w.hours_worked >= HOURS_WARN:
                severity = "high" if w.hours_worked >= HOURS_MAX else "medium"
                conds.append(self.condition(
                    state, key=f"hours:{w.id}", type="working_time_limit", zone=w.zone, station=w.station,
                    severity=severity,
                    evidence=[f"{w.hours_worked:.1f}h worked today (limit {HOURS_MAX:.0f}h)"],
                    suggested_action="Relieve before the legal limit",
                    data={"worker_id": w.id}))
        return conds
