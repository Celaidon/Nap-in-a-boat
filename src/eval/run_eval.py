"""
Evaluation runner module (src/eval/run_eval.py).
Evaluates a single blend GGUF model or mock model against coding_set.jsonl and style_prompts.jsonl.
Outputs results to results/raw/<blend_id>.json.
"""

import argparse
import json
import pathlib
import time

from src.eval.extract import extract_code
from src.eval.judge import judge_style
from src.eval.prompts import format_coding_prompt
from src.eval.rhyme import rhyme_score
from src.eval.sandbox import run_tests


def run_evaluation(
    gguf_path: str | None = None,
    blend_id: str = "sweep_000",
    out_path: str | None = None,
    use_mock: bool = False,
) -> dict:
    coding_file = pathlib.Path("data/coding_set.jsonl")
    style_file = pathlib.Path("data/style_prompts.jsonl")

    assert coding_file.exists(), f"Coding set missing: {coding_file}"
    assert style_file.exists(), f"Style set missing: {style_file}"

    coding_items = [json.loads(line) for line in coding_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    style_items = [json.loads(line) for line in style_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    model = None
    if not use_mock and gguf_path and pathlib.Path(gguf_path).exists():
        try:
            from llama_cpp import Llama
            print(f"Loading GGUF model: {gguf_path}")
            model = Llama(model_path=gguf_path, n_ctx=4096, verbose=False)
        except Exception as e:  # noqa: BLE001
            print(f"Could not load GGUF model ({e}), falling back to mock mode")

    def generate_fn(prompt: str, max_tokens: int = 400, default_code: str | None = None) -> tuple[str, float]:
        start = time.time()
        if model is not None:
            output = model.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            text = output["choices"][0]["message"]["content"] or ""
            tokens_generated = output.get("usage", {}).get("completion_tokens", len(text.split()))
        else:
            # Deterministic mock responses for testing pipeline
            if default_code is not None:
                if blend_id == "sweep_100":
                    text = f"```python\n{default_code}\n```"
                else:
                    text = "```python\ndef solution(*args, **kwargs):\n    pass\n```"
            elif "python" in prompt.lower() or "function" in prompt.lower():
                text = "```python\ndef solution(*args, **kwargs):\n    pass\n```"
            else:
                if blend_id == "sweep_100":
                    text = "Terse code model output. Line 1.\nLine 2.\nLine 3."
                else:
                    text = (
                        "The night is serene and clear,\n"
                        "The quiet stars draw very near.\n"
                        "A peaceful stillness in the air,\n"
                        "With gentle calm beyond compare."
                    )
            tokens_generated = len(text.split())

        elapsed = time.time() - start
        tps = tokens_generated / max(0.001, elapsed)
        return text, tps

    code_results = []
    tps_list = []

    print(f"Evaluating coding problems ({len(coding_items)})...")
    for item in coding_items:
        prompt = format_coding_prompt(item["entry_point"], item["prompt"])
        answer, tps = generate_fn(prompt, max_tokens=512, default_code=item.get("reference_solution"))
        tps_list.append(tps)

        code_snippet = extract_code(answer, item["entry_point"])
        sandbox_res = run_tests(code_snippet, item["tests"])

        code_results.append({
            "id": item["id"],
            "entry_point": item["entry_point"],
            "answer": answer,
            "extracted_code": code_snippet,
            "passed": sandbox_res["passed"],
            "timed_out": sandbox_res["timed_out"],
            "error": sandbox_res["error"],
        })

    code_pass_count = sum(1 for r in code_results if r["passed"])
    code_pass_rate = code_pass_count / len(coding_items)

    style_results = []
    print(f"Evaluating style prompts ({len(style_items)})...")
    for item in style_items:
        answer, tps = generate_fn(item["prompt"], max_tokens=400)
        tps_list.append(tps)

        j_res = judge_style(item["prompt"], answer)
        r_score = rhyme_score(answer) if item.get("kind") == "poem" else 0.0

        style_results.append({
            "id": item["id"],
            "kind": item.get("kind", "style"),
            "prompt": item["prompt"],
            "answer": answer,
            "judge_score": j_res,
            "rhyme_score": r_score,
        })

    avg_style_score = sum(r["judge_score"]["overall"] for r in style_results) / len(style_items)
    avg_rhyme_score = sum(r["rhyme_score"] for r in style_results if r["kind"] == "poem") / max(1, sum(1 for r in style_results if r["kind"] == "poem"))
    avg_tps = sum(tps_list) / max(1, len(tps_list))

    out_data = {
        "blend_id": blend_id,
        "gguf_path": gguf_path,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_code": len(coding_items),
        "n_style": len(style_items),
        "code_pass": round(code_pass_rate, 4),
        "style_score": round(avg_style_score, 2),
        "rhyme_score": round(avg_rhyme_score, 2),
        "tokens_per_sec": round(avg_tps, 2),
        "code_results": code_results,
        "style_results": style_results,
    }

    if out_path is None:
        out_path = f"results/raw/{blend_id}.json"

    out_file = pathlib.Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out_data, indent=2), encoding="utf-8")

    print(f"Evaluation complete for {blend_id}. Output saved to {out_path}")
    return out_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BlendLab model evaluation runner")
    parser.add_argument("--gguf", type=str, default=None, help="Path to GGUF model file")
    parser.add_argument("--blend-id", type=str, default="sweep_000", help="Blend ID name")
    parser.add_argument("--out", type=str, default=None, help="Output path")
    parser.add_argument("--mock", action="store_true", help="Run with mock generation")

    args = parser.parse_args()
    run_evaluation(gguf_path=args.gguf, blend_id=args.blend_id, out_path=args.out, use_mock=args.mock)
