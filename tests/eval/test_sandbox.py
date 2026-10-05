"""
Tests for Check B2 safe sandbox runner (src/eval/sandbox.py).
"""

import pathlib
import time

from src.eval.sandbox import run_tests


def test_sandbox_correct_code():
    code = "def add(a, b):\n    return a + b"
    tests = "assert add(2, 3) == 5\nassert add(-1, 1) == 0"

    res = run_tests(code, tests, timeout_s=5)
    assert res["passed"] is True
    assert res["timed_out"] is False
    assert res["error"] is None


def test_sandbox_wrong_answer():
    code = "def add(a, b):\n    return a - b"
    tests = "assert add(2, 3) == 5"

    res = run_tests(code, tests, timeout_s=5)
    assert res["passed"] is False
    assert res["timed_out"] is False
    assert res["error"] is not None


def test_sandbox_infinite_loop_timeout():
    code = "def loop():\n    while True:\n        pass"
    tests = "loop()"

    start = time.time()
    res = run_tests(code, tests, timeout_s=2)
    duration = time.time() - start

    assert res["passed"] is False
    assert res["timed_out"] is True
    assert duration < 5.0, f"Expected timeout within ~2s, took {duration:.2f}s"


def test_sandbox_network_blocking_or_error():
    code = (
        "import urllib.request\n"
        "def fetch():\n"
        "    return urllib.request.urlopen('https://httpbin.org/get', timeout=2).read()\n"
    )
    tests = "res = fetch()\nassert len(res) > 0"

    res = run_tests(code, tests, timeout_s=4)
    # Network call should fail or be blocked
    assert res["passed"] is False


def test_sandbox_filesystem_isolation():
    test_file = pathlib.Path("test_leak.txt")
    if test_file.exists():
        test_file.unlink()

    code = (
        "def write_file():\n"
        "    with open('test_leak.txt', 'w') as f:\n"
        "        f.write('hacked')\n"
    )
    tests = "write_file()"

    run_tests(code, tests, timeout_s=5)

    # Check host file system outside temporary execution dir
    assert not test_file.exists(), "Host filesystem was mutated!"
