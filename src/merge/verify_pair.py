# src/merge/verify_pair.py
# Check A1: Verify that Model A and Model B are compatible for SLERP merging.
#
# What we check (without loading full weights into memory):
#   1. Architecture config fields match
#   2. Tokenizer vocabularies and special tokens match
#   3. Every tensor name and shape matches (reading safetensors headers only)
#
# Run:
#   python -m src.merge.verify_pair
#
# Pass condition: 0 config mismatches, identical vocab, 0 tensor mismatches.

from __future__ import annotations

import json
import os
import pathlib
from collections.abc import Generator

from dotenv import load_dotenv
from huggingface_hub import snapshot_download
from safetensors import safe_open
from transformers import AutoTokenizer

from contracts.record_check import record_check

# ── Config ──────────────────────────────────────────────────────────────────

load_dotenv()

MODEL_A = "google/gemma-1.1-7b-it"
MODEL_B = "google/codegemma-7b-it"
CACHE_DIR = pathlib.Path("hf_cache")

# Fields that must be identical for SLERP to be valid.
REQUIRED_CONFIG_FIELDS = [
    "hidden_size",
    "num_hidden_layers",
    "num_attention_heads",
    "num_key_value_heads",
    "intermediate_size",
    "head_dim",
    "vocab_size",
    "rope_theta",
    "model_type",
]

# ── Helpers ──────────────────────────────────────────────────────────────────


def download_model(model_id: str) -> pathlib.Path:
    """Download config + tokenizer + safetensors headers to hf_cache/.
    Uses the HF_TOKEN env var for gated models (Gemma requires login).
    """
    token = os.environ.get("HF_TOKEN")
    print(f"\n[download] {model_id} …")
    local_dir = snapshot_download(
        repo_id=model_id,
        cache_dir=str(CACHE_DIR),
        token=token,
        ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*"],
    )
    print(f"[download] saved to {local_dir}")
    return pathlib.Path(local_dir)


def load_config(model_dir: pathlib.Path) -> dict:
    """Load config.json from the model directory."""
    config_path = model_dir / "config.json"
    return json.loads(config_path.read_text())


def compare_configs(cfg_a: dict, cfg_b: dict) -> list[str]:
    """Return a list of mismatch descriptions for the required fields."""
    mismatches = []
    for field in REQUIRED_CONFIG_FIELDS:
        val_a = cfg_a.get(field, "<missing>")
        val_b = cfg_b.get(field, "<missing>")
        if val_a != val_b:
            mismatches.append(f"  {field}: A={val_a!r}  B={val_b!r}")
    return mismatches


def compare_tokenizers(dir_a: pathlib.Path, dir_b: pathlib.Path) -> list[str]:
    """Compare vocabularies and special tokens. Returns mismatch descriptions."""
    mismatches = []
    token = os.environ.get("HF_TOKEN")

    print("[tokenizer] loading A …")
    tok_a = AutoTokenizer.from_pretrained(str(dir_a), token=token)
    print("[tokenizer] loading B …")
    tok_b = AutoTokenizer.from_pretrained(str(dir_b), token=token)

    vocab_a = tok_a.get_vocab()
    vocab_b = tok_b.get_vocab()

    if vocab_a != vocab_b:
        only_a = set(vocab_a) - set(vocab_b)
        only_b = set(vocab_b) - set(vocab_a)
        different_ids = {
            tok for tok in set(vocab_a) & set(vocab_b)
            if vocab_a[tok] != vocab_b[tok]
        }
        if only_a:
            mismatches.append(f"  tokens only in A ({len(only_a)}): {list(only_a)[:5]} …")
        if only_b:
            mismatches.append(f"  tokens only in B ({len(only_b)}): {list(only_b)[:5]} …")
        if different_ids:
            mismatches.append(f"  tokens with different IDs ({len(different_ids)}): {list(different_ids)[:5]} …")

    # Check special tokens
    special_a = {k: str(v) for k, v in tok_a.special_tokens_map.items()}
    special_b = {k: str(v) for k, v in tok_b.special_tokens_map.items()}
    if special_a != special_b:
        mismatches.append(f"  special tokens differ: A={special_a}  B={special_b}")

    return mismatches


def iter_tensor_shapes(model_dir: pathlib.Path) -> Generator[tuple[str, list[int]], None, None]:
    """Yield (tensor_name, shape) by reading safetensors headers only — no weights loaded."""
    shard_paths = sorted(model_dir.glob("*.safetensors"))
    if not shard_paths:
        raise FileNotFoundError(f"No .safetensors files found in {model_dir}")
    for shard in shard_paths:
        with safe_open(str(shard), framework="pt") as f:
            for name in f:
                shape = list(f.get_slice(name).get_shape())
                yield name, shape


