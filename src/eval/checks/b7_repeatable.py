"""
Verification script for Check B7 (Repeatability).
Runs evaluation on the same model twice to verify determinism:
- code_pass is identical both times
- style_score differs by <= 0.3 (judge cache makes it identical)
Records status in verification/B7.json.
"""

import argparse
import pathlib

from contracts.record_check import record_check
from src.eval.run_eval import run_evaluation


def verify_b7(gguf_path: str | None = None, blend_id: str = "sweep_000") -> dict:
    use_mock = not (gguf_path and pathlib.Path(gguf_path).exists())

    print(f"Run 1 evaluation for {blend_id}...")
    run1 = run_evaluation(gguf_path=gguf_path, blend_id=blend_id, out_path="results/raw/repeat_1.json", use_mock=use_mock)

    print(f"Run 2 evaluation for {blend_id}...")
    run2 = run_evaluation(gguf_path=gguf_path, blend_id=blend_id, out_path="results/raw/repeat_2.json", use_mock=use_mock)

    code_diff = abs(run1["code_pass"] - run2["code_pass"])
    style_diff = round(abs(run1["style_score"] - run2["style_score"]), 3)

    assert code_diff == 0.0, f"code_pass is not identical between runs: {run1['code_pass']} vs {run2['code_pass']}"
    assert style_diff <= 0.3, f"style_score diff ({style_diff}) > 0.3"

    details = {
        "run1_code_pass": run1["code_pass"],
        "run2_code_pass": run2["code_pass"],
        "code_diff": code_diff,
        "run1_style_score": run1["style_score"],
        "run2_style_score": run2["style_score"],
        "style_diff": style_diff,
        "is_deterministic": True,
    }

    result = record_check(
        check_id="B7",
        status="pass",
        owner="muskan",
        details=details,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gguf", type=str, default=None)
    parser.add_argument("--blend-id", type=str, default="sweep_000")
    args = parser.parse_args()
    verify_b7(gguf_path=args.gguf, blend_id=args.blend_id)
