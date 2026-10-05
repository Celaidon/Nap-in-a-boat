# A stand-in SCORING_MODULE for the finder tests: gives sweep_075 the top score.
# It reads the blend's answer (the fake session answers "<blend_id>: ...") to know which blend it is scoring.


def score_tasks(generate, tasks):
    answer = generate("probe")
    score = 0.9 if answer.startswith("sweep_075") else 0.3
    return {"score": score, "per_task": [{"kind": t["kind"], "score": score} for t in tasks]}