def compare_tensors(dir_a: pathlib.Path, dir_b: pathlib.Path) -> tuple[list[str], int]:
    """Compare tensor names and shapes between two models.
    Returns (list of mismatch descriptions, total tensor count).
    """
    print("[tensors] reading A headers …")
    tensors_a = dict(iter_tensor_shapes(dir_a))
    print(f"[tensors] A has {len(tensors_a)} tensors")

    print("[tensors] reading B headers …")
    tensors_b = dict(iter_tensor_shapes(dir_b))
    print(f"[tensors] B has {len(tensors_b)} tensors")

    mismatches = []
    total = max(len(tensors_a), len(tensors_b))

    only_a = set(tensors_a) - set(tensors_b)
    only_b = set(tensors_b) - set(tensors_a)
    for name in sorted(only_a)[:10]:
        mismatches.append(f"  tensor only in A: {name} shape={tensors_a[name]}")
    for name in sorted(only_b)[:10]:
        mismatches.append(f"  tensor only in B: {name} shape={tensors_b[name]}")

    for name in set(tensors_a) & set(tensors_b):
        if tensors_a[name] != tensors_b[name]:
            mismatches.append(
                f"  shape mismatch {name}: A={tensors_a[name]}  B={tensors_b[name]}"
            )

    return mismatches, total


# ── Main ─────────────────────────────────────────────────────────────────────


def run_verification(model_a: str = MODEL_A, model_b: str = MODEL_B) -> dict:
    """Run the full A1 compatibility check. Returns the details dict."""
    print("=" * 60)
    print("A1: Pair Compatibility Check")
    print(f"  Model A: {model_a}")
    print(f"  Model B: {model_b}")
    print("=" * 60)

    # 1. Download
    dir_a = download_model(model_a)
    dir_b = download_model(model_b)

    # 2. Config comparison
    print("\n[config] comparing architecture fields …")
    cfg_a = load_config(dir_a)
    cfg_b = load_config(dir_b)
    config_mismatches = compare_configs(cfg_a, cfg_b)

    print(f"[config] checked {len(REQUIRED_CONFIG_FIELDS)} fields — "
          f"{len(config_mismatches)} mismatch(es)")
    for m in config_mismatches:
        print(m)

    # Print matching values for the record
    for field in REQUIRED_CONFIG_FIELDS:
        val = cfg_a.get(field, "<missing>")
        status = "✓" if field not in "".join(config_mismatches) else "✗"
        print(f"  {status} {field}: {val}")

    # 3. Tokenizer comparison
    print("\n[tokenizer] comparing vocabularies and special tokens …")
    tokenizer_mismatches = compare_tokenizers(dir_a, dir_b)
    print(f"[tokenizer] {len(tokenizer_mismatches)} mismatch(es)")
    for m in tokenizer_mismatches:
        print(m)

    # 4. Tensor shape comparison
    print("\n[tensors] comparing tensor names and shapes …")
    tensor_mismatches, total_tensors = compare_tensors(dir_a, dir_b)
    print(f"[tensors] {total_tensors} tensors checked — {len(tensor_mismatches)} mismatch(es)")
    for m in tensor_mismatches[:20]:  # cap output; full count goes in details
        print(m)

    # 5. Verdict
    total_mismatches = (
        len(config_mismatches) + len(tokenizer_mismatches) + len(tensor_mismatches)
    )
    status = "pass" if total_mismatches == 0 else "fail"

    print("\n" + "=" * 60)
    print(f"RESULT: {status.upper()} — {total_mismatches} total mismatch(es)")
    if status == "fail":
        print("Consider trying google/codegemma-1.1-7b-it as Model B.")
    print("=" * 60)

    details = {
        "model_a": model_a,
        "model_b": model_b,
        "config_fields_checked": len(REQUIRED_CONFIG_FIELDS),
        "config_mismatches": len(config_mismatches),
        "config_mismatch_details": config_mismatches,
        "tokenizer_mismatches": len(tokenizer_mismatches),
        "tokenizer_mismatch_details": tokenizer_mismatches,
        "total_tensors": total_tensors,
        "tensor_mismatches": len(tensor_mismatches),
        "tensor_mismatch_details": tensor_mismatches[:20],
        "total_mismatches": total_mismatches,
        # Record the num_hidden_layers value for use in A2 YAML layer_range
        "num_hidden_layers": cfg_a.get("num_hidden_layers"),
    }

    record_check("A1", status, "teamlead", details)
    return details


if __name__ == "__main__":
    run_verification()
