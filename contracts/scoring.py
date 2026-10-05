# contracts/scoring.py
# This is the CONTRACT definition of the scoring function signature.
# Track B delivers the real implementation in src/eval/scoring.py.
# Track C's Best Blend Finder imports from src/eval/scoring.py at runtime;
# this file exists so anyone can read the interface without needing Track B's code.

from collections.abc import Callable
from typing import Literal, TypedDict


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

    CONTRACT: This signature is frozen. Do not change field names or types
    without a PR approved by all three track owners.
    """
    # MOCK: deterministic, no model calls. Replace with src/eval/scoring.py.
    per_task = [{"kind": t.get("kind", "style"), "score": 0.5} for t in tasks]
    return {"score": 0.5, "per_task": per_task}
