"""Repo checks that CI runs on every PR (and anyone can run locally):

    python scripts/validate_repo.py

1. models/registry.json and results/metrics.json, if committed, must match the contract schemas.
2. No model weights (.gguf, .safetensors, .bin) and no .env may be tracked by Git, and no tracked
   file may be over 5 MB (plan section 9.8).
Exits 0 when clean, 1 with one line per problem otherwise.
"""

import json
import os
import pathlib
import subprocess
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (committed data file, its contract schema). Missing files are fine: they arrive at S2 / S3.
DATA_FILES = [
    ("models/registry.json", "contracts/schemas/registry.schema.json"),
    ("results/metrics.json", "contracts/schemas/metrics.schema.json"),
]
FORBIDDEN_SUFFIXES = (".gguf", ".safetensors", ".bin")
MAX_FILE_BYTES = 5 * 1024 * 1024


def check_data_files(root: pathlib.Path) -> list[str]:
    problems = []
    for data_path, schema_path in DATA_FILES:
        path = root / data_path
        if not path.exists():
            print(f"skip  {data_path} (not committed yet)")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            schema = json.loads((root / schema_path).read_text(encoding="utf-8"))
            jsonschema.validate(instance=data, schema=schema)
        except json.JSONDecodeError as exc:
            problems.append(f"{data_path}: not valid JSON ({exc})")
        except jsonschema.ValidationError as exc:
            where = "/".join(str(p) for p in exc.absolute_path) or "(top level)"
            problems.append(f"{data_path}: breaks {schema_path}: {exc.message} (at {where})")
        else:
            print(f"ok    {data_path} matches {pathlib.Path(schema_path).name}")
    return problems


def tracked_files(root: pathlib.Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    return [name for name in out.split("\0") if name]


def check_tracked_files(root: pathlib.Path) -> list[str]:
    problems = []
    for name in tracked_files(root):
        base = pathlib.PurePosixPath(name).name
        if name.endswith(FORBIDDEN_SUFFIXES):
            problems.append(f"{name}: model weights must never be committed (they go to Spaces)")
        elif base == ".env":
            problems.append(f"{name}: .env holds secrets and must never be committed")
        elif (root / name).is_file() and (root / name).stat().st_size > MAX_FILE_BYTES:
            problems.append(f"{name}: over 5 MB; large files do not belong in Git")
    if not problems:
        print("ok    no model files, .env or oversized files are tracked")
    return problems


def main(root: pathlib.Path = ROOT) -> int:
    problems = check_data_files(root) + check_tracked_files(root)
    for problem in problems:
        print(f"FAIL  {problem}")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::error title=Repo check failed::{problem}")  # shows on the run page without opening logs
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
