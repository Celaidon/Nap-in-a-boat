"""
Verification script for Check B4 (Style Judge).
Executes judge consistency and calibration tests and records verification status in verification/B4.json.
"""

from contracts.record_check import record_check
from src.eval.judge import judge_style


def verify_b4() -> dict:
    prompt = "Write a rhyming poem about a starry night."
    good = (
        "The stars are shining bright tonight,\n"
        "They fill the sky with silver light.\n"
        "The moon is full and soft and clear,\n"
        "And brings a quiet peace so near."
    )
    bad = "star night night sky star bright blue."

    s1 = judge_style(prompt, good)
    s2 = judge_style(prompt, good)
    s_bad = judge_style(prompt, bad)

    consistency_diff = abs(s1["overall"] - s2["overall"])
    is_consistent = consistency_diff <= 1.0
    is_calibrated = s1["overall"] >= s_bad["overall"]

    details = {
        "good_score": s1["overall"],
        "bad_score": s_bad["overall"],
        "consistency_diff": consistency_diff,
        "is_consistent": is_consistent,
        "is_calibrated": is_calibrated,
    }

    result = record_check(
        check_id="B4",
        status="pass" if (is_consistent and is_calibrated) else "fail",
        owner="muskan",
        details=details,
    )
    return result


if __name__ == "__main__":
    verify_b4()
