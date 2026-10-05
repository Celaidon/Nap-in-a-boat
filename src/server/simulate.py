# SIMULATED mode: answers come from a hosted API (Groq, Gemini, OpenRouter...), NOT from merged weights.
# The blend position only changes the model choice and a style instruction. It exists for demos and UI work,
# and the UI always labels it as simulated. Turn it on with SIM_PROVIDER (see Settings).
import asyncio
import json
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from src.server.generate import Cancelled, GenerationError

PRESETS = {  # all three speak the OpenAI chat-completions format
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
}


class ApiSimulator:
    def __init__(self, settings, registry: dict, transport: httpx.BaseTransport | None = None):
        if settings.sim_provider not in PRESETS and not settings.sim_base_url:
            raise ValueError(f"SIM_PROVIDER must be one of {sorted(PRESETS)} or SIM_BASE_URL must be set")
        if not settings.sim_writing_model.strip():
            raise ValueError("SIM_WRITING_MODEL is empty. Set it in .env to a model id from your provider's model list.")
        if not settings.sim_api_key:
            raise ValueError("SIM_API_KEY is empty. Put the key in .env, never in the repo.")
        self.base = (settings.sim_base_url or PRESETS[settings.sim_provider]).rstrip("/")
        self.key = settings.sim_api_key
        self.writing_model = settings.sim_writing_model
        self.code_model = settings.sim_code_model or settings.sim_writing_model
        self.t = {b["id"]: b["t"] for b in registry["blends"]}
        self.transport = transport
        self._slots = asyncio.Semaphore(2)  # free tiers have low rate limits

    def route(self, blend_id: str) -> tuple[str, str]:
        """Which API model answers and the style instruction. This is the whole 'simulation'."""
        t = self.t[blend_id]
        model = self.code_model if t > 0.5 else self.writing_model
        if t == 0:
            style = "You are a creative writing assistant. Prefer expressive prose or verse."
        elif t == 1:
            style = "You are a coding assistant. Answer with clear, correct code and a one-line explanation."
        else:
            style = (f"Answer in a blend of {round((1 - t) * 100)}% expressive writing and {round(t * 100)}% "
                     "precise coding style. Use code only when the task needs it.")
        return model, style

    def _payload(self, blend_id: str, prompt: str, max_tokens: int, temperature: float, stream: bool) -> dict:
        model, style = self.route(blend_id)
        return {"model": model, "stream": stream, "max_tokens": max_tokens, "temperature": temperature,
                "messages": [{"role": "system", "content": style}, {"role": "user", "content": prompt}]}

    def _fail(self, status: int, body: str) -> GenerationError:
        code = "busy" if status == 429 else "internal"
        return GenerationError(code, f"Simulation API error {status}: {body[:160]}")

    async def stream(self, blend_id: str, prompt: str, max_tokens: int, temperature: float,
                     stop_event: threading.Event) -> AsyncIterator[str]:
        headers = {"Authorization": f"Bearer {self.key}"}
        body = self._payload(blend_id, prompt, max_tokens, temperature, True)
        async with self._slots, httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10), transport=self.transport) as client:
            try:
                async with client.stream("POST", f"{self.base}/chat/completions", json=body, headers=headers) as r:
                    if r.status_code != 200:
                        raise self._fail(r.status_code, (await r.aread()).decode(errors="replace"))
                    async for line in r.aiter_lines():
                        if stop_event.is_set():
                            return
                        if not line.startswith("data:") or line.strip() == "data: [DONE]":
                            continue
                        choices = json.loads(line[5:]).get("choices") or [{}]
                        text = (choices[0].get("delta") or {}).get("content")
                        if text:
                            yield text
            except httpx.HTTPError as exc:
                raise GenerationError("internal", f"Simulation API unreachable: {exc}") from exc

    @asynccontextmanager
    async def session(self, blend_id: str, stop_event: threading.Event):
        """For the Best Blend Finder: a blocking generate(prompt) -> str, run in a worker thread."""

        def generate(prompt: str) -> str:
            if stop_event.is_set():
                raise Cancelled
            with httpx.Client(timeout=60, transport=self.transport) as client:
                r = client.post(f"{self.base}/chat/completions", headers={"Authorization": f"Bearer {self.key}"},
                                json=self._payload(blend_id, prompt, 512, 0.0, False))
            if r.status_code != 200:
                raise RuntimeError(self._fail(r.status_code, r.text).message)
            return r.json()["choices"][0]["message"]["content"] or ""

        async with self._slots:
            yield generate
