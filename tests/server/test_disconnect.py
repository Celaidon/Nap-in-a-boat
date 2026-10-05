# Check C5: a client that disconnects or cancels never leaves a thread running or a model locked.
import os
import pathlib
import threading
import time

import pytest

from tests.server.conftest import collect
from tests.server.test_models import Harness

LONG = 400  # tokens: about 8 s of fake inference, so only a stop signal can end it quickly
STOP_WITHIN_S = 1.0


def gen(request_id="r1", blend_id="sweep_050", **extra) -> dict:
    return {"type": "generate", "request_id": request_id, "blend_id": blend_id, "prompt": "hi", **extra}


def worker_threads() -> int:
    return sum(1 for t in threading.enumerate() if t.name == "llm-worker")


def wait_until(condition, timeout=STOP_WITHIN_S) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


@pytest.fixture
def served(make_client, tmp_path):
    """A running test app whose tokens come from a slow fake model through the real ModelManager."""
    client = make_client()
    harness = Harness(tmp_path, llm_tokens=LONG)
    client.app.state.manager = harness.manager
    client.app.state.stream = harness.manager.stream
    return client, harness


def test_disconnect_mid_stream_stops_worker_and_frees_the_model(served):
    client, harness = served
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen())
        assert ws.receive_json()["type"] == "token"  # generation is running
        assert worker_threads() == 1
    # The socket is closed now.
    assert wait_until(lambda: worker_threads() == 0), "worker thread kept running after disconnect"
    assert harness.loaded_llms["sweep_050"].active == 0

    # The lock was released: a new request on the same model completes (and is not stuck behind r1).
    started = time.monotonic()
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen("r2", max_tokens=5))
        assert collect(ws, "r2")[-1]["type"] == "done"
    assert time.monotonic() - started < 3
    assert harness.loaded_llms["sweep_050"].max_active == 1  # never overlapped with the stopped one


def test_cancel_stops_worker_and_frees_the_model(served):
    client, harness = served
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen())
        assert ws.receive_json()["type"] == "token"
        cancel_sent = time.monotonic()
        ws.send_json({"type": "cancel", "request_id": "r1"})
        assert collect(ws, "r1")[-1]["code"] == "cancelled"
        assert time.monotonic() - cancel_sent < STOP_WITHIN_S
        assert harness.loaded_llms["sweep_050"].active == 0  # the reply only comes once inference has ended
        assert wait_until(lambda: worker_threads() == 0)

        ws.send_json(gen("r2", max_tokens=3))
        assert collect(ws, "r2")[-1]["type"] == "done"
    assert harness.loaded_llms["sweep_050"].max_active == 1


def test_twenty_connect_disconnect_cycles_do_not_grow_threads(served):
    client, harness = served

    def cycle() -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(gen(max_tokens=LONG))
            assert ws.receive_json()["type"] == "token"
        assert wait_until(lambda: worker_threads() == 0), "a worker thread was left behind"

    cycle()  # warm-up: creates the server's pooled helper threads once, so they are not counted as growth
    baseline = threading.active_count()
    counts = []
    for _ in range(20):
        cycle()
        counts.append(threading.active_count())
    assert max(counts) <= baseline + 1, f"thread count grew from {baseline}: {counts}"  # +1 = the one live cycle
    assert wait_until(lambda: threading.active_count() <= baseline), (
        f"threads grew from {baseline} to {threading.active_count()}"
    )
    assert harness.loaded_llms["sweep_050"].max_active == 1


def test_disconnect_while_queued_behind_a_busy_model(served):
    client, harness = served
    with client.websocket_connect("/ws") as first:
        first.send_json(gen("a"))
        assert first.receive_json()["type"] == "token"  # "a" holds the model

        with client.websocket_connect("/ws") as second:
            second.send_json(gen("b"))  # queued behind "a"
            time.sleep(0.2)
        # "b" disconnected while waiting: its queue slot must be gone and it must not run.

        first.send_json({"type": "cancel", "request_id": "a"})
        assert collect(first, "a")[-1]["code"] == "cancelled"
        assert wait_until(lambda: worker_threads() == 0)

        first.send_json(gen("c", max_tokens=3))
        assert collect(first, "c")[-1]["type"] == "done"
    assert harness.loaded_llms["sweep_050"].max_active == 1


def test_cancel_a_request_that_is_still_queued(served):
    client, _ = served
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen("a"))
        assert ws.receive_json()["type"] == "token"
        ws.send_json(gen("b"))  # waits for the model
        time.sleep(0.1)
        ws.send_json({"type": "cancel", "request_id": "b"})
        assert collect(ws, "b")[-1]["code"] == "cancelled"
        ws.send_json({"type": "cancel", "request_id": "a"})
        assert collect(ws, "a")[-1]["code"] == "cancelled"
        assert wait_until(lambda: worker_threads() == 0)


# ---- real model (not run in CI) ---------------------------------------------

REAL_MODEL = os.environ.get("DEV_MODEL_OVERRIDE") or "local_models/qwen2.5-0.5b-instruct-q4_k_m.gguf"


@pytest.mark.models
@pytest.mark.skipif(not pathlib.Path(REAL_MODEL).exists(), reason=f"{REAL_MODEL} not found")
def test_real_model_disconnect_stops_within_a_second(make_client):
    client = make_client(dev_model_override=REAL_MODEL, fake_generator=False)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(gen(prompt="Write a very long story about the sea.", max_tokens=1000))
        assert ws.receive_json()["type"] == "token"
        gone = time.monotonic()
    assert wait_until(lambda: worker_threads() == 0)
    assert time.monotonic() - gone < STOP_WITHIN_S

    with client.websocket_connect("/ws") as ws:  # the model is usable again
        ws.send_json(gen("r2", prompt="Say hi.", max_tokens=10))
        assert collect(ws, "r2")[-1]["type"] == "done"
