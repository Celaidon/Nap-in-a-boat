# Running the BlendLab server in Docker

Build from the repo root (models are never baked into the image):

```bash
docker build -f docker/Dockerfile -t blendlab:latest .
```

## Try it locally with the mock files and a tiny model

```bash
docker run --rm -p 8000:8000 \
  -e REGISTRY_PATH=contracts/mocks/registry.json \
  -e METRICS_PATH=contracts/mocks/metrics.json \
  -e SCORING_MODULE=contracts.scoring \
  -e DEV_MODEL_OVERRIDE=/app/local_models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  -v "$PWD/local_models:/app/local_models" \
  blendlab:latest
python scripts/smoke_test.py http://localhost:8000
```

Use `-e FAKE_GENERATOR=true` instead of the model lines to stream a fixed sentence (no model needed).

## Production

The image defaults to the real files (`models/registry.json`, `results/metrics.json`, `src.eval.scoring`)
and refuses to start if they are missing. Pass secrets with `--env-file .env`, never inside the image.
The server runs as uid 10001, so the mounted models folder must be writable by it:

```bash
sudo mkdir -p /opt/blendlab/models && sudo chown -R 10001 /opt/blendlab/models
docker run -d --restart unless-stopped --env-file .env \
  -v /opt/blendlab/models:/app/local_models -p 80:8000 blendlab:latest
```
