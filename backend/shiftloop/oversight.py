"""Oversight: who decided what, how often the AI was overridden, and what data each agent uses."""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from .central.engine import CentralIntelligence
from .models import Incident
from .state import FactoryState

DATA_USE = {
    "staffing": {"uses": ["shift roster", "absences", "qualification matrix", "safety roles", "hours worked"],
                 "purpose": "cover stations with qualified people within legal working-time limits",
                 "never": ["performance scoring", "speed or error rates per person"]},
    "assembly": {"uses": ["station status", "cycle time per station", "tool torque", "part stock",
                          "quality camera detections"],
                 "purpose": "detect stops, real slowdowns, tool wear, shortages and defect patterns",
                 "never": ["linking cycle times or defects to named workers"]},
    "safety": {"uses": ["smoke/heat/gas sensors", "battery temperature", "fire, exit and PPE cameras (zone level)"],
               "purpose": "detect fire, overheating, gas, blocked exits and missing protective equipment",
               "never": ["face recognition", "identifying who is not wearing PPE"]},
    "central": {"uses": ["events from the three agents", "supervisor decisions"],
                "purpose": "merge, rank and recommend; every action needs a human decision",
                "never": ["acting without supervisor confirmation"]},
}


def oversight_report(state: FactoryState, central: CentralIntelligence) -> dict:
    counts = Counter(d.decision for d in state.decisions)
    total = len(state.decisions)
    overrides = counts["modify"] + counts["dismiss"]
    agents = {}
    for name in ("staffing", "assembly", "safety"):
        involved = [i for i in state.incidents.values() if name in i.agents]
        decided = [d for d in state.decisions if name in d.agents]
        agents[name] = {
            "events": sum(1 for e in state.events if e.agent == name and not e.cleared),
            "incidents": len(involved),
            "decisions": len(decided),
            "accepted": sum(1 for d in decided if d.decision == "accept"),
            "overridden": sum(1 for d in decided if d.decision != "accept"),
        }
    expert_queue = sum(1 for e in state.events if e.type == "inspection_unsure")
    return {
        "decisions": {"total": total, "accept": counts["accept"], "modify": counts["modify"],
                      "dismiss": counts["dismiss"]},
        "override_rate": round(overrides / total, 2) if total else 0.0,
        "human_decided_pct": 100,  # the system has no path that applies an action without a supervisor decision
        "agents": agents,
        "expert_queue": expert_queue,
        "attention": central.attention_summary(state),
        "priority": priority_summary(state),
        "log": [d.model_dump(mode="json") for d in reversed(state.decisions)],
        "data_use": DATA_USE,
        "works_council": {
            "individual_performance_scoring": False,
            "all_decisions_by_humans": True,
            "camera_data": "zone-level detections only; no identities stored",
            "decision_log_retained": True,
        },
    }


MOVES = ("promoted", "demoted", "tier_up", "tier_down", "reopened")


def _active_since(inc: Incident, until: datetime) -> datetime | None:
    """When the incident last entered the active list before `until` (None if it was not active then)."""
    since = None
    for p in inc.history:
        if p.time >= until:  # the decision itself is recorded at `until`
            break
        if p.visibility == "active" and p.status == "open":
            since = since or p.time
        else:
            since = None
    return since


def priority_summary(state: FactoryState) -> dict:
    """How priorities moved over the shift, and how long active incidents waited for a decision."""
    moves = sorted(({"time": p.time.isoformat(), "incident_id": inc.id, "title": inc.title, "change": p.change,
                     "tier": p.tier, "reason": p.reason}
                    for inc in state.incidents.values() for p in inc.history if p.change in MOVES),
                   key=lambda m: m["time"], reverse=True)
    waits = []
    for d in state.decisions:
        inc = state.incidents.get(d.incident_id)
        since = _active_since(inc, d.time) if inc else None
        if since is not None:
            waits.append((d.time - since).total_seconds() / 60)
    return {"moves": moves[:50], "counts": dict(Counter(m["change"] for m in moves)),
            "decisions_timed": len(waits),
            "avg_minutes_active_to_decision": round(sum(waits) / len(waits), 1) if waits else None}
