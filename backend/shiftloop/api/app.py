"""FastAPI app: REST for supervisor actions, WebSocket for live snapshots, and the simulation runner."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from ..factory import zone_of

from ..llm.chat import ChatCopilot
from ..llm.handover import write_handover
from ..oversight import oversight_report
from ..plant import Plant
from ..vision.service import VisionService, detectors_from_env
from ..whatif import what_if
from .snapshot import snapshot


class SimCommand(BaseModel):
    action: Literal["start", "pause", "step", "speed", "reset"]
    minutes: int = 1
    speed: float | None = None  # simulated minutes per real second
    scenario: Literal["demo", "quiet"] | None = None


class DecisionIn(BaseModel):
    decision: Literal["accept", "modify", "dismiss"]
    reason: str = ""
    assignments: list[dict] | None = None


class ChatIn(BaseModel):
    message: str
    history: list[dict] = []
    language: Literal["en", "de", "pl"] = "en"


class LanguageIn(BaseModel):
    language: Literal["en", "de", "pl"] = "en"


class WhatIfIn(BaseModel):
    worker: str
    station: str


class CheckinIn(BaseModel):
    worker: str


class ReportIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    zone: Literal["A", "B", "C", "D"]
    station: str | None = None

    @model_validator(mode="after")
    def station_in_zone(self):
        if self.station is not None:
            valid = {f"S{i:02d}" for i in range(1, 25)}
            if self.station not in valid or zone_of(self.station) != self.zone:
                raise ValueError(f"station {self.station} is not in zone {self.zone}")
        return self


def ml_enabled() -> bool:
    return os.getenv("SHIFTLOOP_ML", "1") != "0"


class Runtime:
    """Holds the plant and everything that must be swapped together on reset."""

    def __init__(self, plant: Plant, copilot: ChatCopilot, detectors: dict, scenario: str):
        self.detectors = detectors
        self.scenario = scenario
        self.running = False
        self.speed = 2.0
        self.lock = asyncio.Lock()
        self.clients: set[WebSocket] = set()
        self.set_plant(plant, copilot)

    def set_plant(self, plant: Plant, copilot: ChatCopilot) -> None:
        self.plant = plant
        self.copilot = copilot
        self.vision = VisionService(plant, self.detectors)

    @property
    def mode(self) -> str:
        return "offline" if self.copilot.client is None else "claude"

    def sim_status(self) -> dict:
        return {"running": self.running, "speed": self.speed, "scenario": self.scenario,
                "vision": self.vision.status()}

    def snapshot(self) -> dict:
        return snapshot(self.plant, self.sim_status(), self.mode)

    async def broadcast(self) -> None:
        if not self.clients:
            return
        msg = json.dumps({"type": "snapshot", "data": self.snapshot()}, default=str)
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:
                self.clients.discard(ws)


def create_app(plant: Plant | None = None, copilot: ChatCopilot | None = None, detectors: dict | None = None,
               autostart: bool = True, scenario: str = "demo") -> FastAPI:
    plant = plant or Plant(scenario=scenario, ml=ml_enabled())
    rt = Runtime(plant, copilot or ChatCopilot(plant), detectors if detectors is not None else detectors_from_env(),
                 scenario)
    rt.running = autostart

    async def runner() -> None:
        while True:
            if rt.running:
                async with rt.lock:
                    rt.plant.step(1)
                await rt.broadcast()
                await asyncio.sleep(1 / max(rt.speed, 0.1))
            else:
                await asyncio.sleep(0.2)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(runner())
        yield
        task.cancel()

    app = FastAPI(title="ShiftLoop", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.state.runtime = rt

    async def changed(result):
        await rt.broadcast()
        return result

    # ------------------------------------------------------------------ read

    @app.get("/api/health")
    async def health():
        return {"ok": True, "mode": rt.mode, "vision": rt.vision.status(), "ml": rt.plant.ml.status}

    @app.get("/api/snapshot")
    async def get_snapshot():
        return rt.snapshot()

    @app.get("/api/workers")
    async def workers():
        st = rt.plant.state
        return {"workers": [w.model_dump(mode="json") for w in st.workers.values()],
                "stations": [{"id": s.id, "zone": s.zone, "name": s.name, "safety_critical": s.safety_critical}
                             for s in st.layout.stations.values()]}

    @app.get("/api/models")
    async def models():
        return {"models": rt.plant.ml.cards()}

    @app.get("/api/oversight")
    async def oversight():
        return oversight_report(rt.plant.state, rt.plant.central)

    # ------------------------------------------------------------------ simulation

    @app.post("/api/sim")
    async def sim(cmd: SimCommand):
        async with rt.lock:
            if cmd.action == "start":
                rt.running = True
            elif cmd.action == "pause":
                rt.running = False
            elif cmd.action == "step":
                rt.plant.step(max(1, min(cmd.minutes, 600)))
            elif cmd.action == "speed" and cmd.speed:
                rt.speed = max(0.1, min(cmd.speed, 120))
            elif cmd.action == "reset":
                rt.scenario = cmd.scenario or rt.scenario
                new = Plant(scenario=rt.scenario, ml=rt.plant.ml.available)
                rt.set_plant(new, ChatCopilot(new, client=rt.copilot.client, offline=rt.copilot.client is None))
                rt.running = False
        return await changed(rt.sim_status())

    # ------------------------------------------------------------------ supervisor actions

    @app.post("/api/incidents/{incident_id}/decision")
    async def decision(incident_id: str, body: DecisionIn):
        async with rt.lock:
            if incident_id not in rt.plant.state.incidents:
                raise HTTPException(404, "unknown incident")
            d = rt.plant.decide(incident_id, body.decision, body.reason, body.assignments)
        return await changed(d.model_dump(mode="json"))

    @app.post("/api/notifications/{notification_id}/ack")
    async def ack_notification(notification_id: str):
        n = next((n for n in rt.plant.state.notifications if n.id == notification_id), None)
        if n is None:
            raise HTTPException(404, "unknown notification")
        n.acknowledged = True
        return await changed(n.model_dump(mode="json"))

    @app.post("/api/escalations/{escalation_id}/ack")
    async def ack_escalation(escalation_id: str):
        async with rt.lock:
            if escalation_id not in rt.plant.state.escalations:
                raise HTTPException(404, "unknown escalation")
            esc = rt.plant.acknowledge(escalation_id)
        return await changed(esc.model_dump(mode="json"))

    @app.post("/api/whatif")
    async def whatif(body: WhatIfIn):
        st = rt.plant.state
        if body.worker not in st.workers or body.station not in st.layout.stations:
            raise HTTPException(404, "unknown worker or station")
        return what_if(st, body.worker, body.station)

    @app.post("/api/emergency/checkin")
    async def checkin(body: CheckinIn):
        em = rt.plant.state.emergency
        if em is None:
            raise HTTPException(409, "no emergency in progress")
        em.accounted.add(body.worker)
        return await changed({"accounted": len(em.accounted)})

    @app.post("/api/emergency/all-clear")
    async def all_clear():
        async with rt.lock:
            if rt.plant.state.emergency is None:
                raise HTTPException(409, "no emergency in progress")
            plan = rt.plant.all_clear()
        return await changed(plan)

    @app.post("/api/safety/report")
    async def safety_report(body: ReportIn):
        if not rt.plant.ml.available:
            raise HTTPException(503, "safety model not available")
        async with rt.lock:
            event = rt.plant.report_near_miss(body.text, body.zone, body.station)
            incident = next(i for i in rt.plant.state.incidents.values() if event.id in i.event_ids)
        return await changed({"event": event.model_dump(mode="json"),
                              "incident": incident.model_dump(mode="json", exclude={"event_ids", "event_keys"})})

    @app.post("/api/incidents/{incident_id}/explain")
    async def explain_incident(incident_id: str, body: LanguageIn | None = None):
        if incident_id not in rt.plant.state.incidents:
            raise HTTPException(404, "unknown incident")
        language = body.language if body else "en"
        async with rt.lock:
            out = await run_in_threadpool(rt.plant.explain_incident, incident_id, rt.copilot.client, language)
        return {"explanations": out}

    # ------------------------------------------------------------------ copilot

    @app.post("/api/chat")
    async def chat(body: ChatIn):
        # hold the lock so the simulation does not change state while Claude reads it
        async with rt.lock:
            out = await run_in_threadpool(rt.copilot.ask, body.message, body.history, body.language)
        return await changed(out)

    @app.post("/api/proposals/{proposal_id}/{action}")
    async def proposal(proposal_id: str, action: Literal["confirm", "reject"]):
        async with rt.lock:
            p = rt.plant.state.proposals.get(proposal_id)
            if p is None:
                raise HTTPException(404, "unknown proposal")
            if p.status != "pending":
                raise HTTPException(409, f"proposal already {p.status}")
            out = rt.plant.confirm_proposal(proposal_id) if action == "confirm" else rt.plant.reject_proposal(proposal_id)
        return await changed(out)

    @app.post("/api/handover")
    async def handover(body: LanguageIn):
        async with rt.lock:
            return await run_in_threadpool(write_handover, rt.plant, rt.copilot.client, body.language)

    # ------------------------------------------------------------------ vision

    @app.post("/api/vision/{camera_id}")
    async def vision(camera_id: str, image: UploadFile = File(...)):
        data = await image.read()
        async with rt.lock:
            try:
                readings = rt.vision.process(camera_id, data, image_ref=image.filename)
            except KeyError:
                raise HTTPException(404, "unknown camera")
            except LookupError as e:
                raise HTTPException(503, str(e))
        return await changed({"detections": [r.model_dump(mode="json") for r in readings]})

    # ------------------------------------------------------------------ live updates

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        rt.clients.add(websocket)
        try:
            await websocket.send_text(json.dumps({"type": "snapshot", "data": rt.snapshot()}, default=str))
            while True:
                await websocket.receive_text()  # keep-alive; client messages are ignored
        except WebSocketDisconnect:
            rt.clients.discard(websocket)

    return app



def main() -> None:
    import uvicorn

    uvicorn.run("shiftloop.api.app:make_default", factory=True, host="0.0.0.0", port=8000)


def make_default() -> FastAPI:
    return create_app()
