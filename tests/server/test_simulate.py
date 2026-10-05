# SIMULATED mode: hosted-API answers, always labeled. The provider is faked with httpx.MockTransport.
import json
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from src.server.generate import GenerationError
from src.server.main import create_app
from src.server.settings import Settings
from src.server.simulate import ApiSimulator
from tests.server.conftest import collect


def sse(*pieces):
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}" for p in pieces]
    return "\n\n".join([*lines, "data: [DONE]"]) + "\n\n"


class Provider:
    """Records requests and replies like an OpenAI-compatible API."""

    def __init__(self, status=200):
        self.status, self.requests = status, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append((request.headers.get("authorization"), body))
        if self.status != 200:
            return httpx.Response(self.status, text="rate limited")
        if body["stream"]:
            return httpx.Response(200, text=sse("Soft ", "rain"))
        return httpx.Response(200, json={"choices": [{"message": {"content": "full answer"}}]})


def settings(**kw):
    base = {"_env_file": None, "sim_provider": "groq", "sim_api_key": "test-key", "sim_writing_model": "w-model", "sim_code_model": "c-model"}
    return Settings(**{**base, **kw})


@pytest.fixture
def served():
    provider = Provider()
    cfg = settings()
    app = create_app(cfg)
    with TestClient(app) as client:
        client.app.state.stream = ApiSimulator(cfg, client.app.state.registry, httpx.MockTransport(provider)).stream
        yield client, provider


def test_health_says_simulated(served):
    client, _ = served
    assert client.get("/health").json()["simulated"] == {"provider": "groq", "writing_model": "w-model", "code_model": "c-model"}


def test_streams_provider_text_through_the_websocket(served):
    client, provider = served
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "generate", "request_id": "r1", "blend_id": "sweep_100", "prompt": "hi"})
        msgs = collect(ws, "r1")
    assert "".join(m["text"] for m in msgs if m["type"] == "token") == "Soft rain"
    assert msgs[-1]["type"] == "done"
    auth, body = provider.requests[0]
    assert auth == "Bearer test-key" and body["model"] == "c-model" and body["stream"] is True
    assert "coding assistant" in body["messages"][0]["content"]


def test_blend_position_picks_model_and_style():
    sim = ApiSimulator(settings(), {"blends": [{"id": "a", "t": 0}, {"id": "b", "t": 0.25}, {"id": "c", "t": 0.5}, {"id": "d", "t": 0.75}]})
    assert sim.route("a")[0] == "w-model" and "creative writing" in sim.route("a")[1]
    assert sim.route("b")[0] == "w-model" and "75% expressive writing and 25%" in sim.route("b")[1]
    assert sim.route("c")[0] == "w-model"
    assert sim.route("d")[0] == "c-model"


def test_rate_limit_becomes_busy():
    cfg = settings()
    sim = ApiSimulator(cfg, {"blends": [{"id": "x", "t": 0.5}]}, httpx.MockTransport(Provider(429)))

    async def go():
        async for _ in sim.stream("x", "hi", 10, 0.5, threading.Event()):
            pass

    import asyncio
    with pytest.raises(GenerationError) as info:
        asyncio.run(go())
    assert info.value.code == "busy"


def test_finder_session_returns_full_text():
    import asyncio

    sim = ApiSimulator(settings(), {"blends": [{"id": "x", "t": 0.5}]}, httpx.MockTransport(Provider()))

    async def go():
        async with sim.session("x", threading.Event()) as generate:
            return await asyncio.to_thread(generate, "q")

    assert asyncio.run(go()) == "full answer"


def test_refuses_to_start_without_a_key():
    with pytest.raises(ValueError, match="SIM_API_KEY"):
        ApiSimulator(settings(sim_api_key=""), {"blends": []})
