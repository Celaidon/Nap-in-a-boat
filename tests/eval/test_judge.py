"""
Tests for Check B4 style judge (src/eval/judge.py).
"""

from src.eval.judge import judge_style


def test_judge_consistency():
    prompt = "Write a short poem about the night sky."
    answer = (
        "The night is quiet, deep and black,\n"
        "The stars trace out a glowing track.\n"
        "The silver moon sits high above,\n"
        "A quiet night we learn to love."
    )

    score1 = judge_style(prompt, answer)
    score2 = judge_style(prompt, answer)
    score3 = judge_style(prompt, answer)

    assert abs(score1["overall"] - score2["overall"]) <= 1.0
    assert abs(score2["overall"] - score3["overall"]) <= 1.0


def test_judge_calibration():
    prompt = "Write a clear explanation of machine learning."
    well_written = (
        "Machine learning is a field of artificial intelligence where computer systems learn from data "
        "to improve their performance on tasks without being explicitly programmed."
    )
    shuffled = "learning Machine intelligence artificial computer improve data tasks from."

    score_good = judge_style(prompt, well_written)
    score_bad = judge_style(prompt, shuffled)

    assert score_good["overall"] >= score_bad["overall"]


def test_judge_bad_output_handling():
    prompt = "Write a poem."
    empty_answer = ""

    score = judge_style(prompt, empty_answer)
    assert isinstance(score, dict)
    assert "overall" in score
    assert 1.0 <= score["overall"] <= 10.0
