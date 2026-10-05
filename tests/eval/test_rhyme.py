"""
Tests for Check B5 rhyme and meter scorer (src/eval/rhyme.py).
"""

from src.eval.rhyme import rhyme_score


def test_rhyme_score_high_for_rhyming_poem():
    # Original rhyming poem with regular meter (AABB)
    poem = (
        "The gentle waves flow onto shore,\n"
        "The ocean whispers evermore.\n"
        "The golden sun begins to rise,\n"
        "And light up all the morning skies."
    )
    score = rhyme_score(poem)
    assert score > 0.7, f"Expected rhyming poem score > 0.7, got {score}"


def test_rhyme_score_low_for_free_prose():
    # Free prose split into lines without rhymes or regular meter
    prose = (
        "The computer algorithm processed the incoming database entries\n"
        "without any noticeable delay or memory bottleneck.\n"
        "System administrators monitored network bandwidth\n"
        "and logged system diagnostics to persistent storage."
    )
    score = rhyme_score(prose)
    assert score < 0.3, f"Expected free prose score < 0.3, got {score}"


def test_rhyme_score_empty_or_single_line():
    assert rhyme_score("") == 0.0
    assert rhyme_score("Single line poem") == 0.0
