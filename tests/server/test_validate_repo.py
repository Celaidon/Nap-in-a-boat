# Check C9 (part): scripts/validate_repo.py catches broken data files and forbidden files.
import importlib.util
import json
import shutil
import subprocess

import pytest

from src.server.settings import ROOT

spec = importlib.util.spec_from_file_location("validate_repo", ROOT / "scripts" / "validate_repo.py")
validate_repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_repo)


class Repo:
    """A throwaway git repo holding the contract schemas, like the real one."""

    def __init__(self, path):
        self.path = path
        shutil.copytree(ROOT / "contracts", path / "contracts", ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)

    def add(self, relative: str, content: bytes | str) -> None:
        file = self.path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content if isinstance(content, bytes) else content.encode())
        subprocess.run(["git", "add", "-f", relative], cwd=self.path, check=True)


@pytest.fixture
def repo(tmp_path):
    return Repo(tmp_path)


def mock(name: str) -> str:
    return (ROOT / "contracts" / "mocks" / name).read_text()


def test_clean_repo_passes_even_without_the_data_files(repo, capsys):
    assert validate_repo.main(repo.path) == 0
    assert "not committed yet" in capsys.readouterr().out


def test_valid_registry_and_metrics_pass(repo, capsys):
    repo.add("models/registry.json", mock("registry.json"))
    repo.add("results/metrics.json", mock("metrics.json"))
    assert validate_repo.main(repo.path) == 0
    out = capsys.readouterr().out
    assert "models/registry.json matches" in out and "results/metrics.json matches" in out


def test_registry_that_breaks_the_schema_fails(repo, capsys):
    registry = json.loads(mock("registry.json"))
    registry["blends"][0]["id"] = "sweep_999"  # not one of the eight ids
    repo.add("models/registry.json", json.dumps(registry))
    assert validate_repo.main(repo.path) == 1
    assert "models/registry.json: breaks" in capsys.readouterr().out


def test_metrics_out_of_range_fails(repo, capsys):
    metrics = json.loads(mock("metrics.json"))
    metrics["blends"][0]["code_pass"] = 1.7
    repo.add("results/metrics.json", json.dumps(metrics))
    assert validate_repo.main(repo.path) == 1
    assert "results/metrics.json: breaks" in capsys.readouterr().out


def test_unparseable_json_fails(repo, capsys):
    repo.add("results/metrics.json", "{nope")
    assert validate_repo.main(repo.path) == 1
    assert "not valid JSON" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["models/sweep_050.gguf", "weights/model.safetensors", "x/pytorch_model.bin"])
def test_model_weights_are_rejected(repo, capsys, name):
    repo.add(name, b"fake weights")
    assert validate_repo.main(repo.path) == 1
    assert "model weights must never be committed" in capsys.readouterr().out


def test_env_file_is_rejected_but_env_example_is_fine(repo, capsys):
    repo.add(".env.example", "HF_TOKEN=\n")
    assert validate_repo.main(repo.path) == 0
    repo.add(".env", "HF_TOKEN=secret\n")
    assert validate_repo.main(repo.path) == 1
    assert ".env holds secrets" in capsys.readouterr().out


def test_oversized_file_is_rejected(repo, capsys):
    repo.add("results/huge.dat", b"x" * (validate_repo.MAX_FILE_BYTES + 1))
    assert validate_repo.main(repo.path) == 1
    assert "over 5 MB" in capsys.readouterr().out


def test_problems_become_github_annotations_in_ci(repo, capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    repo.add("models/sweep_050.gguf", b"fake weights")
    assert validate_repo.main(repo.path) == 1
    assert "::error title=Repo check failed::models/sweep_050.gguf" in capsys.readouterr().out
