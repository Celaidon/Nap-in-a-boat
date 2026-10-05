"""
Script to build data/coding_set.jsonl from MBPP (sanitized).
Pick at least 50 coding problems, verify reference solutions pass tests,
and output format matching contract 4.7.
"""

import ast
import json
import pathlib
import random

from datasets import load_dataset


def extract_entry_point(code: str, test_list: list[str]) -> str:
    """Extract the main function entry point name from reference code or test list."""
    # First, try to see if a function name appears in test_list assertions
    for test in test_list:
        if "(" in test:
            # e.g., assert remove_Occ("hello","l") == "heo" -> remove_Occ
            part = test.split("(")[0]
            tokens = part.replace("assert", "").strip().split()
            if tokens:
                potential_fn = tokens[-1]
                if potential_fn.isidentifier():
                    return potential_fn

    # Fallback to ast parsing
    try:
        tree = ast.parse(code)
        fns = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        if fns:
            return fns[0]
    except (SyntaxError, ValueError):
        pass

    raise ValueError(f"Could not extract entry point from code:\n{code}")


def build_coding_set(output_path: str = "data/coding_set.jsonl", num_problems: int = 55, seed: int = 42):
    random.seed(seed)
    dataset = load_dataset("google-research-datasets/mbpp", "sanitized", split="test")

    valid_problems = []
    for sample in dataset:
        task_id = sample.get("task_id")
        prompt = sample.get("prompt")
        code = sample.get("code")
        test_list = sample.get("test_list", [])
        test_imports = sample.get("test_imports", [])

        if not prompt or not code or not test_list:
            continue

        try:
            entry_point = extract_entry_point(code, test_list)
        except ValueError:
            continue

        # Combine imports and tests into test execution string
        all_tests = []
        for imp in test_imports:
            if imp.strip() and imp.strip() not in all_tests:
                all_tests.append(imp.strip())
        for t in test_list:
            if t.strip():
                all_tests.append(t.strip())

        tests_str = "\n".join(all_tests)

        # Sanity check: execute reference_solution + tests in local scope
        exec_globals = {}
        try:
            exec(code + "\n\n" + tests_str, exec_globals)  # noqa: S102
        except (AssertionError, Exception):  # noqa: BLE001, S112
            # Skip if reference solution itself fails tests
            continue

        item = {
            "id": f"mbpp_{task_id}",
            "prompt": prompt.strip(),
            "entry_point": entry_point,
            "tests": tests_str,
            "reference_solution": code.strip(),
        }
        valid_problems.append(item)

    print(f"Total valid candidate problems: {len(valid_problems)}")
    if len(valid_problems) < num_problems:
        raise RuntimeError(f"Requested {num_problems} problems, but only found {len(valid_problems)} valid ones.")

    # Shuffle deterministically with seed and take num_problems
    random.shuffle(valid_problems)
    selected = sorted(valid_problems[:num_problems], key=lambda x: int(x["id"].split("_")[1]))

    out_file = pathlib.Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for item in selected:
            f.write(json.dumps(item) + "\n")

    print(f"Wrote {len(selected)} problems to {output_path}")


if __name__ == "__main__":
    build_coding_set()
