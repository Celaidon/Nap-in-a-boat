# Check C1: REST endpoints serve contract-valid data, and bad data stops startup.
import json
import pathlib

import jsonschema
import pytest
from fastapi.testclient import TestClient

from src.server.main import ConfigError, create_app
from src.server.settings import ROOT, Settings


def schema(name: str) -> dict:
    return json.loads((ROOT / "contracts" / "schemas" / name).read_text())


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None))) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "loaded": []}


def test_registry_matches_schema(client):
    r = client.get("/api/registry")
    assert r.status_code == 200
    jsonschema.validate(r.json(), schema("registry.schema.json"))
    assert len(r.json()["blends"]) == 8


def test_metrics_matches_schema(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    jsonschema.validate(r.json(), schema("metrics.schema.json"))


def start_with(tmp_path: pathlib.Path, **overrides):
    """Try to start the app with some settings pointing at bad files."""
    with TestClient(create_app(Settings(_env_file=None, **overrides))):
        pass


def test_invalid_registry_stops_startup(tmp_path):
    bad = tmp_path / "registry.json"
    bad.write_text(json.dumps({"pair": {"model_a": "a", "model_b": "b"}}))  # no "blends"
    with pytest.raises(ConfigError, match=r"Registry file .* does not match registry.schema.json"):
        start_with(tmp_path, registry_path=str(bad))


def test_missing_metrics_stops_startup(tmp_path):
    with pytest.raises(ConfigError, match="Metrics file not found"):
        start_with(tmp_path, metrics_path=str(tmp_path / "nope.json"))


def test_unparseable_registry_stops_startup(tmp_path):
    bad = tmp_path / "registry.json"
    bad.write_text("{not json")
    with pytest.raises(ConfigError, match="not valid JSON"):
        start_with(tmp_path, registry_path=str(bad))
