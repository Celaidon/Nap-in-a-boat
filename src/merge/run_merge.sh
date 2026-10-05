#!/usr/bin/env bash
# src/merge/run_merge.sh
# Check A2: Run the 50/50 merge

echo "Starting SLERP merge for sweep_050..."
mergekit-yaml configs/merges/sweep_050.yaml merged/sweep_050 --lazy-unpickle
echo "Merge complete! Output saved to merged/sweep_050"
