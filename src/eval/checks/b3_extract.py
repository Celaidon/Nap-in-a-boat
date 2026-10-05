"""
Verification script for Check B3 (Code Extraction).
Executes extraction test cases and records verification status in verification/B3.json.
"""

from contracts.record_check import record_check
from src.eval.extract import extract_code
from src.eval.prompts import format_coding_prompt


def verify_b3() -> dict:
    # 1. Fenced with language tag test
    raw1 = "```python\ndef fn1(): return 1\n```"
    c1 = extract_code(raw1, "fn1")
    assert c1 == "def fn1(): return 1"

    # 2. Fenced without language tag
    raw2 = "```\ndef fn2(): return 2\n```"
    c2 = extract_code(raw2, "fn2")
    assert c2 == "def fn2(): return 2"

    # 3. Multiple blocks test
    raw3 = "```python\ndef noise(): pass\n```\n```python\ndef fn3(): return 3\n```"
    c3 = extract_code(raw3, "fn3")
    assert c3 == "def fn3(): return 3"

    # 4. No fences test
    raw4 = "Explanation...\ndef fn4(): return 4\nEnd"
    c4 = extract_code(raw4, "fn4")
    assert c4.startswith("def fn4(): return 4")

    # 5. Nothing found test
    raw5 = "No code here"
    c5 = extract_code(raw5, "fn5")
    assert c5 == "No code here"

    # 6. Test prompt template formatting
    prompt_str = format_coding_prompt("test_fn", "Write a function that adds two numbers.")
    assert "test_fn" in prompt_str

    details = {
        "fenced_lang_tag": c1 == "def fn1(): return 1",
        "fenced_no_tag": c2 == "def fn2(): return 2",
        "multiple_blocks_picked": c3 == "def fn3(): return 3",
        "no_fences_extracted": c4.startswith("def fn4(): return 4"),
        "fallback_whole_answer": c5 == "No code here",
        "prompt_template_valid": "test_fn" in prompt_str,
    }

    result = record_check(
        check_id="B3",
        status="pass",
        owner="muskan",
        details=details,
    )
    return result


if __name__ == "__main__":
    verify_b3()
