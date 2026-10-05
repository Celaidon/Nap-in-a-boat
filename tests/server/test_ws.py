# Check C2: the WebSocket protocol, driven by the fake generator.
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from src.server import generate
from tests.server.conftest import check_message, collect


def generate_msg(request_id="r1", **extra) -> dict:
    return {"type": "generate", "request_id": request_id, "blend_id": "sweep_050", "prompt": "hi", **extra}


def test_generate_streams_tokens_then_done(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(generate_msg())
        messages = collect(ws, "r1")

    tokens = [m for m in messages if m["type"] == "token"]
    done = messages[-1]
    assert done["type"] == "done"
    assert len(tokens) > 3
    assert "".join(t["text"] for t in tokens).split() == generate.FAKE_SENTENCE.split()  # in order
    assert done["tokens"] == len(tokens)
    assert done["blend_id"] == "sweep_050"


def test_max_tokens_limits_stream(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(generate_msg(max_tokens=3))
        messages = collect(ws, "r1")
    assert messages[-1]["type"] == "done"
    assert messages[-1]["tokens"] == 3


def test_unknown_blend(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({**generate_msg(), "blend_id": "sweep_999"})
        (msg,) = collect(ws, "r1")
    assert msg["type"] == "error"
    assert msg["code"] == "unknown_blend"


def test_malformed_json_is_bad_request(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_text("{this is not json")
        msg = check_message(ws.receive_json())
        assert msg["type"] == "error" and msg["code"] == "bad_request"
        # The connection survives and still works.
        ws.send_json(generate_msg(max_tokens=1))
        assert collect(ws, "r1")[-1]["type"] == "done"


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "teleport", "request_id": "r1"},  # unknown type
        {"type": "generate", "request_id": "r1", "prompt": "x"},  # missing blend_id
        {"type": "generate", "blend_id": "sweep_050", "prompt": "x"},  # missing request_id
        {"type": "generate", "request_id": "r1", "blend_id": "sweep_050", "prompt": 5},  # wrong type
        {"type": "generate", "request_id": "r1", "blend_id": "sweep_050", "prompt": "x", "max_tokens": 0},
        {"type": "generate", "request_id": "r1", "blend_id": "sweep_050", "prompt": "x", "temperature": -1},
        {"type": "find_best", "request_id": "r1"},  # missing tasks
        [1, 2, 3],  # not an object
    ],
)
def test_bad_messages(client, bad):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(bad)
        msg = check_message(ws.receive_json())
    assert msg["type"] == "error"
    assert msg["code"] == "bad_request"


def test_cancel_mid_stream(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(generate_msg())
        assert check_message(ws.receive_json())["type"] == "token"  # stream is running
        ws.send_json({"type": "cancel", "request_id": "r1"})
        messages = collect(ws, "r1")
        assert messages[-1]["type"] == "error"
        assert messages[-1]["code"] == "cancelled"

        # Nothing more arrives for r1 after the cancelled error: a new request is clean.
        ws.send_json(generate_msg("r2", max_tokens=2))
        r2 = collect(ws, "r2")
        assert [m["type"] for m in r2] == ["token", "token", "done"]


def test_cancel_of_unknown_request_is_ignored(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "cancel", "request_id": "nope"})
        ws.send_json(generate_msg(max_tokens=1))
        assert collect(ws, "r1")[-1]["type"] == "done"


def test_two_requests_on_one_connection(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(generate_msg("a", max_tokens=4))
        ws.send_json(generate_msg("b", max_tokens=6))
        seen = {"a": 0, "b": 0}
        done = set()
        while len(done) < 2:
            msg = check_message(ws.receive_json())
            if msg["type"] == "token":
                seen[msg["request_id"]] += 1
            elif msg["type"] == "done":
                done.add(msg["request_id"])
    assert seen == {"a": 4, "b": 6}


def test_server_sends_ping(make_client):
    client = make_client(ping_interval_s=0.05)
    with client.websocket_connect("/ws") as ws:
        msg = check_message(ws.receive_json())
        assert msg == {"type": "ping"}
        ws.send_json({"type": "pong"})


def test_silent_client_is_disconnected(make_client):
    client = make_client(ping_interval_s=0.05, pong_timeout_s=0.2)
    started = time.monotonic()
    with client.websocket_connect("/ws") as ws, pytest.raises(WebSocketDisconnect):
        while True:
            ws.receive_json()  # never answers pong, so the server hangs up
    assert time.monotonic() - started < 5


def test_client_that_answers_pong_stays_connected(make_client):
    client = make_client(ping_interval_s=0.05, pong_timeout_s=0.2)
    with client.websocket_connect("/ws") as ws:
        deadline = time.monotonic() + 0.8  # well past the pong timeout
        while time.monotonic() < deadline:
            if ws.receive_json() == {"type": "ping"}:
                ws.send_json({"type": "pong"})
        ws.send_json(generate_msg(max_tokens=1))
        assert collect(ws, "r1")[-1]["type"] == "done"
