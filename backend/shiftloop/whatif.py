"""'What happens if I move this person?' Checked on a copy of the state; nothing real changes."""
from __future__ import annotations

import copy

from .factory import ZONE_ORDER
from .matching import MAX_DAILY_HOURS
from .state import SHIFT_HOURS, FactoryState


def _snapshot(state: FactoryState) -> dict:
    return {
        "uncovered": {s for s in state.layout.stations if state.station_occupant(s) is None},
        "wardens": {z: len(state.fire_wardens(z)) for z in ZONE_ORDER},
        "aiders": {z: len(state.first_aiders(z)) for z in ZONE_ORDER},
    }


def what_if(state: FactoryState, worker_id: str, to_station: str) -> dict:
    sim = copy.deepcopy(state)
    w = sim.workers[worker_id]
    before = _snapshot(sim)
    from_station = w.station
    level = w.level(to_station, on=sim.now.date())
    displaced = sim.assign(worker_id, to_station)
    after = _snapshot(sim)

    warnings, benefits = [], []
    if level < 2:
        warnings.append(f"{w.name} is not qualified on {to_station} (level {level})")
    if from_station and from_station in after["uncovered"]:
        warnings.append(f"{from_station} would be left without an operator")
    if displaced:
        warnings.append(f"{sim.workers[displaced].name} would be displaced from {to_station}")
    for z in ZONE_ORDER:
        if before["wardens"][z] > 0 and after["wardens"][z] == 0:
            warnings.append(f"Zone {z} would have no fire warden")
        if before["aiders"][z] > 0 and after["aiders"][z] == 0:
            warnings.append(f"Zone {z} would have no first aider")
    remaining = max(0.0, SHIFT_HOURS - sim.shift_elapsed_h)
    if w.hours_worked + remaining > MAX_DAILY_HOURS:
        warnings.append(f"{w.name} would exceed {MAX_DAILY_HOURS:.0f}h today")
    if to_station in before["uncovered"] and level >= 2:
        benefits.append(f"{to_station} covered by a qualified operator ({w.name}, level {level})")
    return {"worker": worker_id, "worker_name": w.name, "from_station": from_station, "to_station": to_station,
            "ok": not warnings, "warnings": warnings, "benefits": benefits}
