#!/bin/bash
# Build and (re)start the BlendLab container on the Droplet. Run on the Droplet as root:
#   /opt/blendlab/repo/scripts/deploy/deploy.sh [git-ref]      # default: main; e.g. v0.9-backend-complete
# Needs /opt/blendlab/.env (see .env.example) and the repo cloned by setup_droplet.sh.
set -euo pipefail

BASE=/opt/blendlab
REF="${1:-main}"
PORT="${PORT:-80}"

[ -f "$BASE/.env" ] || { echo "Missing $BASE/.env. Copy it over SSH first (never through Git)." >&2; exit 1; }

cd "$BASE/repo"
git fetch --tags origin
git checkout "$REF"
# A branch needs a fast-forward; a tag is already exact.
git rev-parse --verify -q "origin/$REF" >/dev/null && git merge --ff-only "origin/$REF"
echo "Deploying $(git rev-parse --short HEAD) ($REF)"

docker build -f docker/Dockerfile -t blendlab:latest .

docker rm -f blendlab >/dev/null 2>&1 || true
docker run -d --name blendlab --restart unless-stopped \
    --env-file "$BASE/.env" \
    -v "$BASE/models:/app/local_models" \
    -p "$PORT:8000" \
    blendlab:latest

# Wait for the server to answer (the first model download happens later, on first use).
for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
        echo "Up: $(curl -s "http://127.0.0.1:$PORT/health")"
        exit 0
    fi
    sleep 1
done
echo "Server did not become healthy. Logs:" >&2
docker logs --tail 50 blendlab >&2
exit 1
