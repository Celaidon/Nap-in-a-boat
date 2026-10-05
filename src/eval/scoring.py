"""
Evaluation scoring module (src/eval/scoring.py).
Delivers the real score_tasks implementation matching contracts/scoring.py.
Used by Track C's Best Blend Finder.
"""

from collections.abc import Callable
from typing import Literal, TypedDict

from src.eval.extract import extract_code
from src.eval.judge import judge_style
from src.eval.sandbox import run_tests


class Task(TypedDict, total=False):
    kind: Literal["code", "style"]
    prompt: str
    entry_point: str   # code tasks only
    tests: str         # code tasks only: python assert lines


def score_tasks(generate: Callable[[str], str], tasks: list[Task]) -> dict:
    """Score one model on a few tasks.

    Args:
        generate: Callable that takes a prompt string and returns the model's
                  full text response.
        tasks: List of Task dicts. Each must have 'kind' and 'prompt'.
               Code tasks also need 'entry_point' and 'tests'.

    Returns:
        {
            "score": float,        # aggregate 0..1
            "per_task": [
                {"kind": str, "score": float}  # 0..1 per task
            ]
        }
    """
    if not tasks:
        return {"score": 0.0, "per_task": []}

    per_task = []
    for task in tasks:
        kind = task.get("kind", "style")
        prompt = task.get("prompt", "")

        if kind == "code":
            entry_point = task.get("entry_point", "")
            tests = task.get("tests", "")
            answer = generate(prompt)
            extracted = extract_code(answer, entry_point)
            sandbox_res = run_tests(extracted, tests)
            task_score = 1.0 if sandbox_res["passed"] else 0.0
        else:
            answer = generate(prompt)
            judge_res = judge_style(prompt, answer)
            overall = float(judge_res.get("overall", 5.0))
            task_score = round(min(1.0, max(0.0, overall / 10.0)), 4)

        per_task.append({"kind": kind, "score": task_score})

    avg_score = sum(t["score"] for t in per_task) / len(per_task)
    return {"score": round(avg_score, 4), "per_task": per_task}
