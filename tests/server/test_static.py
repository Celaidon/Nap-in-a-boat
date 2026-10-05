# The built frontend is served at "/" without shadowing the API or the WebSocket.
from fastapi.testclient import TestClient

from src.server.main import create_app
from src.server.settings import Settings
from tests.server.conftest import collect


def app_with_web(tmp_path, with_index=True):
    if with_index:
        (tmp_path / "index.html").write_text("<!doctype html><title>BlendLab</title><div id=root></div>")
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "app.js").write_text("console.log('hi')")
    settings = Settings(_env_file=None, fake_generator=True, web_dir=str(tmp_path))
    return TestClient(create_app(settings))


def test_root_serves_the_frontend_and_its_assets(tmp_path):
    with app_with_web(tmp_path) as client:
        page = client.get("/")
        assert page.status_code == 200 and "BlendLab" in page.text
        assert client.get("/assets/app.js").status_code == 200


def test_api_and_health_still_win_over_the_static_mount(tmp_path):
    with app_with_web(tmp_path) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert len(client.get("/api/registry").json()["blends"]) == 8
        assert "blends" in client.get("/api/metrics").json()


def test_websocket_still_works_with_the_frontend_mounted(tmp_path):
    with app_with_web(tmp_path) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "generate", "request_id": "r1", "blend_id": "sweep_050", "prompt": "hi", "max_tokens": 2})
        assert collect(ws, "r1")[-1]["type"] == "done"


def test_server_runs_without_a_built_frontend(tmp_path):
    with app_with_web(tmp_path, with_index=False) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 404  # nothing to serve, but the API is fine
