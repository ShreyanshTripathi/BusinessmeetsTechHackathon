"""Common behaviour for the specialised agents.

Agents describe the *conditions* they currently see. `_sync` turns that into events:
a new condition is emitted once, a severity increase is re-emitted, and a condition that disappears
is emitted again with `cleared=True`. This keeps the supervisor from being flooded with repeats.
"""
from __future__ import annotations

from ..models import Event, Severity
from ..state import FactoryState


class BaseAgent:
    name: str = "base"

    def __init__(self) -> None:
        self._active: dict[str, Event] = {}

    def handle(self, reading, state: FactoryState) -> list[Event]:
        return []

    def tick(self, state: FactoryState) -> list[Event]:
        return []

    @property
    def active(self) -> list[Event]:
        return list(self._active.values())

    def condition(self, state: FactoryState, *, key: str, type: str, zone: str, severity: Severity | str,
                  station: str | None = None, confidence: float = 1.0, evidence: list[str] | None = None,
                  suggested_action: str = "", data: dict | None = None) -> Event:
        return Event(id="", agent=self.name, time=state.now, zone=zone, station=station, type=type,
                     severity=Severity(severity), confidence=confidence, evidence=evidence or [],
                     suggested_action=suggested_action, key=f"{self.name}:{key}", data=data or {})

    def forecast_condition(self, state: FactoryState, ml: dict, key: str, inbox_from: float = 0.8) -> Event:
        """An ML prediction as a condition.

        Forecasts never rank above medium, so live problems come first; under `inbox_from` risk they are low,
        which keeps them out of the supervisor's inbox (they show as model forecasts instead).
        """
        severity = Severity.medium if ml["confidence"] >= inbox_from else Severity.low
        return self.condition(state, key=key, type=ml["type"], zone=ml["zone"], station=ml.get("station"),
                              severity=severity, confidence=ml["confidence"], evidence=ml["evidence"],
                              suggested_action=ml["suggested_action"], data=ml["data"])

    def _sync(self, state: FactoryState, conditions: list[Event], scope: str = "") -> list[Event]:
        """Diff current conditions (within `scope`, a key prefix) against the active set."""
        prefix = f"{self.name}:{scope}"
        out: list[Event] = []
        current = {c.key: c for c in conditions}
        for key, cond in current.items():
            prev = self._active.get(key)
            if prev is None or cond.severity.rank > prev.severity.rank:
                ev = cond.model_copy(update={"id": state.next_id("evt"), "time": state.now})
                self._active[key] = ev
                out.append(ev)
            else:
                # same or lower severity: refresh details silently
                self._active[key] = prev.model_copy(update={"severity": cond.severity, "evidence": cond.evidence,
                                                            "data": cond.data, "confidence": cond.confidence})
        for key in [k for k in self._active if k.startswith(prefix) and k not in current]:
            prev = self._active.pop(key)
            out.append(prev.model_copy(update={"id": state.next_id("evt"), "time": state.now, "cleared": True}))
        return out
