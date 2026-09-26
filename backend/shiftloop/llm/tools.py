"""Tools the chat copilot can call. Read tools query live state; propose_* tools only stage actions."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..kpis import kpis
from ..matching import cover_candidates
from ..models import Proposal
from ..whatif import what_if

if TYPE_CHECKING:
    from ..plant import Plant


def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or []}


STATION = {"type": "string", "description": "Station id, e.g. S12"}
WORKER = {"type": "string", "description": "Worker id (e.g. W027) or name"}

TOOLS: list[dict] = [
    {"name": "get_incidents",
     "description": "Current incidents ranked by urgency, with merged evidence, likely cause and recommendation. "
                    "Held incidents are lower priority ones not shown on the supervisor's inbox.",
     "input_schema": _schema({"include_held": {"type": "boolean", "description": "Also return held incidents"}})},
    {"name": "get_station",
     "description": "Live status of one station: operator, qualification, cycle time, torque, stock, downtime.",
     "input_schema": _schema({"station_id": STATION}, ["station_id"])},
    {"name": "get_zone",
     "description": "One zone (A-D): people present, fire wardens, first aiders, station status, sensor readings.",
     "input_schema": _schema({"zone": {"type": "string", "enum": ["A", "B", "C", "D"]}}, ["zone"])},
    {"name": "get_worker",
     "description": "One worker: role, zone, station, qualifications (0 untrained, 1 trainee, 2 qualified, "
                    "3 trainer), safety roles, hours worked today, status.",
     "input_schema": _schema({"name_or_id": WORKER}, ["name_or_id"])},
    {"name": "find_cover",
     "description": "Qualified, available people who could take over a station, best first, within working-time limits.",
     "input_schema": _schema({"station_id": STATION,
                              "include_assigned": {"type": "boolean",
                                                   "description": "Also include people currently at another station"}},
                             ["station_id"])},
    {"name": "get_kpis",
     "description": "Shift KPIs: cars built vs plan, downtime per station, defects, open safety issues, impact.",
     "input_schema": _schema({})},
    {"name": "get_recent_events",
     "description": "Recent events from the specialised agents (staffing, assembly, safety), newest first.",
     "input_schema": _schema({"agent": {"type": "string", "enum": ["staffing", "assembly", "safety"]},
                              "station_id": STATION,
                              "limit": {"type": "integer", "description": "Max events (default 15)"}})},
    {"name": "what_if",
     "description": "Check the effect of moving a worker to a station (qualification, gaps, fire warden cover, "
                    "hours) without changing anything.",
     "input_schema": _schema({"worker": WORKER, "station_id": STATION}, ["worker", "station_id"])},
    {"name": "propose_assignment",
     "description": "Stage moving a worker to a station. Nothing changes until the supervisor confirms it in the UI.",
     "input_schema": _schema({"worker": WORKER, "station_id": STATION,
                              "reason": {"type": "string", "description": "Why, in one sentence"}},
                             ["worker", "station_id", "reason"])},
    {"name": "propose_decision",
     "description": "Stage accepting or dismissing an incident's recommendation. The supervisor must confirm.",
     "input_schema": _schema({"incident_id": {"type": "string"},
                              "decision": {"type": "string", "enum": ["accept", "dismiss"]},
                              "reason": {"type": "string"}}, ["incident_id", "decision"])},
]


class ToolExecutor:
    def __init__(self, plant: "Plant") -> None:
        self.plant = plant
        self.proposals: list[Proposal] = []

    @property
    def state(self):
        return self.plant.state

    def run(self, name: str, args: dict[str, Any]) -> dict:
        fn = getattr(self, name, None) if name in {t["name"] for t in TOOLS} else None
        if fn is None:
            return {"error": f"unknown tool {name!r}"}
        try:
            return fn(**args)
        except (KeyError, ValueError, TypeError) as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------ lookups

    def _worker(self, name_or_id: str):
        ws = self.state.workers
        if name_or_id in ws:
            return ws[name_or_id]
        hits = [w for w in ws.values() if name_or_id.lower() in w.name.lower()]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise KeyError(f"no worker matching {name_or_id!r}")
        raise ValueError(f"{name_or_id!r} matches several workers: {', '.join(w.name for w in hits)}")

    def _station_id(self, station_id: str) -> str:
        sid = station_id.upper().strip()
        if sid not in self.state.layout.stations:
            raise KeyError(f"no station {station_id!r}")
        return sid

    # ------------------------------------------------------------------ read tools

    def get_incidents(self, include_held: bool = False) -> dict:
        central = self.plant.central
        out = []
        for inc in central.open_incidents(self.state):
            if inc.visibility == "held" and not include_held:
                continue
            out.append({"id": inc.id, "title": inc.title, "severity": inc.severity.value, "category": inc.category,
                        "visibility": inc.visibility, "score": inc.score, "zone": inc.zone, "stations": inc.stations,
                        "agents": inc.agents, "likely_cause": inc.likely_cause, "evidence": inc.evidence[:6],
                        "recommendation": inc.recommendation.model_dump() if inc.recommendation else None})
        return {"incidents": out, "attention": central.attention_summary(self.state)}

    def get_station(self, station_id: str) -> dict:
        sid = self._station_id(station_id)
        st = self.state.layout.stations[sid]
        occ = self.state.station_occupant(sid)
        last = self.state.last_station.get(sid)
        return {"station": sid, "name": st.name, "zone": st.zone, "status": st.status,
                "safety_critical": st.safety_critical,
                "operator": None if occ is None else {"id": occ.id, "name": occ.name,
                                                      "level": occ.level(sid, on=self.state.now.date())},
                "cycle_time_s": last.cycle_time_s if last else None, "takt_s": st.takt_s,
                "torque_nm": last.torque_nm if last else None, "stock": last.stock if last else {},
                "downtime_min": round(self.state.downtime_min.get(sid, 0), 1),
                "defects": self.state.defects.get(sid, 0)}

    def get_zone(self, zone: str) -> dict:
        zone = zone.upper()
        if zone not in {"A", "B", "C", "D"}:
            raise ValueError("zone must be A, B, C or D")
        st = self.state
        sensors = {sid: r.value for sid, r in st.last_sensor.items() if r.zone == zone}
        return {"zone": zone, "people": st.zone_headcount(zone),
                "fire_wardens": [w.name for w in st.fire_wardens(zone)],
                "first_aiders": [w.name for w in st.first_aiders(zone)],
                "stations": {sid: s.status for sid, s in st.layout.stations.items() if s.zone == zone},
                "sensors": sensors, "exits": st.layout.zone(zone).exits,
                "emergency": bool(st.emergency and st.emergency.zone == zone)}

    def get_worker(self, name_or_id: str) -> dict:
        w = self._worker(name_or_id)
        return {"id": w.id, "name": w.name, "role": w.role, "zone": w.zone, "station": w.station, "status": w.status,
                "qualifications": w.qualifications, "fire_warden": w.fire_warden, "first_aider": w.first_aider,
                "hours_worked": round(w.hours_worked, 2), "busy_with": w.busy_with, "languages": w.languages}

    def find_cover(self, station_id: str, include_assigned: bool = False) -> dict:
        sid = self._station_id(station_id)
        cands = cover_candidates(self.state, sid, include_assigned=include_assigned)
        return {"station": sid, "candidates": [c.as_dict() for c in cands]}

    def get_kpis(self) -> dict:
        return kpis(self.state, self.plant.central)

    def get_recent_events(self, agent: str | None = None, station_id: str | None = None, limit: int = 15) -> dict:
        evs = [e for e in reversed(self.state.events)
               if (agent is None or e.agent == agent) and (station_id is None or e.station == station_id.upper())]
        return {"events": [{"time": e.time.strftime("%H:%M"), "agent": e.agent, "type": e.type, "zone": e.zone,
                            "station": e.station, "severity": e.severity.value, "cleared": e.cleared,
                            "evidence": e.evidence} for e in evs[:limit]]}

    def what_if(self, worker: str, station_id: str) -> dict:
        return what_if(self.state, self._worker(worker).id, self._station_id(station_id))

    # ------------------------------------------------------------------ proposals (staged, never applied here)

    def _stage(self, kind: str, description: str, params: dict) -> dict:
        p = Proposal(id=self.state.next_id("prp"), kind=kind, description=description, params=params)
        self.state.proposals[p.id] = p
        self.proposals.append(p)
        return {"proposal_id": p.id, "status": "pending", "description": description,
                "note": "Shown to the supervisor with Confirm / Reject buttons; not applied yet."}

    def propose_assignment(self, worker: str, station_id: str, reason: str = "") -> dict:
        w, sid = self._worker(worker), self._station_id(station_id)
        check = what_if(self.state, w.id, sid)
        desc = f"Move {w.name} to {sid}" + (f": {reason}" if reason else "")
        out = self._stage("assign", desc, {"worker": w.id, "station": sid, "reason": reason})
        out["warnings"] = check["warnings"]
        return out

    def propose_decision(self, incident_id: str, decision: str, reason: str = "") -> dict:
        inc = self.state.incidents[incident_id]
        return self._stage("incident_decision", f"{decision.title()}: {inc.title}",
                           {"incident_id": incident_id, "decision": decision, "reason": reason})
