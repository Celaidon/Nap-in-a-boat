"""
Verification script for Check B1 (Datasets).
Executes dataset checks and records verification status in verification/B1.json.
"""

import json
import pathlib

from contracts.record_check import record_check


def verify_b1() -> dict:
    coding_path = pathlib.Path("data/coding_set.jsonl")
    style_path = pathlib.Path("data/style_prompts.jsonl")

    assert coding_path.exists(), "data/coding_set.jsonl missing"
    assert style_path.exists(), "data/style_prompts.jsonl missing"

    coding_lines = coding_path.read_text(encoding="utf-8").strip().splitlines()
    style_lines = style_path.read_text(encoding="utf-8").strip().splitlines()

    n_coding = len(coding_lines)
    n_style = len(style_lines)

    assert n_coding >= 50, f"Expected >= 50 coding problems, got {n_coding}"
    assert n_style == 20, f"Expected 20 style prompts, got {n_style}"

    # Verify reference solutions pass rate
    passed_ref = 0
    failed_broken = 0

    for line in coding_lines:
        item = json.loads(line)
        sol = item["reference_solution"]
        tests = item["tests"]
        entry_point = item["entry_point"]

        # 1. Reference solution test
        g1 = {}
        try:
            exec(sol + "\n\n" + tests, g1)  # noqa: S102
            passed_ref += 1
        except Exception as e:  # noqa: BLE001
            print(f"Error running ref sol for {item['id']}: {e}")

        # 2. Broken solution test
        dummy_code = f"def {entry_point}(*args, **kwargs):\n    return None"
        g2 = {}
        try:
            exec(dummy_code + "\n\n" + tests, g2)  # noqa: S102
        except Exception:  # noqa: BLE001
            failed_broken += 1

    ref_pass_rate = passed_ref / n_coding
    broken_fail_rate = failed_broken / n_coding

    assert ref_pass_rate == 1.0, f"Reference pass rate must be 1.0, got {ref_pass_rate}"
    assert broken_fail_rate == 1.0, f"Broken solution fail rate must be 1.0, got {broken_fail_rate}"

    details = {
        "n_coding": n_coding,
        "n_style": n_style,
        "reference_pass_rate": ref_pass_rate,
        "broken_fail_rate": broken_fail_rate,
    }

    result = record_check(
        check_id="B1",
        status="pass",
        owner="muskan",
        details=details,
    )
    return result


if __name__ == "__main__":
    verify_b1()
