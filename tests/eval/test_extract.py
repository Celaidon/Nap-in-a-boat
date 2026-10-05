"""
Tests for Check B3 code extractor (src/eval/extract.py).
"""

from src.eval.extract import extract_code


def test_extract_fenced_with_language_tag():
    raw = (
        "Here is the solution:\n\n"
        "```python\n"
        "def is_prime(n):\n"
        "    return n > 1\n"
        "```\n\n"
        "Hope this helps!"
    )
    code = extract_code(raw, "is_prime")
    assert code == "def is_prime(n):\n    return n > 1"


def test_extract_fenced_without_language_tag():
    raw = (
        "```\n"
        "def remove_occ(s, ch):\n"
        "    return s.replace(ch, '')\n"
        "```"
    )
    code = extract_code(raw, "remove_occ")
    assert code == "def remove_occ(s, ch):\n    return s.replace(ch, '')"


def test_extract_multiple_blocks_picks_matching_entry_point():
    raw = (
        "Here is a helper function:\n"
        "```python\n"
        "def helper():\n"
        "    pass\n"
        "```\n\n"
        "And here is the main function:\n"
        "```python\n"
        "def target_fn(x):\n"
        "    return x * 2\n"
        "```"
    )
    code = extract_code(raw, "target_fn")
    assert code == "def target_fn(x):\n    return x * 2"


def test_extract_no_fences_starts_at_def():
    raw = (
        "Sure! Here is the python code:\n\n"
        "def add(a, b):\n"
        "    return a + b\n\n"
        "That's all."
    )
    code = extract_code(raw, "add")
    assert code.startswith("def add(a, b):")


def test_extract_explanation_before_and_after():
    raw = (
        "The problem asks for removing duplicates.\n\n"
        "```python\n"
        "def remove_dups(lst):\n"
        "    return list(set(lst))\n"
        "```\n\n"
        "This function converts the list to a set."
    )
    code = extract_code(raw, "remove_dups")
    assert code == "def remove_dups(lst):\n    return list(set(lst))"


def test_extract_nothing_found_returns_whole_answer():
    raw = "I don't know how to solve this."
    code = extract_code(raw, "missing_fn")
    assert code == raw
