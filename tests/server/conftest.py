# Shared helpers for the server tests.
import json

import jsonschema
import pytest
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
