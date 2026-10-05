# Best Blend Finder: score every blend on the user's tasks and recommend one.
# This file never knows how scoring works; it just hands score_tasks a generate() function.
import threading
from collections.abc import Awaitable, Callable

from src.server.generate import GenerationError, run_blocking

MAX_TASKS = 3
TASK_KINDS = ("code", "style")


def validate_tasks(tasks) -> list[dict]:
    """Check the tasks from a find_best message; raise bad_request with a clear reason."""
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
        raise GenerationError("bad_request", f"find_best needs between 1 and {MAX_TASKS} tasks")
    for number, task in enumerate(tasks, 1):
        if not isinstance(task, dict):
            raise GenerationError("bad_request", f"Task {number} must be an object")
        if task.get("kind") not in TASK_KINDS:
            raise GenerationError("bad_request", f"Task {number}: kind must be 'code' or 'style'")
        if not isinstance(task.get("prompt"), str) or not task["prompt"].strip():
            raise GenerationError("bad_request", f"Task {number}: prompt must be a non-empty string")
        if task["kind"] == "code":
            for name in ("entry_point", "tests"):
                if not isinstance(task.get(name), str) or not task[name].strip():
                    raise GenerationError("bad_request", f"Task {number}: code tasks need '{name}'")
    return tasks


def pick_best(scores: dict[str, float], blends: list[dict]) -> str:
    """Highest score wins. Ties go to the blend closest to t = 0.5, then to registry order."""
    rank = {b["id"]: (abs(b["t"] - 0.5), index) for index, b in enumerate(blends)}
    return min(scores, key=lambda blend_id: (-round(scores[blend_id], 9), *rank[blend_id]))


def check_score(blend_id: str, result) -> float:
    score = result.get("score") if isinstance(result, dict) else None
    if isinstance(score, bool) or not isinstance(score, int | float) or not 0 <= score <= 1:
        raise GenerationError("internal", f"Scoring returned an invalid score for {blend_id}: {result!r}")
    return float(score)


async def find_best(
    app,
    tasks: list[dict],
    stop: threading.Event,
    on_progress: Callable[[int, int, str], Awaitable[None]],
) -> tuple[str, dict[str, float]]:
    """Test every blend in the registry on `tasks`. Returns (best_blend_id, scores)."""
    if app.state.finder_running:
        raise GenerationError("busy", "Another Best Blend Finder run is in progress, try again shortly")
    app.state.finder_running = True  # no await since the check above, so only one run can win
    try:
        blends = app.state.registry["blends"]
        scores: dict[str, float] = {}
        for step, blend in enumerate(blends, 1):
            blend_id = blend["id"]
            await on_progress(step, len(blends), blend_id)
            try:
                # The session holds the model's lock for the whole scoring of this blend.
                async with app.state.session(blend_id, stop) as generate:
                    result = await run_blocking(app.state.score_tasks, generate, tasks)
            except GenerationError:
                raise
            except Exception as exc:
                raise GenerationError("internal", f"Scoring {blend_id} failed: {type(exc).__name__}: {exc}") from exc
            scores[blend_id] = check_score(blend_id, result)
        return pick_best(scores, blends), scores
    finally:
        app.state.finder_running = False
