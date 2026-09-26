"""Match people to problems: who is present, qualified, free, close by and within working-time limits."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .factory import ZONE_ORDER, zone_of
from .state import SHIFT_HOURS, FactoryState

MAX_DAILY_HOURS = 10.0  # German Working Hours Act (ArbZG) daily maximum


@dataclass
class Candidate:
    worker_id: str
    name: str
    zone: str
    score: float
    reason: str
    level: int = 0
    current_station: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def zone_distance(a: str, b: str) -> int:
    return abs(ZONE_ORDER.index(a) - ZONE_ORDER.index(b))


def _remaining_shift_hours(state: FactoryState) -> float:
    return max(0.0, SHIFT_HOURS - state.shift_elapsed_h)


def cover_candidates(
    state: FactoryState,
    station_id: str,
    include_assigned: bool = False,
    needed_hours: float | None = None,
    limit: int = 5,
) -> list[Candidate]:
    """Qualified people who could take over a station, best first."""
    zone = zone_of(station_id)
    needed = _remaining_shift_hours(state) if needed_hours is None else needed_hours
    today = state.now.date()
    out: list[Candidate] = []
    for w in state.present():
        if w.role not in ("operator", "floater") or w.station == station_id or w.busy_with:
            continue
        if w.station is not None and not include_assigned:
            continue
        level = w.level(station_id, on=today)
        if level < 2:
            continue
        if w.hours_worked + needed > MAX_DAILY_HOURS:
            continue
        dist = zone_distance(w.zone, zone)
        score = level * 10 + (15 if w.station is None else 0) - dist * 5 - w.hours_worked
        skill = "trainer" if level == 3 else "qualified"
        where = "free" if w.station is None else f"currently at {w.station}"
        reason = f"{skill} on {station_id}, {where}, zone {w.zone}, {w.hours_worked:.1f}h worked"
        out.append(Candidate(w.id, w.name, w.zone, score, reason, level, w.station))
    out.sort(key=lambda c: -c.score)
    return out[:limit]


def maintenance_candidates(state: FactoryState, zone: str, limit: int = 3) -> list[Candidate]:
    out = []
    for w in state.present():
        if w.role != "maintenance" or w.busy_with:
            continue
        dist = zone_distance(w.zone, zone)
        out.append(Candidate(w.id, w.name, w.zone, 10 - dist * 3,
                             f"maintenance, free, in zone {w.zone} ({dist} zone(s) away)"))
    out.sort(key=lambda c: -c.score)
    return out[:limit]


def warden_donors(state: FactoryState, zone: str, limit: int = 3) -> list[Candidate]:
    """Fire wardens who can move to `zone` without leaving their own zone without a warden."""
    out = []
    for z in ZONE_ORDER:
        if z == zone:
            continue
        wardens = state.fire_wardens(z)
        if len(wardens) < 2:
            continue
        for w in wardens:
            if w.busy_with:
                continue
            dist = zone_distance(z, zone)
            score = 10 - dist * 3 + (5 if w.station is None else 0)
            note = "" if w.station is None else f"; {w.station} needs a backfill"
            out.append(Candidate(w.id, w.name, z, score,
                                 f"fire warden, zone {z} keeps {len(wardens) - 1} warden(s){note}",
                                 current_station=w.station))
    out.sort(key=lambda c: -c.score)
    return out[:limit]
