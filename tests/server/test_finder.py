# Check C6: the Best Blend Finder.
import json
import time

import pytest
from fastapi.testclient import TestClient

from src.server.finder import MAX_TASKS, pick_best
from src.server.main import ConfigError, create_app
from src.server.settings import ROOT, Settings
from tests.server.conftest import check_message, collect
from tests.server.test_models import Harness, make_registry

TASKS = [
    {"kind": "code", "prompt": "Write a function is_prime(n)", "entry_point": "is_prime", "tests": "assert is_prime(7)"},
    {"kind": "style", "prompt": "Write a short poem about the sea"},
]
REGISTRY = json.loads((ROOT / "contracts" / "mocks" / "registry.json").read_text())
ALL_IDS = [b["id"] for b in REGISTRY["blends"]]


def find_msg(request_id="f1", tasks=TASKS) -> dict:
    return {"type": "find_best", "request_id": request_id, "tasks": tasks}


def run_finder(ws, request_id="f1") -> tuple[list[dict], dict]:
    """Collect progress messages and the final message (result or error) of one find_best."""
    messages = collect(ws, request_id, stop_types=("result", "error"))
    return messages[:-1], messages[-1]


# ---- the happy path ---------------------------------------------------------


def test_progress_in_order_then_a_valid_result_with_the_mock_scorer(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg())
        progress, result = run_finder(ws)

    assert [p["step"] for p in progress] == list(range(1, 9))
    assert all(p["type"] == "progress" and p["of"] == 8 for p in progress)
    assert [p["blend_id"] for p in progress] == ALL_IDS  # registry order
    assert result["type"] == "result"
    assert set(result["scores"]) == set(ALL_IDS)
    assert set(result["scores"].values()) == {0.5}  # the mock gives everything 0.5
    assert result["best_blend_id"] == "sweep_050"  # all tied: closest to t=0.5, first in registry order


def test_a_scorer_that_prefers_one_blend_gets_that_blend_recommended(make_client):
    client = make_client(scoring_module="tests.server.fake_scoring")
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg())
        _, result = run_finder(ws)
    assert result["best_blend_id"] == "sweep_075"
    assert result["scores"]["sweep_075"] == 0.9
    assert result["scores"]["sweep_050"] == 0.3


def test_finder_can_run_twice_in_a_row(client):
    with client.websocket_connect("/ws") as ws:
        for request_id in ("f1", "f2"):
            ws.send_json(find_msg(request_id))
            assert run_finder(ws, request_id)[1]["type"] == "result"


# ---- tie-break --------------------------------------------------------------


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ({"sweep_000": 0.7, "sweep_075": 0.7}, "sweep_075"),  # |0.75-0.5| beats |0-0.5|
        ({"sweep_100": 0.7, "sweep_025": 0.7}, "sweep_025"),  # same distance: registry order
        ({"sweep_050": 0.6, "gradient_mid": 0.6, "split_attn_code": 0.6}, "sweep_050"),  # all t=0.5: registry order
        ({"sweep_000": 0.9, "sweep_050": 0.8}, "sweep_000"),  # a higher score always wins
        ({"sweep_050": 0.3, "sweep_025": 0.3000000000001}, "sweep_050"),  # float noise is not a real difference
    ],
)
def test_pick_best(scores, expected):
    assert pick_best(scores, REGISTRY["blends"]) == expected


# ---- bad requests -----------------------------------------------------------


@pytest.mark.parametrize(
    "tasks",
    [
        [TASKS[1]] * (MAX_TASKS + 1),  # more than 3
        [],
        [{"kind": "code", "prompt": "x", "entry_point": "f"}],  # code task without tests
        [{"kind": "code", "prompt": "x", "tests": "assert f()"}],  # code task without entry_point
        [{"kind": "haiku", "prompt": "x"}],  # unknown kind
        [{"kind": "style", "prompt": "   "}],  # blank prompt
        ["just a string"],
        "not a list",
    ],
)
def test_bad_tasks_are_rejected(client, tasks):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg(tasks=tasks))
        msg = check_message(ws.receive_json())
    assert msg["type"] == "error" and msg["code"] == "bad_request"
    assert msg["request_id"] == "f1"


def test_three_tasks_are_accepted(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg(tasks=[TASKS[1]] * MAX_TASKS))
        assert run_finder(ws)[1]["type"] == "result"


# ---- scorer problems --------------------------------------------------------


def test_a_crashing_scorer_is_an_internal_error_and_the_finder_recovers(client):
    def crash(generate, tasks):
        raise ValueError("scorer bug")

    good = client.app.state.score_tasks
    client.app.state.score_tasks = crash
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg())
        _, error = run_finder(ws)
        assert error["code"] == "internal"
        assert "sweep_000" in error["message"] and "scorer bug" in error["message"]

        client.app.state.score_tasks = good  # not stuck "running" after a failure
        ws.send_json(find_msg("f2"))
        assert run_finder(ws, "f2")[1]["type"] == "result"


