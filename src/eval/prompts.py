"""
Standard prompt templates for evaluation in Track B.
Keeping templates centralized ensures identical prompts across all blends.
"""

CODING_PROMPT_TEMPLATE = (
    "Write a Python function `{entry_point}`. {prompt}\n"
    "Return only the code in one Python code block."
)


def format_coding_prompt(entry_point: str, prompt: str) -> str:
    """Format prompt for model code generation."""
    return CODING_PROMPT_TEMPLATE.format(entry_point=entry_point, prompt=prompt)
