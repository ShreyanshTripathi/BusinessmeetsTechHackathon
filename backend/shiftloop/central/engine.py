"""Central intelligence: connects the three specialised agents and decides what the supervisor sees."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..models import Event, Incident, PriorityPoint, Severity
from ..state import Emergency, FactoryState
from .fusion import belongs_to, category_of, likely_cause, merged_category, title_for
from .ranking import assess
from .recommend import recommend

ATTENTION_BUDGET = 3
HOLD_MARGIN = 5.0  # an active incident keeps its slot unless a same-tier challenger beats it by this much
HISTORY_STEP = 2.0  # record a history point when the score moved at least this much
TREND_WINDOW = timedelta(minutes=10)
TREND_MIN = 3.0  # score change over the window that counts as rising or falling


class CentralIntelligence:
    def __init__(self, attention_budget: int = ATTENTION_BUDGET) -> None:
        self.budget = attention_budget
        self.active_events: dict[str, dict[str, Event]] = {}  # incident id -> event key -> latest event

    # ------------------------------------------------------------------ ingest

    def ingest(self, state: FactoryState, events: list[Event]) -> list[Incident]:
        changed: dict[str, Incident] = {}
        for e in events:
            state.events.append(e)
            inc = self._clear(state, e) if e.cleared else self._merge(state, e)
            if inc is not None:
                changed[inc.id] = inc
        if changed:
            self.rerank(state)
        return list(changed.values())

    def _live(self, state: FactoryState) -> list[Incident]:
        return [i for i in state.incidents.values() if i.status in ("open", "accepted")]

    def _clear(self, state: FactoryState, e: Event) -> Incident | None:
        for inc in self._live(state):
            if e.key in inc.event_keys:
                inc.event_keys.remove(e.key)
                self.active_events[inc.id].pop(e.key, None)
                inc.event_ids.append(e.id)
                inc.updated = state.now
                if not inc.event_keys:
                    inc.status = "resolved"
                    inc.visibility = "held"
                else:
                    self._refresh(state, inc)
                return inc
        return None

    def _merge(self, state: FactoryState, e: Event) -> Incident:
        target = next((i for i in self._live(state) if belongs_to(e, i, list(self.active_events[i.id].values()))), None)
        if target is None:
            target = Incident(id=state.next_id("inc"), title="", zone=e.zone, severity=e.severity,
                              category=category_of(e), opened=state.now, updated=state.now)
            state.incidents[target.id] = target
            self.active_events[target.id] = {}
            previous_severity = None
        else:
            previous_severity = target.severity
        new_finding = e.key not in target.event_keys
        self.active_events[target.id][e.key] = e
        if new_finding:
            target.event_keys.append(e.key)
        target.event_ids.append(e.id)
        target.updated = state.now
        if e.station and e.station not in target.stations:
            target.stations.append(e.station)
        if e.agent not in target.agents:
            target.agents.append(e.agent)
        self._refresh(state, target)
        escalated = previous_severity is None or target.severity.rank > previous_severity.rank
        if target.status == "accepted" and (escalated or new_finding):
            target.status = "open"  # new or worse information after the supervisor acted: needs attention again
        if escalated and target.severity.rank >= Severity.high.rank:
            level = "critical" if target.severity == Severity.critical else "warning"
            state.notify(level, target.title, target.recommendation.summary if target.recommendation else "", target.id)
        self._maybe_emergency(state, target)
        return target

    def _refresh(self, state: FactoryState, inc: Incident) -> None:
        events = list(self.active_events[inc.id].values())
        inc.severity = max((e.severity for e in events), key=lambda s: s.rank)
        inc.category = merged_category(events)
        inc.confidence = round(min(e.confidence for e in events), 2)
        inc.title = title_for(events)
        inc.likely_cause = likely_cause(events)
        inc.evidence = [line for e in events for line in e.evidence]
        inc.predictions = [{"event_id": e.id, "model": e.data["model"], "risk": e.confidence,  # same rounding as the evidence text
                            "explanation": e.data.get("explanation", ""), "drivers": e.data.get("drivers", [])}
                           for e in events if e.data.get("model")]
        inc.recommendation = recommend(state, inc, events)

    def _maybe_emergency(self, state: FactoryState, inc: Incident) -> None:
        rec = inc.recommendation
        if rec and rec.action == "emergency" and state.emergency is None:
            state.emergency = Emergency(zone=rec.target, started=state.now, reason=inc.title, incident_id=inc.id)

    # ------------------------------------------------------------------ ranking & attention

    def rerank(self, state: FactoryState) -> None:
        """Re-score every live incident, fill the attention slots and record what changed. Runs every minute."""
        now = state.now
        live = self._live(state)
        for inc in live:
            waiting = _minutes(inc.waiting_since, now) if inc.waiting_since else 0.0
            a = assess(inc, list(self.active_events[inc.id].values()), state, waiting)
            inc.tier, inc.score, inc.score_parts = a["tier"], a["score"], a["parts"]
            inc.priority_reason, inc.priority_cause = a["reason"], a["cause"]
            inc.waiting_min = int(waiting)
        # low-severity items never take a slot; incumbents keep theirs unless clearly beaten (no flicker)
        eligible = sorted((i for i in live if i.status == "open" and i.severity.rank >= Severity.medium.rank),
                          key=lambda i: (i.tier, -(i.score + (HOLD_MARGIN if i.visibility == "active" else 0))))
        slots = {i.id for i in eligible[: self.budget]}
        for inc in live:
            inc.visibility = "active" if inc.id in slots else "held"
            if inc.visibility == "held":
                inc.waiting_since = None
            elif inc.waiting_since is None:
                inc.waiting_since = now
        for inc in state.incidents.values():
            _track(inc, now)

    def open_incidents(self, state: FactoryState) -> list[Incident]:
        return sorted((i for i in state.incidents.values() if i.status == "open"), key=rank_key)

    def events_for(self, incident_id: str) -> list[Event]:
        return list(self.active_events.get(incident_id, {}).values())

    def attention_summary(self, state: FactoryState) -> dict:
        active = sum(1 for i in self.open_incidents(state) if i.visibility == "active")
        return {"signals": state.signals, "events": len(state.events), "incidents": len(state.incidents),
                "active": active, "held_back": max(0, state.signals - active)}


# --------------------------------------------------------------------------- priority over time


def rank_key(inc: Incident) -> tuple:
    return -inc.score, -inc.score_parts.get("total", 0)


def _minutes(since: datetime, now: datetime) -> float:
    return (now - since).total_seconds() / 60


def _change(last: PriorityPoint | None, inc: Incident) -> str | None:
    if last is None:
        return "opened"
    if inc.status != last.status:
        return "reopened" if inc.status == "open" else inc.status
    if inc.status in ("resolved", "dismissed"):
        return None
    if inc.tier != last.tier:
        return "tier_up" if inc.tier < last.tier else "tier_down"
    if inc.visibility != last.visibility:
        return "promoted" if inc.visibility == "active" else "demoted"
    if inc.priority_cause != last.cause:
        return "cause"
    if abs(inc.score - last.score) >= HISTORY_STEP:
        return "score"
    return None


def _track(inc: Incident, now: datetime) -> None:
    """Append a history point when the priority moved; keep the trend fields current."""
    last = inc.history[-1] if inc.history else None
    change = _change(last, inc)
    if change is not None:
        point = PriorityPoint(time=now, score=inc.score, tier=inc.tier, visibility=inc.visibility,
                              status=inc.status, reason=inc.priority_reason, cause=inc.priority_cause,
                              change=change)
        if last is not None and last.time == now:  # several reranks in one minute: keep one point
            if change == "score" or last.change == "opened":
                point.change = last.change
            inc.history[-1] = point
        else:
            inc.history.append(point)
    if inc.status in ("open", "accepted"):
        cutoff = now - TREND_WINDOW
        past = next((p for p in reversed(inc.history) if p.time <= cutoff), inc.history[0])
        inc.score_delta_10m = round(inc.score - past.score, 1)
        inc.trend = ("rising" if inc.score_delta_10m >= TREND_MIN else
                     "falling" if inc.score_delta_10m <= -TREND_MIN else "steady")
