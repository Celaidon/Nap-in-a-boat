# Check C3: real token streaming never blocks the event loop.
# Most tests use FakeLlm, which blocks like llama-cpp-python does but needs no model file.
# Tests marked `models` use a real GGUF (DEV_MODEL_OVERRIDE) and are skipped in CI.
import asyncio
import os
import pathlib
import threading
import time

import pytest

from src.server.generate import DevModelStreamer, GenerationError, stream_tokens
from src.server.main import create_app
from src.server.settings import Settings
from tests.server.conftest import collect

TOKEN_DELAY_S = 0.05


def chunk(text=None, role=None) -> dict:
    delta = {}
    if role:
        delta["role"] = role
    if text is not None:
        delta["content"] = text
    return {"choices": [{"delta": delta}]}


class FakeLlm:
    """Mimics Llama.create_chat_completion(stream=True): a blocking generator."""

    def __init__(self, n_tokens=20, fail_after=None):
        self.n_tokens = n_tokens
        self.fail_after = fail_after
        self.threads_seen = set()

    def create_chat_completion(self, messages, max_tokens, temperature, stream):
        assert stream is True
        self.threads_seen.add(threading.current_thread().name)
        yield chunk(role="assistant")  # llama-cpp's first chunk has no text
        for i in range(min(self.n_tokens, max_tokens)):
            if self.fail_after is not None and i >= self.fail_after:
                raise RuntimeError("model exploded")
            time.sleep(TOKEN_DELAY_S)  # blocking, like real inference
            yield chunk(text=f"w{i} ")


def fake_streamer(llm: FakeLlm) -> DevModelStreamer:
    return DevModelStreamer("fake.gguf", loader=lambda path: llm)


def gen_msg(request_id="r1", **extra) -> dict:
    return {"type": "generate", "request_id": request_id, "blend_id": "sweep_050", "prompt": "hi", **extra}


# ---- stream_tokens ----------------------------------------------------------


def test_stream_tokens_yields_text_and_skips_role_chunk():
    async def run():
        pieces = []
        async for text in stream_tokens(FakeLlm(3), [], 10, 0.7, threading.Event()):
            pieces.append(text)
        return pieces

    assert asyncio.run(run()) == ["w0 ", "w1 ", "w2 "]


def test_worker_error_becomes_internal_error():
    async def run():
        async for _ in stream_tokens(FakeLlm(10, fail_after=2), [], 10, 0.7, threading.Event()):
            pass

    with pytest.raises(GenerationError) as info:
        asyncio.run(run())
    assert info.value.code == "internal"
    assert "model exploded" in info.value.message


def test_inference_runs_off_the_event_loop_thread():
    llm = FakeLlm(2)

    async def run():
        async for _ in stream_tokens(llm, [], 10, 0.7, threading.Event()):
            pass

    asyncio.run(run())
    assert llm.threads_seen == {"llm-worker"}


# ---- through the websocket --------------------------------------------------


def test_health_stays_fast_while_generating(make_client):
    client = make_client()
    client.app.state.stream = fake_streamer(FakeLlm(60))  # about 3 s of blocking inference
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen_msg())
        assert ws.receive_json()["type"] == "token"  # generation is underway

        latencies = []
        for _ in range(8):
            start = time.perf_counter()
            assert client.get("/health").status_code == 200
            latencies.append(time.perf_counter() - start)
            time.sleep(0.05)

        assert max(latencies) < 0.2, f"/health took {max(latencies) * 1000:.0f} ms while generating"
        rest = collect(ws, "r1")
        assert rest[-1]["type"] == "done"  # it was still streaming the whole time


def test_done_reports_sensible_speed(make_client):
    client = make_client()
    client.app.state.stream = fake_streamer(FakeLlm(20))
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen_msg())
        done = collect(ws, "r1")[-1]
    assert done["type"] == "done" and done["tokens"] == 20
    assert 5 < done["tokens_per_sec"] < 25  # the fake emits about 20 tokens/s


def test_model_load_failure_is_internal_error(make_client):
    def bad_loader(path):
        raise OSError("no such file")

    client = make_client()
    client.app.state.stream = DevModelStreamer("missing.gguf", loader=bad_loader)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen_msg())
        last = collect(ws, "r1")[-1]
    assert last["type"] == "error" and last["code"] == "internal"
    assert "Could not load model" in last["message"]


def test_settings_pick_dev_streamer_when_override_set():
    app = create_app(Settings(_env_file=None, dev_model_override="some.gguf"))
    assert isinstance(app.state.stream, DevModelStreamer)


# ---- real model (not run in CI) ---------------------------------------------

REAL_MODEL = os.environ.get("DEV_MODEL_OVERRIDE") or "local_models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
needs_model = pytest.mark.skipif(not pathlib.Path(REAL_MODEL).exists(), reason=f"{REAL_MODEL} not found")


@pytest.mark.models
@needs_model
def test_real_model_streams_tokens(make_client):
    client = make_client(dev_model_override=REAL_MODEL)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen_msg(prompt="Say hello in five words.", max_tokens=40, temperature=0))
        messages = collect(ws, "r1")
    done = messages[-1]
    assert done["type"] == "done"
    assert done["tokens"] >= 3
    assert done["tokens_per_sec"] > 0
    assert "".join(m["text"] for m in messages if m["type"] == "token").strip()


@pytest.mark.models
@needs_model
def test_real_model_health_stays_fast(make_client):
    client = make_client(dev_model_override=REAL_MODEL)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen_msg(prompt="Write a long story about a boat.", max_tokens=200))
        assert ws.receive_json()["type"] == "token"
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            assert client.get("/health").status_code == 200
            latencies.append(time.perf_counter() - start)
            time.sleep(0.1)
        ws.send_json({"type": "cancel", "request_id": "r1"})
        collect(ws, "r1")
    assert max(latencies) < 0.2, f"/health took {max(latencies) * 1000:.0f} ms during real generation"
