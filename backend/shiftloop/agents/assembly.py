"""General Assembly agent: station status, real slowdowns, tool wear, part shortages and defect patterns."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta
from statistics import mean, pstdev

from ..models import Event, Severity, StationReading, VisionDetection
from ..state import FactoryState
from ..stats import drop_is_real, trend_eta
from .base import BaseAgent

BASELINE_READINGS = 30  # torque readings used to learn what "normal" looks like
ROLLING = 10
DRIFT_RATIO = 2.0  # rolling spread vs baseline that signals tool wear
FAILURE_RATIO = 4.0  # spread at which the tool is expected to fail
DEFECT_WINDOW = timedelta(minutes=30)
UNSURE_CONFIDENCE = 0.5


class AssemblyAgent(BaseAgent):
    name = "assembly"

    def __init__(self) -> None:
        super().__init__()
        self.cycles: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
        self.torque: dict[str, list[float]] = defaultdict(list)
        self.torque_spread: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))  # (minute, spread)
        self.defect_times: dict[str, deque] = defaultdict(deque)

    def handle(self, reading, state: FactoryState) -> list[Event]:
        if isinstance(reading, StationReading):
            return self._sync(state, self._station_conditions(reading, state), scope=f"{reading.station}:")
        if isinstance(reading, VisionDetection) and reading.station and reading.label == "defect":
            if reading.confidence < UNSURE_CONFIDENCE:
                return [self._unsure(reading, state)]
            self.defect_times[reading.station].append(reading.time)
            return self._sync(state, self._defect_conditions(state), scope="defects:")
        return []

    def tick(self, state: FactoryState) -> list[Event]:
        return self._sync(state, self._defect_conditions(state), scope="defects:")

    # ------------------------------------------------------------------ station readings

    def _station_conditions(self, r: StationReading, state: FactoryState) -> list[Event]:
        sid, zone = r.station, r.zone
        station = state.layout.stations[sid]
        conds: list[Event] = []

        if r.status == "stopped":
            conds.append(self.condition(state, key=f"{sid}:status", type="station_stopped", zone=zone, station=sid,
                                        severity="high", evidence=[f"{sid} ({station.name}) reports STOPPED"],
                                        suggested_action="Dispatch maintenance"))
        elif r.status == "starved":
            conds.append(self.condition(state, key=f"{sid}:status", type="station_starved", zone=zone, station=sid,
                                        severity="medium", evidence=[f"{sid} is waiting for parts or cars"],
                                        suggested_action="Check upstream station and material"))

        if r.status == "running":
            self.cycles[sid].append(r.cycle_time_s)
            real, info = drop_is_real(list(self.cycles[sid]), target=station.takt_s)
            if real:
                conds.append(self.condition(
                    state, key=f"{sid}:slow", type="slowdown", zone=zone, station=sid, severity="medium",
                    confidence=min(0.99, 0.5 + info["z"] / 20),
                    evidence=[f"{info['verdict']}: {info['slower_pct']}% slower than takt "
                              f"({info['recent_mean']}s vs {station.takt_s:.0f}s)"],
                    suggested_action="Find the cause before it costs output", data=info))

        if r.torque_nm is not None:
            conds += self._torque_conditions(r, state)

        for part, units in r.stock.items():
            rate = r.consumption_per_min.get(part, 0)
            if rate <= 0:
                continue
            minutes_left = round(units / rate)
            if minutes_left < 30:
                conds.append(self.condition(
                    state, key=f"{sid}:stock:{part}", type="part_shortage", zone=zone, station=sid,
                    severity="high" if minutes_left < 10 else "medium",
                    evidence=[f"{units} {part} left at {sid}, ~{minutes_left} min at current rate"],
                    suggested_action="Call logistics for replenishment",
                    data={"part": part, "minutes_left": minutes_left, "units": units}))
        return conds

    def _torque_conditions(self, r: StationReading, state: FactoryState) -> list[Event]:
        sid = r.station
        series = self.torque[sid]
        series.append(r.torque_nm)
        if len(series) < BASELINE_READINGS + ROLLING:
            return []
        base = series[:BASELINE_READINGS]
        base_mean, base_spread = mean(base), max(pstdev(base), 0.05)
        recent = series[-ROLLING:]
        spread = pstdev(recent)
        minute = (r.time - state.now.replace(hour=0, minute=0)).total_seconds() / 60
        self.torque_spread[sid].append((minute, spread))
        ratio = spread / base_spread
        shift = abs(mean(recent) - base_mean) / base_spread
        if ratio < DRIFT_RATIO and shift < 4:
            return []
        pts = list(self.torque_spread[sid])[-15:]
        eta = trend_eta([p[0] for p in pts], [p[1] for p in pts], FAILURE_RATIO * base_spread)
        if ratio >= FAILURE_RATIO:
            eta = 0.0
        severity = Severity.high if eta is not None and eta <= 60 else Severity.medium
        eta_txt = "imminent" if eta == 0 else (f"~{eta:.0f} min" if eta is not None else "unknown")
        return [self.condition(
            state, key=f"{sid}:torque", type="predicted_tool_failure", zone=r.zone, station=sid, severity=severity,
            confidence=min(0.95, 0.4 + ratio / 10),
            evidence=[f"torque spread {ratio:.1f}x normal ({spread:.2f} vs {base_spread:.2f} Nm)",
                      f"mean torque {mean(recent):.1f} Nm (normal {base_mean:.1f} Nm)",
                      f"predicted failure: {eta_txt}"],
            suggested_action="Swap the tool at the next break",
            data={"eta_min": None if eta is None else round(eta), "spread_ratio": round(ratio, 2)})]

    # ------------------------------------------------------------------ vision

    def _defect_conditions(self, state: FactoryState) -> list[Event]:
        conds = []
        for sid, times in self.defect_times.items():
            while times and state.now - times[0] > DEFECT_WINDOW:
                times.popleft()
            n = len(times)
            if n < 2:
                continue
            spread = n >= 3
            conds.append(self.condition(
                state, key=f"defects:{sid}", type="defect_pattern", zone=state.layout.stations[sid].zone,
                station=sid, severity="high" if spread else "medium",
                evidence=[f"{n} defects detected at {sid} in the last 30 min"],
                suggested_action="Stop and contain: the defect may be spreading" if spread else "100% check at station",
                data={"count": n, "spread_risk": spread}))
        return conds

    def _unsure(self, r: VisionDetection, state: FactoryState) -> Event:
        return Event(id=state.next_id("evt"), agent=self.name, time=state.now, zone=r.zone, station=r.station,
                     type="inspection_unsure", severity=Severity.low, confidence=r.confidence,
                     evidence=[f"Model unsure ({r.confidence:.0%}) about '{r.detail or r.label}' at {r.station}"],
                     suggested_action="Expert review", key=f"{self.name}:unsure:{r.camera}:{r.time.isoformat()}",
                     data={"camera": r.camera, "image_ref": r.image_ref})
