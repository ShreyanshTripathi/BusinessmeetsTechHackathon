"""Wires everything together: simulator → bus → specialised agents → central intelligence."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import actions
from .agents.assembly import AssemblyAgent
from .agents.safety import SafetyAgent
from .agents.staffing import StaffingAgent
from .bus import EventBus
from .central.engine import CentralIntelligence
from .central.recommend import next_break
from .models import Decision
from .simulator.shift import ShiftSimulator
from .state import FactoryState

REPAIR_MIN = 20
MINUTE = timedelta(minutes=1)


class Plant:
    def __init__(self, seed: int = 42, scenario: str = "demo") -> None:
        self.state = FactoryState.create(seed)
        self.bus = EventBus()
        self.agents = [StaffingAgent(), AssemblyAgent(), SafetyAgent()]
        self.central = CentralIntelligence()
        self.sim = ShiftSimulator(self.state, seed=seed, scenario=scenario)
        self.bus.subscribe("reading", self._on_reading)
        self.bus.subscribe("events", self._on_events)
        self.listeners: list = []  # callables notified after each simulated minute

    # ------------------------------------------------------------------ pipeline

    def _on_reading(self, reading) -> None:
        self.state.record(reading)
        for agent in self.agents:
            events = agent.handle(reading, self.state)
            if events:
                self.bus.publish("events", events)

    def _on_events(self, events) -> None:
        self.central.ingest(self.state, events)

    def ingest(self, reading) -> None:
        """Readings from outside the simulator, e.g. a camera frame analysed by the vision service."""
        self.bus.publish("reading", reading)

    def step(self, minutes: int = 1) -> None:
        for _ in range(minutes):
            for reading in self.sim.generate():
                self.bus.publish("reading", reading)
            for agent in self.agents:
                events = agent.tick(self.state)
                if events:
                    self.bus.publish("events", events)
            actions.check_escalations(self.state)
            actions.release_resolved(self.state)
            self.sim.account()
            self.state.advance(MINUTE)
            for listener in self.listeners:
                listener()

    def run_until(self, target: datetime) -> None:
        while self.state.now < target:
            self.step(1)

    # ------------------------------------------------------------------ supervisor actions

    def decide(self, incident_id: str, decision: str, reason: str = "", assignments: list[dict] | None = None) -> Decision:
        d = actions.decide(self.state, self.central, incident_id, decision, reason, assignments)
        if decision != "dismiss":
            self._react(incident_id)
        return d

    def _react(self, incident_id: str) -> None:
        """Let the simulated plant respond to what the supervisor set in motion."""
        inc = self.state.incidents[incident_id]
        types = {e.type: e for e in self.central.events_for(incident_id)}
        now = self.state.now
        for station in inc.stations:
            if "station_stopped" in types:
                self.sim.schedule_repair(station, now + timedelta(minutes=REPAIR_MIN))
            elif "predicted_tool_failure" in types:
                brk = next_break(now)
                eta = types["predicted_tool_failure"].data.get("eta_min")
                planned = brk is not None and eta is not None and (brk - now).total_seconds() / 60 < eta
                self.sim.schedule_repair(station, brk if planned else now + timedelta(minutes=5))
            if "defect_pattern" in types:
                self.sim.stop_defects(station)
            if "part_shortage" in types:
                self.sim.replenish(station)

    def confirm_proposal(self, proposal_id: str) -> dict:
        """The supervisor confirmed something the chat copilot proposed."""
        p = self.state.proposals[proposal_id]
        if p.status != "pending":
            raise ValueError(f"proposal {proposal_id} is already {p.status}")
        if p.kind == "assign":
            worker, station = p.params["worker"], p.params["station"]
            displaced = self.state.assign(worker, station)
            applied = [f"{self.state.workers[worker].name} → {station}"]
            if displaced:
                applied.append(f"{self.state.workers[displaced].name} freed")
            self.state.decisions.append(Decision(
                id=self.state.next_id("dec"), time=self.state.now, incident_id="chat", incident_title=p.description,
                recommended=p.description, decision="accept", reason=p.params.get("reason", ""), applied=applied,
                agents=["central"], decided_by="supervisor (via chat)"))
        else:
            d = self.decide(p.params["incident_id"], p.params["decision"], p.params.get("reason", ""))
            d.decided_by = "supervisor (via chat)"
            applied = d.applied
        p.status = "confirmed"
        return {"proposal": p.model_dump(), "applied": applied or ["recorded"]}

    def reject_proposal(self, proposal_id: str) -> dict:
        p = self.state.proposals[proposal_id]
        p.status = "rejected"
        return {"proposal": p.model_dump()}

    def all_clear(self) -> dict:
        return actions.all_clear(self.state)

    def acknowledge(self, escalation_id: str):
        return actions.acknowledge_escalation(self.state, escalation_id)
