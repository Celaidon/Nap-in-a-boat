#!/usr/bin/env python
"""Smoke test for a running BlendLab server.

    python scripts/smoke_test.py http://localhost:8000
    python scripts/smoke_test.py https://demo.example.com --blends sweep_000,sweep_050,sweep_100 --min-tokens 20

Checks /health, /api/registry and /api/metrics, then generates tokens over /ws on each
blend and prints tokens per second. Exits 0 if everything passed, 1 otherwise.
The last output line is `RESULT {json}`, easy to copy into verification details.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

from websockets.sync.client import connect

PROMPT = "Write a short poem about the sea."


class SmokeFailure(Exception):
    pass


def get_json(base: str, path: str) -> dict:
    try:
        with urllib.request.urlopen(base + path, timeout=15) as response:
            return json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise SmokeFailure(f"GET {path} failed: {exc}") from exc


def check_rest(base: str) -> list[str]:
    health = get_json(base, "/health")
    if health.get("status") != "ok":
        raise SmokeFailure(f"/health says {health}")
    print(f"ok  /health      loaded={health.get('loaded')}")

    registry = get_json(base, "/api/registry")
    blend_ids = [b["id"] for b in registry.get("blends", [])]
    if not blend_ids:
        raise SmokeFailure("/api/registry has no blends")
    print(f"ok  /api/registry {len(blend_ids)} blends")

    metrics = get_json(base, "/api/metrics")
    if not metrics.get("blends"):
        raise SmokeFailure("/api/metrics has no blends")
    print(f"ok  /api/metrics  {len(metrics['blends'])} blends")
    return blend_ids


def generate(base: str, blend_id: str, max_tokens: int, timeout: float) -> dict:
    """Stream one answer over /ws. Returns token count and speeds (server-reported and measured here)."""
    url = base.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
    request_id = uuid.uuid4().hex[:8]
    started = time.monotonic()
    first_token_at = None
    tokens = 0
    with connect(url, open_timeout=30, max_size=None) as ws:
        ws.send(json.dumps({
            "type": "generate", "request_id": request_id, "blend_id": blend_id,
            "prompt": PROMPT, "max_tokens": max_tokens, "temperature": 0.7,
        }))
        while True:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise SmokeFailure(f"{blend_id}: no 'done' within {timeout:.0f}s")
            try:
                message = json.loads(ws.recv(timeout=remaining))
            except TimeoutError:
                raise SmokeFailure(f"{blend_id}: no 'done' within {timeout:.0f}s") from None
            kind = message.get("type")
            if kind == "ping":
                ws.send(json.dumps({"type": "pong"}))
            elif message.get("request_id") != request_id:
                continue
            elif kind == "token":
                tokens += 1
                first_token_at = first_token_at or time.monotonic()
            elif kind == "error":
                raise SmokeFailure(f"{blend_id}: server error {message['code']}: {message['message']}")
            elif kind == "done":
                now = time.monotonic()
                measured = (tokens - 1) / (now - first_token_at) if tokens > 1 and now > first_token_at else 0.0
                return {
                    "blend_id": blend_id,
                    "tokens": message["tokens"],
                    "server_tokens_per_sec": message["tokens_per_sec"],
                    "client_tokens_per_sec": round(measured, 2),
                    "seconds_to_first_token": round(first_token_at - started, 1) if first_token_at else None,
                }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url", help="e.g. http://localhost:8000")
    parser.add_argument("--blends", default="sweep_050", help="comma-separated blend ids to generate on")
    parser.add_argument("--tokens", type=int, default=50, help="max_tokens to request (default 50)")
    parser.add_argument("--min-tokens", type=int, default=1, help="fail if fewer tokens than this arrive")
    parser.add_argument("--timeout", type=float, default=600, help="seconds to wait per blend; first load is slow")
    args = parser.parse_args(argv)
    base = args.base_url.rstrip("/")

    try:
        known = check_rest(base)
        results = []
        for blend_id in [b.strip() for b in args.blends.split(",") if b.strip()]:
            if blend_id not in known:
                raise SmokeFailure(f"{blend_id} is not in the registry ({', '.join(known)})")
            result = generate(base, blend_id, args.tokens, args.timeout)
            if result["tokens"] < args.min_tokens:
                raise SmokeFailure(f"{blend_id}: only {result['tokens']} tokens, wanted at least {args.min_tokens}")
            print(
                f"ok  /ws {blend_id}: {result['tokens']} tokens, {result['server_tokens_per_sec']} tok/s "
                f"(measured {result['client_tokens_per_sec']}), first token after {result['seconds_to_first_token']}s"
            )
            results.append(result)
    except SmokeFailure as exc:
        print(f"FAILED: {exc}")
        return 1

    print("SMOKE TEST PASSED")
    print("RESULT " + json.dumps({"base_url": base, "generations": results}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
