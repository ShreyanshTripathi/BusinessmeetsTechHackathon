"""Oversight: who decided what, how often the AI was overridden, and what data each agent uses."""
from __future__ import annotations

from collections import Counter

from .central.engine import CentralIntelligence
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
        "log": [d.model_dump(mode="json") for d in reversed(state.decisions)],
        "data_use": DATA_USE,
        "works_council": {
            "individual_performance_scoring": False,
            "all_decisions_by_humans": True,
            "camera_data": "zone-level detections only; no identities stored",
            "decision_log_retained": True,
        },
    }
