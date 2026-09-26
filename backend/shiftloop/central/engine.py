"""Central intelligence: connects the three specialised agents and decides what the supervisor sees."""
from __future__ import annotations

from ..models import Event, Incident, Severity
from ..state import Emergency, FactoryState
from .fusion import belongs_to, category_of, likely_cause, merged_category, title_for
from .ranking import score
from .recommend import recommend

ATTENTION_BUDGET = 3


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
        live = self._live(state)
        for inc in live:
            inc.score = score(inc, list(self.active_events[inc.id].values()))
        open_ = sorted((i for i in live if i.status == "open"), key=lambda i: -i.score)
        slots = [i for i in open_ if i.severity.rank >= Severity.medium.rank][: self.budget]
        for inc in open_:
            inc.visibility = "active" if inc in slots else "held"
        for inc in live:
            if inc.status == "accepted":
                inc.visibility = "held"

    def open_incidents(self, state: FactoryState) -> list[Incident]:
        return sorted((i for i in state.incidents.values() if i.status == "open"), key=lambda i: -i.score)

    def events_for(self, incident_id: str) -> list[Event]:
        return list(self.active_events.get(incident_id, {}).values())

    def attention_summary(self, state: FactoryState) -> dict:
        active = sum(1 for i in self.open_incidents(state) if i.visibility == "active")
        return {"signals": state.signals, "events": len(state.events), "incidents": len(state.incidents),
                "active": active, "held_back": max(0, state.signals - active)}
