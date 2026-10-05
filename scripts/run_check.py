# Runs one Track C check's tests and records the result with contracts/record_check.py.
# Usage: python scripts/run_check.py C1 [--details '{"key": "value"}']
# Writes verification/<ID>.json; commit that file in the same PR as the code.
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.record_check import record_check

# Which tests prove each check.
CHECK_TESTS = {
    "C1": ["tests/server/test_rest.py"],
    "C2": ["tests/server/test_ws.py"],
    "C3": ["tests/server/test_streaming.py"],
    "C4": ["tests/server/test_models.py"],
    "C5": ["tests/server/test_disconnect.py"],
    "C6": ["tests/server/test_finder.py"],
    "C7": ["tests/server/test_smoke.py"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("check_id", choices=sorted(CHECK_TESTS))
    parser.add_argument("--details", default="{}", help="extra JSON to store (e.g. timings)")
    parser.add_argument("--models", action="store_true", help="also run @pytest.mark.models tests")
    args = parser.parse_args()

    cmd = [sys.executable, "-m", "pytest", "-q", *CHECK_TESTS[args.check_id]]
    if not args.models:
        cmd += ["-m", "not models"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    print(proc.stdout)

    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    details = {"tests": CHECK_TESTS[args.check_id], "pytest_summary": summary}
    details.update(json.loads(args.details))
    record_check(args.check_id, "pass" if proc.returncode == 0 else "fail", "sharva", details)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
