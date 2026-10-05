# Check C7 (part): scripts/smoke_test.py works against a live server. The Docker image itself is
# built and smoke-tested by the `docker` job in CI, because Docker is not available on every dev machine.
import importlib.util
import socket
import threading
import time

import pytest
import uvicorn

from src.server.main import create_app
from src.server.settings import ROOT, Settings

spec = importlib.util.spec_from_file_location("smoke_test", ROOT / "scripts" / "smoke_test.py")
smoke_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke_test)


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


def test_smoke_test_passes_against_a_live_server(live_server, capsys):
    code = smoke_test.main([live_server, "--tokens", "10", "--blends", "sweep_000,sweep_050"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "SMOKE TEST PASSED" in out
    assert out.count("ok  /ws") == 2
    assert "RESULT {" in out


def test_smoke_test_fails_when_too_few_tokens_arrive(live_server, capsys):
    code = smoke_test.main([live_server, "--tokens", "3", "--min-tokens", "50"])
    assert code == 1
    assert "only 3 tokens" in capsys.readouterr().out


def test_smoke_test_fails_on_unknown_blend(live_server, capsys):
    code = smoke_test.main([live_server, "--blends", "sweep_999"])
    assert code == 1
    assert "not in the registry" in capsys.readouterr().out


def test_smoke_test_fails_when_nothing_is_listening(capsys):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    assert smoke_test.main([f"http://127.0.0.1:{port}"]) == 1
    assert "FAILED" in capsys.readouterr().out
