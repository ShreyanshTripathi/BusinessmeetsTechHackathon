import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from shiftloop.api.app import create_app
from shiftloop.llm.chat import ChatCopilot
from shiftloop.plant import Plant
from shiftloop.vision.service import Detection


class FakeDetector:
    def __init__(self, label, conf):
        self.label, self.conf = label, conf

    def detect(self, image):
        return [Detection(self.label, self.conf, "test")]


@pytest.fixture
def client():
    plant = Plant(scenario="demo")
    app = create_app(plant=plant, copilot=ChatCopilot(plant, offline=True),
                     detectors={"quality": FakeDetector("defect", 0.9)}, autostart=False)
    with TestClient(app) as c:
        c.post("/api/sim", json={"action": "step", "minutes": 2})
        yield c


def snap(client):
    r = client.get("/api/snapshot")
    assert r.status_code == 200
    return r.json()


def test_snapshot_contract(client):
    s = snap(client)
    assert set(s) >= {"clock", "sim", "zones", "stations", "incidents", "notifications", "escalations", "emergency",
                      "kpis", "attention", "mode", "expert_queue"}
    assert len(s["stations"]) == 24
    st = s["stations"][0]
    assert set(st) >= {"id", "zone", "name", "status", "operator", "safety_critical", "alert"}
    z = s["zones"][0]
    assert set(z) >= {"id", "people", "fire_wardens", "first_aiders", "exits", "sensors"}
    assert s["incidents"]["active"], "demo starts with incidents"
    inc = s["incidents"]["active"][0]
    assert set(inc) >= {"id", "title", "severity", "category", "agents", "evidence", "recommendation", "likely_cause"}
    assert s["mode"] == "offline"


def test_decision_endpoint_applies_and_logs(client):
    inc = snap(client)["incidents"]["active"][0]
    r = client.post(f"/api/incidents/{inc['id']}/decision", json={"decision": "accept"})
    assert r.status_code == 200 and r.json()["decision"] == "accept"
    assert inc["id"] not in [i["id"] for i in snap(client)["incidents"]["active"]]
    assert client.get("/api/oversight").json()["decisions"]["total"] == 1


def test_decision_on_unknown_incident_is_404(client):
    assert client.post("/api/incidents/inc_9999/decision", json={"decision": "accept"}).status_code == 404


def test_invalid_decision_is_422(client):
    inc = snap(client)["incidents"]["active"][0]
    assert client.post(f"/api/incidents/{inc['id']}/decision", json={"decision": "maybe"}).status_code == 422


def test_notifications_can_be_acknowledged(client):
    n = snap(client)["notifications"][0]
    assert client.post(f"/api/notifications/{n['id']}/ack").status_code == 200
    assert next(x for x in snap(client)["notifications"] if x["id"] == n["id"])["acknowledged"]


def test_escalation_ack_flow(client):
    for i in snap(client)["incidents"]["active"]:
        client.post(f"/api/incidents/{i['id']}/decision", json={"decision": "accept"})
    client.post("/api/sim", json={"action": "step", "minutes": 190})  # ~09:12, tool wear at S12 predicted
    tool = next(i for i in snap(client)["incidents"]["active"] if "S12" in i["stations"])
    assert "maintenance" in tool["recommendation"]["escalations"]
    client.post(f"/api/incidents/{tool['id']}/decision", json={"decision": "accept"})
    esc = next(e for e in snap(client)["escalations"] if e["team"] == "maintenance")
    assert esc["acknowledged_at"] is None
    assert client.post(f"/api/escalations/{esc['id']}/ack").status_code == 200
    assert next(x for x in snap(client)["escalations"] if x["id"] == esc["id"])["acknowledged_at"]


def test_chat_and_proposal_confirmation(client):
    floater = next(w for w in client.get("/api/workers").json()["workers"]
                   if w["role"] == "floater" and w["station"] is None and w["status"] == "present")
    r = client.post("/api/chat", json={"message": f"assign {floater['name']} to S03", "language": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "offline" and body["proposals"]
    pid = body["proposals"][0]["id"]
    assert client.post(f"/api/proposals/{pid}/confirm").status_code == 200
    assert next(s for s in snap(client)["stations"] if s["id"] == "S03")["operator"]["id"] == floater["id"]
    assert client.post(f"/api/proposals/{pid}/confirm").status_code == 409


def test_workers_endpoint_lists_qualifications(client):
    ws = client.get("/api/workers").json()
    assert len(ws["workers"]) == 35 and "qualifications" in ws["workers"][0]
    assert len(ws["stations"]) == 24


def test_whatif_endpoint(client):
    w = client.get("/api/workers").json()["workers"][0]
    r = client.post("/api/whatif", json={"worker": w["id"], "station": "S20"})
    assert r.status_code == 200 and "warnings" in r.json()


def test_handover_endpoint(client):
    r = client.post("/api/handover", json={"language": "en"})
    assert r.status_code == 200 and "Shift handover" in r.json()["text"]


def test_sim_controls(client):
    assert client.post("/api/sim", json={"action": "speed", "speed": 30}).json()["speed"] == 30
    before = snap(client)["clock"]
    client.post("/api/sim", json={"action": "step", "minutes": 10})
    assert snap(client)["clock"] > before
    r = client.post("/api/sim", json={"action": "reset", "scenario": "quiet"})
    assert r.json()["scenario"] == "quiet" and snap(client)["clock"].endswith("06:00:00")


def test_emergency_flow(client):
    client.post("/api/sim", json={"action": "step", "minutes": 60 * 4 + 20})  # to ~10:22
    s = snap(client)
    assert s["emergency"] and s["emergency"]["zone"] == "C"
    person = s["emergency"]["people"][0]
    assert client.post("/api/emergency/checkin", json={"worker": person["id"]}).status_code == 200
    assert next(p for p in snap(client)["emergency"]["people"] if p["id"] == person["id"])["accounted"]
    client.post("/api/sim", json={"action": "step", "minutes": 6})
    r = client.post("/api/emergency/all-clear")
    assert r.status_code == 200 and r.json()["zone"] == "C"
    assert snap(client)["emergency"] is None
    assert client.post("/api/emergency/all-clear").status_code == 409


def test_vision_upload(client):
    buf = io.BytesIO()
    Image.new("RGB", (32, 32)).save(buf, format="PNG")
    r = client.post("/api/vision/CAM-QC-S05", files={"image": ("f.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["detections"][0]["label"] == "defect"
    r = client.post("/api/vision/CAM-FIRE-A", files={"image": ("f.png", buf.getvalue(), "image/png")})
    assert r.status_code == 503  # no fire model loaded in this test
    assert client.post("/api/vision/CAM-NOPE", files={"image": ("f.png", b"x", "image/png")}).status_code == 404


def test_websocket_sends_snapshot(client):
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot" and "stations" in msg["data"]
