import pytest
from fastapi.testclient import TestClient

from shiftloop.api.app import create_app
from shiftloop.llm.chat import ChatCopilot
from shiftloop.plant import Plant


@pytest.fixture
def client():
    plant = Plant(scenario="quiet", ml=True)
    app = create_app(plant=plant, copilot=ChatCopilot(plant, offline=True), detectors={}, autostart=False)
    with TestClient(app) as c:
        yield c


def test_health_reports_ml_status(client):
    assert client.get("/api/health").json()["ml"] == {"staffing": "loaded", "assembly": "loaded", "safety": "loaded"}


def test_near_miss_report_creates_a_rated_incident(client):
    r = client.post("/api/safety/report", json={"text": "Forklift reversed without a spotter and nearly hit "
                                                         "a worker at the battery area.", "zone": "C",
                                                 "station": "S18"})
    assert r.status_code == 200
    body = r.json()
    assert body["event"]["type"] in {"near_miss_rated", "near_miss_unsure"}
    inc = body["incident"]
    assert inc["stations"] == ["S18"] and inc["predictions"][0]["model"] == "safety_model"
    assert inc["predictions"][0]["explanation"]


def test_near_miss_report_validates_input(client):
    assert client.post("/api/safety/report", json={"text": "", "zone": "C"}).status_code == 422
    assert client.post("/api/safety/report", json={"text": "x happened", "zone": "Q"}).status_code == 422
    assert client.post("/api/safety/report", json={"text": "x happened", "zone": "C", "station": "S01"}).status_code == 422


def test_explain_endpoint_returns_offline_explanations(client):
    inc = client.post("/api/safety/report", json={"text": "Oil on the floor near the press, someone slipped.",
                                                  "zone": "A", "station": "S02"}).json()["incident"]
    r = client.post(f"/api/incidents/{inc['id']}/explain", json={"language": "en"})
    assert r.status_code == 200
    ex = r.json()["explanations"][0]
    assert ex["model"] == "safety_model" and ex["mode"] == "offline" and ex["text"]
    assert client.post("/api/incidents/inc_9999/explain", json={}).status_code == 404


def test_models_endpoint_lists_cards(client):
    cards = client.get("/api/models").json()["models"]
    assert {c["model"] for c in cards} == {"staffing_model", "assembly_model", "safety_model"}
    assert all("random forest" in c["algorithm"] for c in cards)


def test_report_without_ml_is_503():
    plant = Plant(scenario="quiet")
    app = create_app(plant=plant, copilot=ChatCopilot(plant, offline=True), detectors={}, autostart=False)
    with TestClient(app) as c:
        r = c.post("/api/safety/report", json={"text": "something happened", "zone": "A"})
        assert r.status_code == 503
        assert c.get("/api/health").json()["ml"] == {"staffing": "unavailable", "assembly": "unavailable",
                                                     "safety": "unavailable"}
