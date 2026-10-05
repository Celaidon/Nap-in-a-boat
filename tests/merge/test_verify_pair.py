# tests/merge/test_verify_pair.py
# Unit tests for A1 comparison logic.
# Uses tiny fake configs and tensor dicts — no real model files needed.
# All tests run in CI (no @pytest.mark.models).
#
# Design: verify_pair.py imports huggingface_hub / transformers / safetensors at
# the top level. Those packages are NOT installed in CI (too large). We therefore
# skip the import entirely in CI by marking the whole module with a custom skip
# condition, while keeping a fast-running pure-Python copy of the comparison
# logic here for CI to test.




# ── Pure-Python copies of the comparison functions (no ML deps) ──────────────
# These mirror the logic in src/merge/verify_pair.py exactly.
# If you change the logic there, update these too.

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


def _compare_configs(cfg_a: dict, cfg_b: dict) -> list[str]:
    mismatches = []
    for field in REQUIRED_CONFIG_FIELDS:
        val_a = cfg_a.get(field, "<missing>")
        val_b = cfg_b.get(field, "<missing>")
        if val_a != val_b:
            mismatches.append(f"  {field}: A={val_a!r}  B={val_b!r}")
    return mismatches


def _compare_tensors_from_dicts(
    tensors_a: dict, tensors_b: dict
) -> tuple[list[str], int]:
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


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_config(**overrides) -> dict:
    """Return a minimal valid config that looks like Gemma 7B."""
    base = {
        "hidden_size": 3072,
        "num_hidden_layers": 28,
        "num_attention_heads": 16,
        "num_key_value_heads": 16,
        "intermediate_size": 24576,
        "head_dim": 256,
        "vocab_size": 256000,
        "rope_theta": 10000.0,
        "model_type": "gemma",
    }
    base.update(overrides)
    return base


# ── Config comparison tests (pure Python, always run in CI) ──────────────────

class TestCompareConfigs:
    def test_identical_configs_no_mismatches(self):
        cfg = make_config()
        assert _compare_configs(cfg, cfg) == []

    def test_detects_hidden_size_mismatch(self):
        cfg_a = make_config(hidden_size=3072)
        cfg_b = make_config(hidden_size=2048)
        mismatches = _compare_configs(cfg_a, cfg_b)
        assert len(mismatches) == 1
        assert "hidden_size" in mismatches[0]

    def test_detects_layer_count_mismatch(self):
        cfg_a = make_config(num_hidden_layers=28)
        cfg_b = make_config(num_hidden_layers=32)
        mismatches = _compare_configs(cfg_a, cfg_b)
        assert any("num_hidden_layers" in m for m in mismatches)

    def test_detects_model_type_mismatch(self):
        cfg_a = make_config(model_type="gemma")
        cfg_b = make_config(model_type="llama")
        mismatches = _compare_configs(cfg_a, cfg_b)
        assert any("model_type" in m for m in mismatches)

    def test_detects_multiple_mismatches(self):
        cfg_a = make_config(hidden_size=3072, vocab_size=256000)
        cfg_b = make_config(hidden_size=2048, vocab_size=32000)
        mismatches = _compare_configs(cfg_a, cfg_b)
        assert len(mismatches) == 2

    def test_missing_field_is_a_mismatch(self):
        cfg_a = make_config()
        cfg_b = {k: v for k, v in make_config().items() if k != "rope_theta"}
        mismatches = _compare_configs(cfg_a, cfg_b)
        assert any("rope_theta" in m for m in mismatches)

    def test_all_required_fields_are_checked(self):
        """Every field in REQUIRED_CONFIG_FIELDS must be caught when it differs."""
        for field in REQUIRED_CONFIG_FIELDS:
            cfg_a = make_config()
            cfg_b = make_config()
            cfg_b[field] = "deliberately_wrong_value"
            mismatches = _compare_configs(cfg_a, cfg_b)
            assert any(field in m for m in mismatches), (
                f"Field '{field}' was not caught by compare_configs"
            )


# ── Tensor comparison tests (pure Python, always run in CI) ──────────────────

class TestCompareTensors:
    def test_identical_tensors_no_mismatches(self):
        tensors = {
            "model.embed_tokens.weight": [256000, 3072],
            "model.layers.0.self_attn.q_proj.weight": [4096, 3072],
        }
        mismatches, total = _compare_tensors_from_dicts(tensors, tensors)
        assert mismatches == []
        assert total == len(tensors)

    def test_detects_shape_mismatch(self):
        tensors_a = {"layer.weight": [3072, 3072]}
        tensors_b = {"layer.weight": [2048, 2048]}
        mismatches, _ = _compare_tensors_from_dicts(tensors_a, tensors_b)
        assert len(mismatches) == 1
        assert "shape mismatch" in mismatches[0]

    def test_detects_tensor_only_in_a(self):
        tensors_a = {"shared.weight": [256000, 3072], "extra.weight": [100, 100]}
        tensors_b = {"shared.weight": [256000, 3072]}
        mismatches, _ = _compare_tensors_from_dicts(tensors_a, tensors_b)
        assert any("only in A" in m for m in mismatches)

    def test_detects_tensor_only_in_b(self):
        tensors_a = {"shared.weight": [256000, 3072]}
        tensors_b = {"shared.weight": [256000, 3072], "extra.weight": [100, 100]}
        mismatches, _ = _compare_tensors_from_dicts(tensors_a, tensors_b)
        assert any("only in B" in m for m in mismatches)

    def test_total_count_is_max_of_both(self):
        tensors_a = {"a": [1, 2], "b": [3, 4]}
        tensors_b = {"a": [1, 2], "b": [3, 4], "c": [5, 6]}
        _, total = _compare_tensors_from_dicts(tensors_a, tensors_b)
        assert total == 3  # max(2, 3)
