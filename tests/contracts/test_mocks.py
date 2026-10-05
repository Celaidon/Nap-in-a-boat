# tests/contracts/test_mocks.py
# Phase 0, check P1: validates both mock files against their JSON schemas.
# Run with: pytest tests/contracts/test_mocks.py
# This test runs in CI (no @pytest.mark.models needed — no model files required).

import json
import pathlib

import jsonschema
import pytest

ROOT = pathlib.Path(__file__).parent.parent.parent  # repo root


def load_json(rel_path: str) -> dict:
    return json.loads((ROOT / rel_path).read_text())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry_schema():
    return load_json("contracts/schemas/registry.schema.json")


@pytest.fixture
def metrics_schema():
    return load_json("contracts/schemas/metrics.schema.json")


@pytest.fixture
def mock_registry():
    return load_json("contracts/mocks/registry.json")


@pytest.fixture
def mock_metrics():
    return load_json("contracts/mocks/metrics.json")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_mock_registry_validates(mock_registry, registry_schema):
    """Mock registry must pass the registry schema (P1)."""
    jsonschema.validate(instance=mock_registry, schema=registry_schema)


def test_mock_metrics_validates(mock_metrics, metrics_schema):
    """Mock metrics must pass the metrics schema (P1)."""
    jsonschema.validate(instance=mock_metrics, schema=metrics_schema)


def test_registry_has_all_eight_blends(mock_registry):
    """All 8 blend IDs from section 1.3 must be present in the mock registry."""
    expected_ids = {
        "sweep_000", "sweep_025", "sweep_050", "sweep_075", "sweep_100",
        "split_attn_code", "split_mlp_code", "gradient_mid",
    }
    actual_ids = {b["id"] for b in mock_registry["blends"]}
    assert actual_ids == expected_ids, f"Missing: {expected_ids - actual_ids}"


def test_registry_t_values(mock_registry):
    """Every blend's t must be between 0 and 1 inclusive."""
    for blend in mock_registry["blends"]:
        assert 0.0 <= blend["t"] <= 1.0, f"{blend['id']}: t={blend['t']} out of range"


def test_registry_parent_method(mock_registry):
    """sweep_000 and sweep_100 must use method='parent'; all others must use 'slerp'."""
    parent_ids = {"sweep_000", "sweep_100"}
    for blend in mock_registry["blends"]:
        if blend["id"] in parent_ids:
            assert blend["method"] == "parent", f"{blend['id']} should be method=parent"
        else:
            assert blend["method"] == "slerp", f"{blend['id']} should be method=slerp"


def test_metrics_has_all_eight_blends(mock_metrics):
    """All 8 blend IDs must be present in the mock metrics."""
    expected_ids = {
        "sweep_000", "sweep_025", "sweep_050", "sweep_075", "sweep_100",
        "split_attn_code", "split_mlp_code", "gradient_mid",
    }
    actual_ids = {b["blend_id"] for b in mock_metrics["blends"]}
    assert actual_ids == expected_ids, f"Missing: {expected_ids - actual_ids}"


def test_metrics_score_ranges(mock_metrics):
    """Numeric scores must stay within their documented bounds."""
    for blend in mock_metrics["blends"]:
        bid = blend["blend_id"]
        assert 0.0 <= blend["code_pass"] <= 1.0, f"{bid}: code_pass out of range"
        assert 0.0 <= blend["style_score"] <= 10.0, f"{bid}: style_score out of range"
        assert 0.0 <= blend["rhyme_score"] <= 1.0, f"{bid}: rhyme_score out of range"
        assert blend["tokens_per_sec"] >= 0, f"{bid}: negative tokens_per_sec"
