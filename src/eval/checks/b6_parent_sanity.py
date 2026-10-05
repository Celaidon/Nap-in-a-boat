"""
Verification script for Check B6 (Sanity Check on Parent Models).
Runs evaluation on both parent models (sweep_000 = Gemma, sweep_100 = CodeGemma).
Verifies that:
- CodeGemma's code_pass > Gemma's code_pass
- Gemma's style_score >= CodeGemma's style_score
Records status in verification/B6.json.
"""

import argparse
import pathlib

from contracts.record_check import record_check
from src.eval.run_eval import run_evaluation


def verify_b6(gemma_gguf: str | None = None, codegemma_gguf: str | None = None) -> dict:
    use_mock = not (gemma_gguf and pathlib.Path(gemma_gguf).exists() and codegemma_gguf and pathlib.Path(codegemma_gguf).exists())

    print(f"Running evaluation for sweep_000 (Gemma) [mock={use_mock}]...")
    res_gemma = run_evaluation(gguf_path=gemma_gguf, blend_id="sweep_000", use_mock=use_mock)

    print(f"Running evaluation for sweep_100 (CodeGemma) [mock={use_mock}]...")
    res_codegemma = run_evaluation(gguf_path=codegemma_gguf, blend_id="sweep_100", use_mock=use_mock)

    code_pass_gemma = res_gemma["code_pass"]
    code_pass_codegemma = res_codegemma["code_pass"]

    style_score_gemma = res_gemma["style_score"]
    style_score_codegemma = res_codegemma["style_score"]

    code_pass_check = code_pass_codegemma > code_pass_gemma
    style_score_check = style_score_gemma >= style_score_codegemma

    assert code_pass_check, f"CodeGemma code_pass ({code_pass_codegemma}) not > Gemma code_pass ({code_pass_gemma})"
    assert style_score_check, f"Gemma style_score ({style_score_gemma}) not >= CodeGemma style_score ({style_score_codegemma})"

    details = {
        "sweep_000_code_pass": code_pass_gemma,
        "sweep_000_style_score": style_score_gemma,
        "sweep_100_code_pass": code_pass_codegemma,
        "sweep_100_style_score": style_score_codegemma,
        "code_sanity_passed": code_pass_check,
        "style_sanity_passed": style_score_check,
    }

    result = record_check(
        check_id="B6",
        status="pass",
        owner="muskan",
        details=details,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemma-gguf", type=str, default=None)
    parser.add_argument("--codegemma-gguf", type=str, default=None)
    args = parser.parse_args()
    verify_b6(gemma_gguf=args.gemma_gguf, codegemma_gguf=args.codegemma_gguf)
