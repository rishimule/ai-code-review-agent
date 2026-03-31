"""Run the evaluation benchmark against multiple models and compare results.

Produces a side-by-side comparison table showing precision, recall, F1,
latency, and token usage for each model.

Usage:
    python -m src.eval.compare_models [--models model1,model2,...]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from src.eval.evaluator import (
    BENCHMARKS_DIR,
    EvalSummary,
    format_table,
    run_evaluation,
    summary_to_json,
)

logger = logging.getLogger(__name__)

DEFAULT_MODELS = [
    "llama-3.3-70b-versatile",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare code review agent across multiple LLM models",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(DEFAULT_MODELS),
        help="Comma-separated list of Groq model names to benchmark",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(BENCHMARKS_DIR / "model_comparison.json"),
        help="Path to write comparison JSON results",
    )
    return parser.parse_args()


def format_comparison_table(results: dict[str, EvalSummary]) -> str:
    """Format a side-by-side comparison table for multiple models."""
    lines: list[str] = []
    sep = "-" * 90

    lines.append("")
    lines.append("MODEL COMPARISON")
    lines.append(sep)
    lines.append(
        f"{'Model':<35} {'Prec':>6} {'Rec':>6} {'F1':>6} "
        f"{'FPR':>6} {'TP':>4} {'FP':>4} {'FN':>4} {'Time':>7} {'Tokens':>7}"
    )
    lines.append(sep)

    for model, summary in results.items():
        lines.append(
            f"{model:<35} "
            f"{summary.precision:>6.2f} {summary.recall:>6.2f} {summary.f1:>6.2f} "
            f"{summary.false_positive_rate:>6.2f} "
            f"{summary.total_tp:>4} {summary.total_fp:>4} {summary.total_fn:>4} "
            f"{summary.total_latency:>6.1f}s {summary.total_tokens:>7}"
        )

    lines.append(sep)

    # Per-category breakdown for each model
    all_cats = set()
    for summary in results.values():
        all_cats.update(summary.per_category.keys())

    if all_cats:
        lines.append("")
        lines.append("PER-CATEGORY RECALL BY MODEL")
        lines.append(sep)
        header = f"{'Category':<16}"
        for model in results:
            short = model[:25]
            header += f" {short:>25}"
        lines.append(header)
        lines.append(sep)

        for cat in sorted(all_cats):
            row = f"{cat:<16}"
            for summary in results.values():
                vals = summary.per_category.get(cat, {})
                acc = vals.get("accuracy", 0.0)
                row += f" {acc:>24.1%}"
            lines.append(row)
        lines.append(sep)

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    results: dict[str, EvalSummary] = {}
    all_json: dict[str, dict] = {}

    for model in models:
        logger.info("=== Evaluating model: %s ===", model)
        summary = run_evaluation(model_name=model)
        results[model] = summary
        all_json[model] = summary_to_json(summary)

        print(f"\n--- {model} ---")
        print(format_table(summary))

    if len(results) > 1:
        print(format_comparison_table(results))

    out_path = Path(args.output)
    with open(out_path, "w") as f:
        json.dump(all_json, f, indent=2)
    logger.info("Comparison results written to %s", out_path)


if __name__ == "__main__":
    main()
