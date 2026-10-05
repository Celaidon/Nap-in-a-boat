"""
Tests for Track B evaluation datasets:
- data/coding_set.jsonl
- data/style_prompts.jsonl
"""

import json
import pathlib

import pytest

DATA_DIR = pathlib.Path("data")
CODING_FILE = DATA_DIR / "coding_set.jsonl"
STYLE_FILE = DATA_DIR / "style_prompts.jsonl"


def test_coding_dataset_structure():
    assert CODING_FILE.exists(), f"{CODING_FILE} does not exist"

    lines = CODING_FILE.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 50, f"Expected at least 50 coding problems, got {len(lines)}"

    seen_ids = set()
    required_keys = {"id", "prompt", "entry_point", "tests", "reference_solution"}

    for idx, line in enumerate(lines, 1):
        item = json.loads(line)
        missing = required_keys - set(item.keys())
        assert not missing, f"Line {idx} missing keys: {missing}"

        assert item["id"] not in seen_ids, f"Duplicate ID found: {item['id']}"
        seen_ids.add(item["id"])

        assert isinstance(item["prompt"], str) and len(item["prompt"]) > 0
        assert isinstance(item["entry_point"], str) and len(item["entry_point"]) > 0
        assert isinstance(item["tests"], str) and len(item["tests"]) > 0
        assert isinstance(item["reference_solution"], str) and len(item["reference_solution"]) > 0


def test_coding_dataset_reference_solutions_pass():
    lines = CODING_FILE.read_text(encoding="utf-8").strip().splitlines()

    for idx, line in enumerate(lines, 1):
        item = json.loads(line)
        solution = item["reference_solution"]
        tests = item["tests"]

        exec_globals = {}
        try:
            exec(solution + "\n\n" + tests, exec_globals)  # noqa: S102
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"Problem {item['id']} reference solution failed tests: {e}")


def test_coding_dataset_broken_solutions_fail():
    lines = CODING_FILE.read_text(encoding="utf-8").strip().splitlines()

    for line in lines:
        item = json.loads(line)
        entry_point = item["entry_point"]
        tests = item["tests"]

        # Create a dummy solution returning None
        dummy_code = f"def {entry_point}(*args, **kwargs):\n    return None"

        exec_globals = {}
        failed = False
        try:
            exec(dummy_code + "\n\n" + tests, exec_globals)  # noqa: S102
        except (AssertionError, Exception):  # noqa: BLE001
            failed = True

        assert failed, f"Problem {item['id']} did not fail with dummy solution!"


def test_style_dataset_structure():
    assert STYLE_FILE.exists(), f"{STYLE_FILE} does not exist"

    lines = STYLE_FILE.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 20, f"Expected exactly 20 style prompts, got {len(lines)}"

    seen_ids = set()
    kind_counts = {"poem": 0, "story": 0, "email": 0, "explanation": 0}
    required_keys = {"id", "kind", "prompt"}

    for idx, line in enumerate(lines, 1):
        item = json.loads(line)
        missing = required_keys - set(item.keys())
        assert not missing, f"Line {idx} missing keys: {missing}"

        assert item["id"] not in seen_ids, f"Duplicate ID found: {item['id']}"
        seen_ids.add(item["id"])

        kind = item["kind"]
        assert kind in kind_counts, f"Invalid kind: {kind}"
        kind_counts[kind] += 1

        assert isinstance(item["prompt"], str) and len(item["prompt"]) > 0

    assert kind_counts["poem"] == 6, f"Expected 6 poems, got {kind_counts['poem']}"
    assert kind_counts["story"] == 5, f"Expected 5 stories, got {kind_counts['story']}"
    assert kind_counts["email"] == 5, f"Expected 5 emails, got {kind_counts['email']}"
    assert kind_counts["explanation"] == 4, f"Expected 4 explanations, got {kind_counts['explanation']}"
