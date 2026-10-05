# Deploying BlendLab to a DigitalOcean Droplet (check C8)

Needs: a DigitalOcean account, the real models in the private Spaces bucket (Track A), and your `.env`.

## 1. Create the Droplet (DigitalOcean website)

- Ubuntu 24.04, CPU Droplet with **16 GB RAM or more** (each 7B Q4_K_M model is about 5 GB in memory, and 2 stay loaded), 60 GB+ disk for the model cache, a region near your users.
- Add your SSH key.
- Create a **Cloud Firewall**: inbound 22 from **your IP only**, 80 and 443 from anywhere. Attach it to the Droplet.

## 2. One-time setup

```bash
ssh root@<droplet-ip> 'bash -s' < scripts/deploy/setup_droplet.sh
scp .env root@<droplet-ip>:/opt/blendlab/.env      # secrets go over SSH, never through Git
ssh root@<droplet-ip> chmod 600 /opt/blendlab/.env
```

`.env` needs at least `DO_SPACES_KEY`, `DO_SPACES_SECRET`, `DO_SPACES_REGION`, `DO_SPACES_BUCKET`, `MAX_LOADED_MODELS=2`.
Leave `DEV_MODEL_OVERRIDE` empty in production. The image already defaults to `models/registry.json`,
`results/metrics.json` and `src.eval.scoring`, so those files must be in the repo (from S3).

## 3. Deploy (and every later update)

```bash
ssh root@<droplet-ip> /opt/blendlab/repo/scripts/deploy/deploy.sh main      # or a tag, e.g. v0.9-backend-complete
```

It checks out the ref, builds the image, restarts the container with `--restart unless-stopped`, and waits for `/health`.
Models download on first use (about 5 GB each, SHA-256 checked) into `/opt/blendlab/models`.

## 4. Verify and record check C8

From your own machine (the first run is slow because each blend downloads and loads):

```bash
python scripts/record_deploy.py http://<droplet-ip>
```

This runs the smoke test, generates 50 tokens on `sweep_000`, `sweep_050` and `sweep_100`, and writes
`verification/C8.json` with tokens per second. **If any is under about 3 tokens/sec, tell the team now:**
the demo may need a bigger Droplet or a lower `max_tokens`. Commit `verification/C8.json` in the C8 PR.

## 5. Optional HTTPS

Point a domain at the Droplet, install Caddy, run the container on port 8000 (`PORT=8000 deploy.sh`) and use
`scripts/deploy/Caddyfile.example`.

## Remember

- Droplets bill even when powered off. Destroy anything you are not using.
- The Droplet's `git clone` is public read-only; it never holds credentials. Keep `.env` out of Git.
