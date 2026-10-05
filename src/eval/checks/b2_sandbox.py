"""
Verification script for Check B2 (Sandbox).
Executes sandbox tests and records verification status in verification/B2.json.
"""

from contracts.record_check import record_check
from src.eval.sandbox import _is_docker_available, run_tests


def verify_b2() -> dict:
    # 1. Correct code test
    res_correct = run_tests("def add(a, b):\n    return a + b", "assert add(2, 3) == 5")
    assert res_correct["passed"] is True, f"Correct code failed: {res_correct}"

    # 2. Wrong answer test
    res_wrong = run_tests("def add(a, b):\n    return a - b", "assert add(2, 3) == 5")
    assert res_wrong["passed"] is False, f"Wrong answer passed: {res_wrong}"

    # 3. Timeout test
    res_timeout = run_tests("def loop():\n    while True:\n        pass", "loop()", timeout_s=2)
    assert res_timeout["timed_out"] is True, f"Infinite loop did not timeout: {res_timeout}"

    # 4. Network block test
    res_net = run_tests(
        "import urllib.request\ndef fetch():\n    return urllib.request.urlopen('https://example.com').read()",
        "fetch()",
        timeout_s=3,
    )
    assert res_net["passed"] is False, "Network fetch succeeded when it should be blocked!"

    details = {
        "docker_available": _is_docker_available(),
        "correct_code_passed": res_correct["passed"],
        "wrong_code_failed": not res_wrong["passed"],
        "infinite_loop_killed": res_timeout["timed_out"],
        "network_blocked": not res_net["passed"],
    }

    result = record_check(
        check_id="B2",
        status="pass",
        owner="muskan",
        details=details,
    )
    return result


if __name__ == "__main__":
    verify_b2()
