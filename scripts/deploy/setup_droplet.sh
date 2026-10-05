#!/bin/bash
# One-time setup of a fresh Ubuntu Droplet (run as root over SSH).
#   ssh root@<droplet-ip> 'bash -s' < scripts/deploy/setup_droplet.sh
# Installs Docker and git, creates the folders deploy.sh expects, and clones the repo.
# It does NOT copy secrets: scp your .env to /opt/blendlab/.env yourself (never through Git).
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Celaidon/Nap-in-a-boat.git}"
BASE=/opt/blendlab

apt-get update
apt-get install -y --no-install-recommends docker.io git curl ca-certificates
systemctl enable --now docker

mkdir -p "$BASE/models"
chown -R 10001 "$BASE/models"   # the container runs as uid 10001 and downloads models here
[ -d "$BASE/repo/.git" ] || git clone "$REPO_URL" "$BASE/repo"

echo "Droplet is ready."
echo "Next: scp .env root@<droplet-ip>:$BASE/.env && chmod 600 $BASE/.env, then run deploy.sh."
