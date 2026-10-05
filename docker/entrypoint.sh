#!/bin/sh
# Container start: check the models folder is usable, then run the server.
set -e

MODELS_DIR="${MODELS_DIR:-/app/local_models}"
mkdir -p "$MODELS_DIR" 2>/dev/null || true
if [ ! -w "$MODELS_DIR" ]; then
    echo "ERROR: $MODELS_DIR is not writable by uid $(id -u)." >&2
    echo "On the host run: sudo chown -R 10001 <the folder you mounted there>" >&2
    exit 1
fi

# One worker on purpose: loaded models live in this process's memory.
exec uvicorn src.server.main:app --host 0.0.0.0 --port "${PORT:-8000}"
