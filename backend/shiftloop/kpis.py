"""Shift KPIs for the dashboard header."""
from __future__ import annotations

from .central.engine import CentralIntelligence
from .state import FactoryState


def kpis(state: FactoryState, central: CentralIntelligence) -> dict:
    takt = next(iter(state.layout.stations.values())).takt_s
    plan = round(state.shift_elapsed_h * 3600 / takt)
    built = int(state.cars_built)
    open_ = central.open_incidents(state)
    downtime = dict(sorted(((k, round(v, 1)) for k, v in state.downtime_min.items() if v > 0),
                           key=lambda kv: -kv[1]))
    return {
        "time": state.now.isoformat(),
        "cars_built": built,
        "plan": plan,
        "output_pct": round(built / plan * 100) if plan else 100,
        "downtime_min": downtime,
        "downtime_total_min": round(sum(downtime.values()), 1),
        "defects": sum(state.defects.values()),
        "open_safety": sum(1 for i in open_ if i.category == "safety"),
        "open_incidents": len(open_),
        "impact": {k: round(v, 1) for k, v in state.impact.items()},
    }
