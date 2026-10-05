# Check C8 (helpers): scripts/record_deploy.py records the right verification data. The real
# deployment on a DigitalOcean Droplet cannot be tested here; this proves the recorder against a live local server.
import importlib.util

import pytest

from src.server.settings import ROOT

spec = importlib.util.spec_from_file_location("record_deploy", ROOT / "scripts" / "record_deploy.py")
record_deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record_deploy)


@pytest.fixture
def recorded(monkeypatch):
    """Capture record_check calls instead of writing verification/C8.json into the repo."""
    calls = []
    monkeypatch.setattr(record_deploy, "record_check", lambda *args: calls.append(args))
    return calls


def test_records_pass_with_speed_for_each_key_blend(live_server, recorded):
    assert record_deploy.main([live_server, "--tokens", "10"]) == 0
    check_id, status, owner, details = recorded[0]
    assert (check_id, status, owner) == ("C8", "pass", "sharva")
    assert set(details["tokens_per_sec"]) == {"sweep_000", "sweep_050", "sweep_100"}
    assert details["base_url"] == live_server
    assert "warning" not in details


def test_slow_speed_is_flagged_in_the_record(live_server, recorded, monkeypatch):
    monkeypatch.setattr(record_deploy, "MIN_TOKENS_PER_SEC", 10_000)  # nothing is that fast
    assert record_deploy.main([live_server, "--tokens", "10"]) == 0
    assert "tell the team" in recorded[0][3]["warning"]


def test_unreachable_server_records_a_failure(recorded):
    assert record_deploy.main(["http://127.0.0.1:9"]) == 1
    check_id, status, _, details = recorded[0]
    assert (check_id, status) == ("C8", "fail")
    assert "error" in details
