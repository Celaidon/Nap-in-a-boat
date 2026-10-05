"""
Tests for Check B8 scoring module (src/eval/scoring.py).
Verifies score_tasks contracts, edge cases, and deterministic scoring.
"""

from src.eval.scoring import Task, score_tasks


def test_score_tasks_correct_code():
    tasks: list[Task] = [
        {
            "kind": "code",
            "prompt": "Write a function add(a, b)",
            "entry_point": "add",
            "tests": "assert add(1, 2) == 3\nassert add(-1, 1) == 0",
        }
    ]

    def mock_generate(prompt: str) -> str:
        return "```python\ndef add(a, b):\n    return a + b\n```"

    result = score_tasks(mock_generate, tasks)
    assert result["score"] == 1.0
    assert len(result["per_task"]) == 1
    assert result["per_task"][0]["kind"] == "code"
    assert result["per_task"][0]["score"] == 1.0


def test_score_tasks_failing_code():
    tasks: list[Task] = [
        {
            "kind": "code",
            "prompt": "Write a function add(a, b)",
            "entry_point": "add",
            "tests": "assert add(1, 2) == 3",
        }
    ]

    def mock_broken_generate(prompt: str) -> str:
        return "```python\ndef add(a, b):\n    return 0\n```"

    result = score_tasks(mock_broken_generate, tasks)
    assert result["score"] == 0.0
    assert len(result["per_task"]) == 1
    assert result["per_task"][0]["score"] == 0.0


def test_score_tasks_style():
    tasks: list[Task] = [
        {
            "kind": "style",
            "prompt": "Write a short poem about the night",
        }
    ]

    def mock_style_generate(prompt: str) -> str:
        return (
            "The stars are bright upon the sea,\n"
            "A calm and peaceful breeze runs free."
        )

    result = score_tasks(mock_style_generate, tasks)
    assert 0.0 <= result["score"] <= 1.0
    assert len(result["per_task"]) == 1
    assert result["per_task"][0]["kind"] == "style"
    assert 0.0 <= result["per_task"][0]["score"] <= 1.0


def test_score_tasks_mixed():
    tasks: list[Task] = [
        {
            "kind": "code",
            "prompt": "Write mul(a, b)",
            "entry_point": "mul",
            "tests": "assert mul(3, 4) == 12",
        },
        {
            "kind": "style",
            "prompt": "Write a friendly greeting",
        },
    ]

    def mock_mixed_generate(prompt: str) -> str:
        if "mul" in prompt:
            return "```python\ndef mul(a, b):\n    return a * b\n```"
        return "Hello, welcome to BlendLab! It is wonderful to meet you."

    result = score_tasks(mock_mixed_generate, tasks)
    assert len(result["per_task"]) == 2
    assert result["per_task"][0]["score"] == 1.0
    assert result["score"] == round(
        (result["per_task"][0]["score"] + result["per_task"][1]["score"]) / 2.0, 4
    )
