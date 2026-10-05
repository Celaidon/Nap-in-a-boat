# src/merge/compare_weights.py
# Check A3: Proves the merge pipeline is mathematically correct.
# Compares a merged model vs its original parent tensor-by-tensor.

import pathlib
import sys

import torch
from safetensors import safe_open

from contracts.record_check import record_check


def get_tensor_map(model_dir: pathlib.Path):
    """Returns a dict mapping tensor_name -> shard_path."""
    tmap = {}
    for shard in model_dir.glob("*.safetensors"):
        with safe_open(str(shard), framework="pt") as f:
            for name in f:
                tmap[name] = str(shard)
    return tmap

def compare_models(dir_original: pathlib.Path, dir_merged: pathlib.Path) -> float:
    print(f"Mapping {dir_original.name}...")
    map_orig = get_tensor_map(dir_original)
    
    print(f"Mapping {dir_merged.name}...")
    map_merged = get_tensor_map(dir_merged)
    
    missing = set(map_orig) - set(map_merged)
    if missing:
        raise ValueError(f"Merged model is missing tensors: {list(missing)[:5]}")
        
    max_diff = 0.0
    
    print("Comparing tensors...")
    for i, name in enumerate(map_orig.keys()):
        # We open and close shards repeatedly here, which is fine because 
        # safe_open memory-maps instantly and cleanly.
        with safe_open(map_orig[name], framework="pt") as f_orig, \
             safe_open(map_merged[name], framework="pt") as f_merged:
            
            t_orig = f_orig.get_tensor(name)
            t_merged = f_merged.get_tensor(name)
            
            # Max absolute difference
            diff = torch.max(torch.abs(t_orig - t_merged)).item()
            max_diff = max(max_diff, diff)
                
        if (i + 1) % 50 == 0:
            print(f"  Checked {i + 1} tensors... current max diff = {max_diff:.8f}")
            
    print(f"Finished. Absolute max diff across all weights: {max_diff:.8f}")
    return max_diff

if __name__ == "__main__":
    print("=" * 60)
    print("A3: Endpoint Parity Check")
    print("=" * 60)
    
    # 1. Compare t=0 against Model A
    orig_a = pathlib.Path("hf_cache/models--google--gemma-1.1-7b-it/snapshots/065a528791af6f57f013e8e42b7276992b45ef71")
    merged_a = pathlib.Path("merged/check_t0")
    
    print("\n[Parity Check 1: t=0.0 vs Model A]")
    if not merged_a.exists():
        print(f"Error: {merged_a} not found. Run mergekit first!")
        sys.exit(1)
        
    max_diff_0 = compare_models(orig_a, merged_a)
    
    # 2. Compare t=1 against Model B
    orig_b = pathlib.Path("hf_cache/models--google--codegemma-1.1-7b-it/snapshots/078cdc51070553d1636d645c9a238f3b0914459ad")
    merged_b = pathlib.Path("merged/check_t1")
    
    print("\n[Parity Check 2: t=1.0 vs Model B]")
    if not merged_b.exists():
        print(f"Error: {merged_b} not found. Run mergekit first!")
        sys.exit(1)
        
    max_diff_1 = compare_models(orig_b, merged_b)
    
    # 3. Verdict
    # Small bf16 rounding errors (e.g., 1e-7) are acceptable, but > 1e-5 is a fail.
    TOLERANCE = 1e-5
    status = "pass" if max_diff_0 < TOLERANCE and max_diff_1 < TOLERANCE else "fail"
    
    print("\n" + "=" * 60)
    print(f"RESULT: {status.upper()}")
    print("=" * 60)
    
    record_check("A3", status, "teamlead", {
        "max_diff_t0": max_diff_0,
        "max_diff_t1": max_diff_1,
        "tolerance": TOLERANCE
    })
    
    if status == "pass":
        print("\nSuccess! You can now delete merged/check_t0 and merged/check_t1 to free disk space.")
