#!/usr/bin/env bash
# src/merge/run_all.sh
# Check A4: Batch runs all merges that haven't been completed yet.

mkdir -p merged

for config_file in configs/merges/*.yaml; do
    # Extract the filename without the path and extension
    name=$(basename "$config_file" .yaml)
    
    # Check if the output folder already exists
    if [ -d "merged/$name" ]; then
        echo "Skipping $name (merged/$name already exists)"
    else
        echo "============================================================"
        echo "Starting merge for $name..."
        echo "============================================================"
        mergekit-yaml "$config_file" "merged/$name" --lazy-unpickle
        echo "Finished $name"
    fi
done

echo "All merges complete!"
