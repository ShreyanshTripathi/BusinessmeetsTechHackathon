"""Priority over time for the timeline page: per incident, bars, score points and markers, ready to draw."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..central.engine import rank_key
from ..central.ranking import BAND, TIER_LABELS
from ..models import Incident
from ..state import SHIFT_START

if TYPE_CHECKING:
    from ..plant import Plant

MARKER_LABELS = {"opened": "Opened", "promoted": "Moved to active", "demoted": "Moved to held",
                 "tier_up": "Tier up", "tier_down": "Tier down", "cause": "Now", "accepted": "Accepted",
                 "reopened": "Reopened", "resolved": "Resolved", "dismissed": "Dismissed"}
DECISION_MARKERS = {"accepted", "resolved", "dismissed"}  # the label says it all
LIVE = ("open", "accepted")


def _incident(inc: Incident) -> dict:
    segments, markers, previous_tier = [], [], None
    for p in inc.history:
        if p.change != "score":
            text = MARKER_LABELS[p.change]
            if p.change in ("tier_up", "tier_down"):
                text += f" ({previous_tier} → {p.tier})"
            if p.change not in DECISION_MARKERS:
                text += f": {p.reason}"
            markers.append({"t": p.time.isoformat(), "kind": p.change, "text": text})
        previous_tier = p.tier
        t = p.time.isoformat()
        if p.status not in LIVE:  # resolved or dismissed: the last bar ends here
            if segments:
                segments[-1]["to"] = t
            break
        visibility = "in_progress" if p.status == "accepted" else p.visibility
        if segments and (segments[-1]["visibility"], segments[-1]["tier"]) == (visibility, p.tier):
            segments[-1]["score"] = p.score
            continue
        if segments:
            segments[-1]["to"] = t
        segments.append({"from": t, "to": None, "visibility": visibility, "tier": p.tier, "score": p.score})
    return {"id": inc.id, "title": inc.title, "category": inc.category, "status": inc.status,
            "visibility": inc.visibility, "tier": inc.tier, "score": inc.score, "trend": inc.trend,
            "priority_reason": inc.priority_reason, "opened": inc.opened.isoformat(), "segments": segments,
            "points": [{"t": p.time.isoformat(), "score": p.score} for p in inc.history], "markers": markers}


def priority_timeline(plant: "Plant") -> dict:
    """Live incidents first in ranking order (active, held, in progress), then closed ones, newest first."""
    incidents = [i for i in plant.state.incidents.values() if i.history]
    open_ = sorted((i for i in incidents if i.status == "open"), key=lambda i: (i.visibility != "active", rank_key(i)))
    accepted = sorted((i for i in incidents if i.status == "accepted"), key=rank_key)
    closed = sorted((i for i in incidents if i.status not in LIVE), key=lambda i: i.history[-1].time, reverse=True)
    return {
        "shift_start": SHIFT_START.isoformat(),
        "now": plant.state.now.isoformat(),
        "tiers": [{"tier": t, "label": label, "min": (3 - t) * BAND, "max": (4 - t) * BAND}
                  for t, label in enumerate(TIER_LABELS)],
        "incidents": [_incident(i) for i in open_ + accepted + closed],
    }
