"""Cost tracking based on token usage and model pricing.

Groq's free tier is $0, but we track what the equivalent cost *would* be
at representative per-token rates to demonstrate cost awareness.
"""

from __future__ import annotations

# Pricing per million tokens (USD).  These mirror typical hosted LLM rates
# and are useful for "what would this cost at scale?" reporting.
PRICING: dict[str, dict[str, float]] = {
    "llama-3.3-70b-versatile": {
        "prompt": 0.59,       # per 1M input tokens
        "completion": 0.79,   # per 1M output tokens
    },
    "llama-3.1-8b-instant": {
        "prompt": 0.05,
        "completion": 0.08,
    },
}

_DEFAULT_PRICING = {"prompt": 0.59, "completion": 0.79}


def estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Return the estimated USD cost for a single LLM call."""
    rates = PRICING.get(model, _DEFAULT_PRICING)
    cost = (
        prompt_tokens * rates["prompt"] / 1_000_000
        + completion_tokens * rates["completion"] / 1_000_000
    )
    return round(cost, 8)


def estimate_review_cost(
    model: str,
    total_prompt_tokens: int,
    total_completion_tokens: int,
) -> dict[str, float]:
    """Return a breakdown dict suitable for the review summary."""
    cost = estimate_cost(model, total_prompt_tokens, total_completion_tokens)
    return {
        "model": model,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "estimated_cost_usd": cost,
    }
