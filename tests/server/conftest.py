# Shared helpers for the server tests.
import json
import os
import socket
import threading
import time

import jsonschema
import pytest
import uvicorn
from fastapi.testclient import TestClient

from src.server.main import create_app
from src.server.settings import ROOT, Settings

WS_SCHEMA = json.loads((ROOT / "contracts" / "schemas" / "ws_messages.schema.json").read_text())


def check_message(message: dict) -> dict:
    """Assert a protocol message matches ws_messages.schema.json, then return it."""
    jsonschema.validate(message, WS_SCHEMA)
    return message


@pytest.fixture
def make_client():
    """Build a TestClient with settings overrides. Cleans up after the test."""
    clients = []

    def build(**overrides) -> TestClient:
        overrides.setdefault("dev_model_override", "")
        overrides.setdefault("fake_generator", True)  # tests opt in to real model code explicitly
        client = TestClient(create_app(Settings(_env_file=None, **overrides)))
        client.__enter__()
        clients.append(client)
        return client

    yield build
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


def collect(ws, request_id: str, stop_types=("done", "error")) -> list[dict]:
    """Read messages for one request until it ends (done or error); ignores other requests' and pings."""
    messages = []
    while True:
        msg = check_message(ws.receive_json())
        if msg.get("request_id") != request_id:
            continue
        messages.append(msg)
        if msg["type"] in stop_types:
            return messages


@pytest.fixture
def live_server():
    """Run the real app on a free local port, the way uvicorn runs it in the container."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = create_app(Settings(_env_file=None, fake_generator=True))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "test server did not start"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _clean_server_env(monkeypatch):
    """Other tests (the judge) load the repo's .env into os.environ. Server tests must not see it."""
    for name in list(os.environ):
        if name.startswith(("SIM_", "CORS_")) or name in {"DEV_MODEL_OVERRIDE", "FAKE_GENERATOR"}:
            monkeypatch.delenv(name)
