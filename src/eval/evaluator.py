"""Evaluation harness for benchmarking the code review agent.

Loads synthetic PR diffs with known bugs, runs the LangGraph pipeline,
and scores the agent's findings against ground-truth annotations.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.agent.graph import build_review_graph
from src.models.findings import Category, Severity

logger = logging.getLogger(__name__)

BENCHMARKS_DIR = Path(__file__).resolve().parents[2] / "benchmarks"
KNOWN_BUGS_DIR = BENCHMARKS_DIR / "known_bugs"
GROUND_TRUTH_PATH = BENCHMARKS_DIR / "ground_truth.json"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    """Result of matching a single agent finding against ground truth."""
    finding: dict[str, Any]
    matched_expected: dict[str, Any] | None = None
    is_true_positive: bool = False


@dataclass
class BenchmarkResult:
    """Evaluation result for a single benchmark diff."""
    diff_name: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    latency_seconds: float = 0.0
    tokens_used: int = 0
    agent_findings: list[dict[str, Any]] = field(default_factory=list)
    matched: list[MatchResult] = field(default_factory=list)
    missed: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class EvalSummary:
    """Aggregated evaluation across all benchmarks."""
    results: list[BenchmarkResult] = field(default_factory=list)
    total_tp: int = 0
    total_fp: int = 0
    total_fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    false_positive_rate: float = 0.0
    per_category: dict[str, dict[str, float]] = field(default_factory=dict)
    total_latency: float = 0.0
    total_tokens: int = 0


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def _finding_matches_expected(
    finding: dict[str, Any], expected: dict[str, Any],
) -> bool:
    """Check if an agent finding corresponds to an expected ground-truth entry.

    Matching criteria:
    - file_path contains the expected file name (handles path prefix differences)
    - line_number falls within [line_min, line_max]
    - category matches
    """
    f_path = finding.get("file_path", "")
    e_file = expected["file"]
    if not (f_path.endswith(e_file) or e_file in f_path):
        return False

    line = finding.get("line_number", -1)
    if not (expected["line_min"] <= line <= expected["line_max"]):
        return False

    f_cat = finding.get("category", "").lower()
    e_cat = expected["category"].lower()
    if f_cat != e_cat:
        return False

    return True


def _evaluate_single(
    diff_name: str,
    diff_text: str,
    expected_findings: list[dict[str, Any]],
    graph: Any,
) -> BenchmarkResult:
    """Run the pipeline on one diff and score against ground truth."""
    result = BenchmarkResult(diff_name=diff_name)

    pr_url = f"https://github.com/benchmark/repo/pull/0"
    start = time.monotonic()
    try:
        pipeline_out = graph.invoke({"pr_url": pr_url, "raw_diff": diff_text})
    except Exception as exc:
        result.errors.append(str(exc))
        result.false_negatives = len(expected_findings)
        result.missed = expected_findings
        return result
    result.latency_seconds = time.monotonic() - start

    summary = pipeline_out.get("summary", {})
    result.tokens_used = summary.get("tokens_used", 0)

    raw_findings = pipeline_out.get("findings", [])
    if not raw_findings and summary:
        # Findings may be nested inside the summary from aggregate node
        nested = summary.get("findings", [])
        if nested:
            raw_findings = nested

    result.agent_findings = raw_findings

    # Greedy matching: each expected finding can match at most one agent finding
    matched_expected_idxs: set[int] = set()
    matched_agent_idxs: set[int] = set()

    for ai, af in enumerate(raw_findings):
        for ei, ef in enumerate(expected_findings):
            if ei in matched_expected_idxs:
                continue
            if _finding_matches_expected(af, ef):
                result.matched.append(MatchResult(
                    finding=af, matched_expected=ef, is_true_positive=True,
                ))
                matched_expected_idxs.add(ei)
                matched_agent_idxs.add(ai)
                break

    result.true_positives = len(matched_expected_idxs)
    result.false_positives = len(raw_findings) - result.true_positives
    result.false_negatives = len(expected_findings) - result.true_positives

    result.missed = [
        ef for i, ef in enumerate(expected_findings)
        if i not in matched_expected_idxs
    ]

    tp, fp = result.true_positives, result.false_positives
    fn = result.false_negatives
    result.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    result.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if result.precision + result.recall > 0:
        result.f1 = 2 * result.precision * result.recall / (result.precision + result.recall)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_ground_truth() -> dict[str, Any]:
    """Load the ground truth JSON file."""
    with open(GROUND_TRUTH_PATH) as f:
        return json.load(f)


def run_evaluation(model_name: str | None = None) -> EvalSummary:
    """Run the full benchmark suite and return aggregated results.

    Args:
        model_name: Optional model override. If provided, sets GROQ_MODEL env
                    var before building the graph. Defaults to the pipeline default.
    """
    if model_name:
        os.environ["GROQ_MODEL"] = model_name

    ground_truth = load_ground_truth()
    graph = build_review_graph()
    summary = EvalSummary()

    category_tp: dict[str, int] = {}
    category_total: dict[str, int] = {}

    for diff_name, entry in sorted(ground_truth.items()):
        diff_path = KNOWN_BUGS_DIR / diff_name
        if not diff_path.exists():
            logger.warning("Missing diff file: %s", diff_path)
            continue

        diff_text = diff_path.read_text()
        expected = entry["expected_findings"]

        logger.info("Evaluating: %s (%d expected findings)", diff_name, len(expected))
        result = _evaluate_single(diff_name, diff_text, expected, graph)
        summary.results.append(result)

        # Per-category tracking
        for ef in expected:
            cat = ef["category"]
            category_total[cat] = category_total.get(cat, 0) + 1

        for m in result.matched:
            if m.is_true_positive and m.matched_expected:
                cat = m.matched_expected["category"]
                category_tp[cat] = category_tp.get(cat, 0) + 1

    # Aggregate
    summary.total_tp = sum(r.true_positives for r in summary.results)
    summary.total_fp = sum(r.false_positives for r in summary.results)
    summary.total_fn = sum(r.false_negatives for r in summary.results)
    summary.total_latency = sum(r.latency_seconds for r in summary.results)
    summary.total_tokens = sum(r.tokens_used for r in summary.results)

    tp, fp, fn = summary.total_tp, summary.total_fp, summary.total_fn
    summary.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    summary.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if summary.precision + summary.recall > 0:
        summary.f1 = (
            2 * summary.precision * summary.recall
            / (summary.precision + summary.recall)
        )
    summary.false_positive_rate = fp / (fp + tp) if (fp + tp) > 0 else 0.0

    for cat in sorted(set(list(category_total.keys()) + list(category_tp.keys()))):
        total = category_total.get(cat, 0)
        detected = category_tp.get(cat, 0)
        summary.per_category[cat] = {
            "total": total,
            "detected": detected,
            "accuracy": detected / total if total > 0 else 0.0,
        }

    return summary


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def summary_to_json(summary: EvalSummary) -> dict[str, Any]:
    """Convert evaluation summary to a JSON-serializable dict."""
    return {
        "aggregate": {
            "precision": round(summary.precision, 4),
            "recall": round(summary.recall, 4),
            "f1": round(summary.f1, 4),
            "false_positive_rate": round(summary.false_positive_rate, 4),
            "true_positives": summary.total_tp,
            "false_positives": summary.total_fp,
            "false_negatives": summary.total_fn,
            "total_latency_seconds": round(summary.total_latency, 2),
            "total_tokens": summary.total_tokens,
        },
        "per_category": {
            cat: {k: round(v, 4) if isinstance(v, float) else v for k, v in vals.items()}
            for cat, vals in summary.per_category.items()
        },
        "per_benchmark": [
            {
                "diff": r.diff_name,
                "tp": r.true_positives,
                "fp": r.false_positives,
                "fn": r.false_negatives,
                "precision": round(r.precision, 4),
                "recall": round(r.recall, 4),
                "f1": round(r.f1, 4),
                "latency_s": round(r.latency_seconds, 2),
                "tokens": r.tokens_used,
                "errors": r.errors,
                "missed": [m.get("label", "") for m in r.missed],
            }
            for r in summary.results
        ],
    }


def format_table(summary: EvalSummary) -> str:
    """Format evaluation results as a readable ASCII table."""
    lines: list[str] = []
    sep = "-" * 95

    lines.append("")
    lines.append("EVALUATION RESULTS")
    lines.append(sep)
    lines.append(
        f"{'Benchmark':<32} {'TP':>4} {'FP':>4} {'FN':>4} "
        f"{'Prec':>6} {'Rec':>6} {'F1':>6} {'Time':>7} {'Tokens':>7}"
    )
    lines.append(sep)

    for r in summary.results:
        name = r.diff_name.replace(".diff", "")
        lines.append(
            f"{name:<32} {r.true_positives:>4} {r.false_positives:>4} "
            f"{r.false_negatives:>4} {r.precision:>6.2f} {r.recall:>6.2f} "
            f"{r.f1:>6.2f} {r.latency_seconds:>6.1f}s {r.tokens_used:>7}"
        )

    lines.append(sep)
    lines.append(
        f"{'TOTAL':<32} {summary.total_tp:>4} {summary.total_fp:>4} "
        f"{summary.total_fn:>4} {summary.precision:>6.2f} {summary.recall:>6.2f} "
        f"{summary.f1:>6.2f} {summary.total_latency:>6.1f}s {summary.total_tokens:>7}"
    )
    lines.append("")

    lines.append("PER-CATEGORY ACCURACY")
    lines.append(sep)
    lines.append(f"{'Category':<16} {'Detected':>10} {'Total':>10} {'Accuracy':>10}")
    lines.append(sep)
    for cat, vals in summary.per_category.items():
        lines.append(
            f"{cat:<16} {vals['detected']:>10} {vals['total']:>10} "
            f"{vals['accuracy']:>9.1%}"
        )
    lines.append(sep)

    # Missed findings
    all_missed = [
        (r.diff_name, m) for r in summary.results for m in r.missed
    ]
    if all_missed:
        lines.append("")
        lines.append("MISSED FINDINGS (False Negatives)")
        lines.append(sep)
        for diff_name, missed in all_missed:
            label = missed.get("label", "unknown")
            lines.append(f"  [{diff_name}] {label}")
        lines.append(sep)

    lines.append(
        f"\nFalse Positive Rate: {summary.false_positive_rate:.1%}"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the evaluation and print results."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    summary = run_evaluation()

    print(format_table(summary))

    out_path = BENCHMARKS_DIR / "eval_results.json"
    with open(out_path, "w") as f:
        json.dump(summary_to_json(summary), f, indent=2)
    logger.info("Results written to %s", out_path)


if __name__ == "__main__":
    main()
