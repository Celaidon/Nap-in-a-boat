# BlendLab

**BlendLab** is an open-source tool that blends two language models with SLERP and lets anyone *see* the trade-off between their skills.

## What it does

Drag a slider from 0 to 1 and the same prompt gives visibly different answers.
- **t = 0** → Model A (`google/gemma-1.1-7b-it`): instruction-tuned, good at writing and conversation.
- **t = 1** → Model B (`google/codegemma-7b-it`): instruction-tuned code model built from the same Gemma 7B base.
- Values in between are SLERP-blended checkpoints, quantized to GGUF Q4_K_M and served live.

A capability curve plots coding pass rate vs. writing style score across all eight blend points. The Best Blend Finder lets you paste up to three of your own tasks and get a personalised recommendation.

## Model Terms

Both models are covered by [Google's Gemma Terms of Use](https://ai.google.dev/gemma/terms). Each team member must accept the terms on the model's Hugging Face page before downloading. Merged/quantized derivatives carry the same terms. GGUF files are stored in a **private** bucket and are not publicly redistributed. See [NOTICE](NOTICE) for dataset credits.

## Setup

> Full setup guide coming in Phase 4. For now, copy `.env.example` to `.env` and fill in your keys.

```bash
git clone https://github.com/<team-lead-username>/blendlab.git
cd blendlab
cp .env.example .env
python3.11 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## Tracks

| Track | Owner | Focus |
|---|---|---|
| A: Models & Merging | Team lead | Pair verification, SLERP merges, GGUF conversion, registry |
| B: Evaluation | Muskan | Coding + style harness, judge, capability curve |
| C: Backend & Infra | Sharva | FastAPI server, WebSocket, Docker, CI, deployment |

## License

Our code is released under the [Apache-2.0 License](LICENSE).
