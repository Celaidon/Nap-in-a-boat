# Simulated mode (hosted API instead of merged weights)

For demos while the real merged models are not ready. The UI shows a permanent **Simulated** banner.
The blend slider only picks one of two API models and adds a style instruction. It is NOT the SLERP blend.

Put these in `.env` (never in Git, never in chat):

```
SIM_PROVIDER=groq          # groq | gemini | openrouter  (or set SIM_BASE_URL for any OpenAI-compatible API)
SIM_API_KEY=<your key>
SIM_WRITING_MODEL=<model id from the provider, used for 0-50%>
SIM_CODE_MODEL=<model id, used above 50%; defaults to the writing model>
```

Run (from the repo root), then open http://localhost:8000:

```bash
uvicorn src.server.main:app --port 8000
```

Leave `SIM_PROVIDER` empty for the real models. Free tiers are rate limited: a 429 shows as "busy" in the UI,
and the Best Blend Finder (8 blends x several calls) may hit the limit.
