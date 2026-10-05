# BlendLab server image. Models are NOT baked in: they download into the mounted
# volume (/app/local_models) and are checksum-verified by the ModelManager.
# Build from the repo root:  docker build -f docker/Dockerfile -t blendlab:latest .
FROM python:3.11-slim

# libgomp1: the prebuilt llama-cpp-python wheel needs the OpenMP runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home blendlab

WORKDIR /app

# --only-binary: use the prebuilt llama-cpp-python wheel; fail fast instead of compiling for 20 minutes.
COPY requirements/server.txt requirements/server.txt
RUN pip install --no-cache-dir --only-binary=llama-cpp-python -r requirements/server.txt

COPY contracts/ contracts/
COPY src/ src/
COPY web/ web/
COPY models/ models/
COPY results/ results/
COPY docker/entrypoint.sh /entrypoint.sh

# The sed strips Windows line endings in case the script was checked out on Windows.
RUN sed -i 's/\r$//' /entrypoint.sh \
    && chmod +x /entrypoint.sh \
    && mkdir -p /app/local_models \
    && chown blendlab /app/local_models

# Production defaults. They fail fast if the real files are missing; override them
# (see docker/README.md) to run with the mock files.
ENV REGISTRY_PATH=models/registry.json \
    METRICS_PATH=results/metrics.json \
    SCORING_MODULE=src.eval.scoring \
    MODELS_DIR=/app/local_models

USER blendlab
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
ENTRYPOINT ["/entrypoint.sh"]
