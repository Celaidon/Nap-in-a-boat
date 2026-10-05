"""
Verification script for Check B5 (Rhyme Scorer).
Executes rhyme and meter scoring tests and records verification status in verification/B5.json.
"""

from contracts.record_check import record_check
from src.eval.rhyme import rhyme_score


def verify_b5() -> dict:
    poem = (
        "The gentle waves flow onto shore,\n"
        "The ocean whispers evermore.\n"
        "The golden sun begins to rise,\n"
        "And light up all the morning skies."
    )
    prose = (
        "The computer algorithm processed database records\n"
        "without memory bottleneck or system latency.\n"
        "Network infrastructure bandwidth was monitored\n"
        "and diagnostics logged to disk storage."
    )

    s_poem = rhyme_score(poem)
    s_prose = rhyme_score(prose)

    high_rhyme_pass = s_poem > 0.7
    low_prose_pass = s_prose < 0.3

    details = {
        "poem_score": s_poem,
        "prose_score": s_prose,
        "high_rhyme_pass": high_rhyme_pass,
        "low_prose_pass": low_prose_pass,
    }

    result = record_check(
        check_id="B5",
        status="pass" if (high_rhyme_pass and low_prose_pass) else "fail",
        owner="muskan",
        details=details,
    )
    return result


if __name__ == "__main__":
    verify_b5()
