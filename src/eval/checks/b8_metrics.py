"""
Verification script for Check B8 (Metrics, Curve, and Scoring Function).
Verifies metrics file matches contract schema, curve rendered, and scoring function passes tests.
Records status in verification/B8.json.
"""

import json
import pathlib

import jsonschema

from contracts.record_check import record_check
from src.eval.aggregate import aggregate_metrics
from src.eval.curve import plot_curve
from src.eval.scoring import Task, score_tasks

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "contracts" / "schemas" / "metrics.schema.json"


def verify_b8() -> dict:
    metrics = aggregate_metrics()
    metrics_path = pathlib.Path("results/metrics.json")
    assert metrics_path.exists(), "results/metrics.json not created"

    # 1. Schema validation
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=metrics, schema=schema)

    blend_ids = {b["blend_id"] for b in metrics["blends"]}
    expected_blends = {
        "sweep_000", "sweep_025", "sweep_050", "sweep_075", "sweep_100",
        "split_attn_code", "split_mlp_code", "gradient_mid"
    }
    assert expected_blends.issubset(blend_ids), f"Missing blends: {expected_blends - blend_ids}"

    # 2. Curve rendering
    curve_path = plot_curve()
    assert pathlib.Path(curve_path).exists(), "results/curve.png not created"
    assert pathlib.Path(curve_path).stat().st_size > 1000, "results/curve.png is empty"

    # 3. Test scoring function
    task: Task = {
        "kind": "code",
        "prompt": "Write inc(x)",
        "entry_point": "inc",
        "tests": "assert inc(4) == 5",
    }
    res_correct = score_tasks(lambda p: "```python\ndef inc(x):\n    return x + 1\n```", [task])
    assert res_correct["score"] == 1.0

    res_broken = score_tasks(lambda p: "```python\ndef inc(x):\n    return 0\n```", [task])
    assert res_broken["score"] == 0.0

    details = {
        "metrics_file_valid": True,
        "n_blends": len(metrics["blends"]),
        "curve_generated": True,
        "scoring_function_ready": True,
    }

    result = record_check(
        check_id="B8",
        status="pass",
        owner="muskan",
        details=details,
    )
    return result


if __name__ == "__main__":
    verify_b8()