@pytest.mark.parametrize("bad_result", [{"score": 1.5}, {"score": -0.1}, {"score": True}, {"nope": 1}, "0.5"])
def test_an_invalid_score_is_an_internal_error(client, bad_result):
    client.app.state.score_tasks = lambda generate, tasks: bad_result
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg())
        _, error = run_finder(ws)
    assert error["code"] == "internal"
    assert "invalid score" in error["message"]


def slow_scorer(generate, tasks):
    time.sleep(0.15)
    return {"score": 0.5, "per_task": []}


def test_a_second_finder_run_at_the_same_time_gets_busy(client):
    client.app.state.score_tasks = slow_scorer
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        first.send_json(find_msg("f1"))
        assert check_message(first.receive_json())["type"] == "progress"  # first run is under way
        second.send_json(find_msg("f2"))
        error = check_message(second.receive_json())
        assert error["type"] == "error" and error["code"] == "busy"
        assert run_finder(first, "f1")[1]["type"] == "result"  # the first run is unaffected


# ---- cancel and disconnect --------------------------------------------------


def test_cancel_stops_the_run(client):
    client.app.state.score_tasks = slow_scorer
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg())
        assert check_message(ws.receive_json())["type"] == "progress"
        ws.send_json({"type": "cancel", "request_id": "f1"})
        _, end = run_finder(ws)
        assert end["type"] == "error" and end["code"] == "cancelled"
        assert client.app.state.finder_running is False

        ws.send_json(find_msg("f2"))  # a new run can start
        assert run_finder(ws, "f2")[1]["type"] == "result"


def test_disconnect_frees_the_finder(client):
    client.app.state.score_tasks = slow_scorer
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg())
        assert check_message(ws.receive_json())["type"] == "progress"
    deadline = time.monotonic() + 2
    while client.app.state.finder_running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert client.app.state.finder_running is False


# ---- with the real ModelManager (fake Llama) --------------------------------


@pytest.fixture
def managed(make_client, tmp_path):
    """A test app whose finder runs through the ModelManager, over a 3-blend registry, MAX_LOADED=2."""
    harness = Harness(tmp_path, max_loaded_models=2)
    client = make_client()
    client.app.state.registry = make_registry()
    client.app.state.manager = harness.manager
    client.app.state.stream = harness.manager.stream
    client.app.state.session = harness.manager.session
    return client, harness


def test_finder_through_the_model_manager(managed):
    client, harness = managed

    def scorer(generate, tasks):
        text = generate("probe")  # blocks in a worker thread, like the real scorer
        return {"score": 0.1 * len(text) % 1, "per_task": []}

    client.app.state.score_tasks = scorer
    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg())
        progress, result = run_finder(ws)

    assert [(p["step"], p["of"]) for p in progress] == [(1, 3), (2, 3), (3, 3)]
    assert result["type"] == "result" and set(result["scores"]) == {"sweep_000", "sweep_050", "sweep_100"}
    assert len(harness.manager.loaded) <= 2  # blends were swapped in and out, not all kept
    for llm in harness.loaded_llms.values():
        assert llm.max_active == 1
        assert llm.calls == [{"max_tokens": 512, "temperature": 0.0, "stream": True}]  # greedy, 512 tokens


def test_cancel_releases_the_model_lock(tmp_path, make_client):
    harness = Harness(tmp_path, llm_tokens=400)  # each generate() would take about 8 s
    client = make_client()
    client.app.state.registry = make_registry()
    client.app.state.manager = harness.manager
    client.app.state.stream = harness.manager.stream
    client.app.state.session = harness.manager.session
    client.app.state.score_tasks = lambda generate, tasks: {"score": len(generate("probe")) / 1e6, "per_task": []}

    with client.websocket_connect("/ws") as ws:
        ws.send_json(find_msg())
        assert check_message(ws.receive_json())["type"] == "progress"
        time.sleep(0.2)  # generation is running inside the scorer
        started = time.monotonic()
        ws.send_json({"type": "cancel", "request_id": "f1"})
        _, end = run_finder(ws)
        assert end["code"] == "cancelled"
        assert time.monotonic() - started < 1.0
        assert harness.loaded_llms["sweep_000"].active == 0  # inference really stopped

        ws.send_json({"type": "generate", "request_id": "g1", "blend_id": "sweep_000", "prompt": "hi", "max_tokens": 3})
        assert collect(ws, "g1")[-1]["type"] == "done"  # the model's lock was released
    assert harness.loaded_llms["sweep_000"].max_active == 1


# ---- startup ----------------------------------------------------------------


def test_missing_scoring_module_stops_startup():
    app = create_app(Settings(_env_file=None, scoring_module="src.eval.does_not_exist"))
    with pytest.raises(ConfigError, match="cannot be imported"), TestClient(app):
        pass


def test_scoring_module_without_score_tasks_stops_startup():
    app = create_app(Settings(_env_file=None, scoring_module="contracts.record_check"))
    with pytest.raises(ConfigError, match="no score_tasks"), TestClient(app):
        pass
