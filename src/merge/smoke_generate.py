# src/merge/smoke_generate.py
# Check A2/A4: Test merged models by generating greedy answers for 5 fixed prompts.

import pathlib
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from contracts.record_check import record_check

PROMPTS = [
    # 2 Coding Prompts
    "Write a Python function to reverse a linked list.",
    "Explain how a SQL LEFT JOIN works with a brief example.",
    # 2 Writing Prompts
    "Write a short, professional email to a client delaying a project deadline by one week.",
    "Describe a futuristic city raining neon lights in exactly two sentences.",
    # 1 General Question
    "What are the three primary colors of light?"
]

def run_smoke_test(model_path: str, output_file: str, check_id: str):
    print(f"Loading {model_path}...")
    
    # We use CPU or CUDA depending on what's available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, 
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True
    ).to(device)

    results = []
    
    for i, prompt_text in enumerate(PROMPTS):
        print(f"\n[{i+1}/5] Prompt: {prompt_text}")
        messages = [{"role": "user", "content": prompt_text}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        
        # Greedy generation (temperature 0), max 200 tokens
        outputs = model.generate(
            **inputs, 
            max_new_tokens=200, 
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )
        
        # Decode only the newly generated tokens
        input_length = inputs.input_ids.shape[1]
        response = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
        
        print(f"Response: {response[:100]}...")
        results.append(f"### Prompt: {prompt_text}\n\n**Response:**\n{response}\n\n---\n")

    # Save to markdown file for team review
    out_path = pathlib.Path("verification") / output_file
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text("\n".join(results), encoding="utf-8")
    print(f"\nSaved samples to {out_path}")
    
    # We leave the status as 'wip' - Team lead must manually judge and run record_check to pass
    record_check(check_id, "wip", "teamlead", {"model": model_path, "samples_file": output_file})
    print(f"Inspect {output_file} and then update {check_id}.json to 'pass' if it looks good!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.merge.smoke_generate <merged_model_dir> <output_md_name> <check_id>")
        sys.exit(1)
    
    run_smoke_test(sys.argv[1], sys.argv[2], sys.argv[3])
