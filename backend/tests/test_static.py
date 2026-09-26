"""In the Docker image the backend also serves the built dashboard, so Render needs one service."""
from fastapi.testclient import TestClient

from shiftloop.api.app import create_app
from shiftloop.llm.chat import ChatCopilot
from shiftloop.plant import Plant


def make(static_dir):
    plant = Plant(scenario="quiet")
    return create_app(plant=plant, copilot=ChatCopilot(plant, offline=True), detectors={}, autostart=False,
                      static_dir=static_dir)


def test_serves_dashboard_assets_and_spa_fallback(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<title>ShiftLoop</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    with TestClient(make(tmp_path)) as c:
        assert "ShiftLoop" in c.get("/").text
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert "ShiftLoop" in c.get("/safety").text  # client-side route falls back to index.html
        assert c.get("/api/health").json()["ok"] is True  # API still wins
        assert c.get("/api/nope").status_code == 404  # unknown API paths are not swallowed by the fallback


def test_without_a_build_only_the_api_is_served(tmp_path):
    with TestClient(make(tmp_path / "missing")) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/").status_code == 404
