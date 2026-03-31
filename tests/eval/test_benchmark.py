"""Benchmark tests for the code review agent evaluation harness.

These tests run the full LangGraph pipeline against known-buggy diffs
and assert minimum quality thresholds. They require a valid GROQ_API_KEY.

Run with:
    pytest tests/eval/test_benchmark.py -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.eval.evaluator import (
    GROUND_TRUTH_PATH,
    KNOWN_BUGS_DIR,
    EvalSummary,
    load_ground_truth,
    run_evaluation,
    summary_to_json,
)


# ---------------------------------------------------------------------------
# Skip if no API key (allows CI to skip gracefully)
# ---------------------------------------------------------------------------

requires_groq = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set",
)

# Loose thresholds — tighten as the agent improves
MIN_RECALL = 0.30
MIN_PRECISION = 0.20
MIN_F1 = 0.25
MAX_FALSE_POSITIVE_RATE = 0.70


# ---------------------------------------------------------------------------
# Fixture: run evaluation once and share across tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def eval_summary() -> EvalSummary:
    return run_evaluation()


# ---------------------------------------------------------------------------
# Structural tests (no API key needed)
# ---------------------------------------------------------------------------

class TestBenchmarkStructure:
    """Validate benchmark files are present and well-formed."""

    def test_ground_truth_exists(self):
        assert GROUND_TRUTH_PATH.exists(), "ground_truth.json is missing"

    def test_ground_truth_valid_json(self):
        gt = load_ground_truth()
        assert isinstance(gt, dict)
        assert len(gt) >= 10, f"Expected >= 10 benchmarks, got {len(gt)}"

    def test_all_diff_files_exist(self):
        gt = load_ground_truth()
        for diff_name in gt:
            diff_path = KNOWN_BUGS_DIR / diff_name
            assert diff_path.exists(), f"Missing diff: {diff_name}"

    def test_ground_truth_schema(self):
        gt = load_ground_truth()
        for diff_name, entry in gt.items():
            assert "expected_findings" in entry, f"{diff_name}: missing expected_findings"
            for finding in entry["expected_findings"]:
                assert "file" in finding, f"{diff_name}: finding missing 'file'"
                assert "line_min" in finding, f"{diff_name}: finding missing 'line_min'"
                assert "line_max" in finding, f"{diff_name}: finding missing 'line_max'"
                assert "category" in finding, f"{diff_name}: finding missing 'category'"
                assert "severity" in finding, f"{diff_name}: finding missing 'severity'"
                assert finding["line_min"] <= finding["line_max"]

    def test_diff_files_are_valid_diffs(self):
        gt = load_ground_truth()
        for diff_name in gt:
            diff_path = KNOWN_BUGS_DIR / diff_name
            content = diff_path.read_text()
            assert "diff --git" in content, f"{diff_name}: not a valid diff format"

    def test_categories_are_valid(self):
        valid_categories = {"bug", "security", "performance", "style", "logic"}
        gt = load_ground_truth()
        for diff_name, entry in gt.items():
            for finding in entry["expected_findings"]:
                assert finding["category"] in valid_categories, (
                    f"{diff_name}: invalid category '{finding['category']}'"
                )

    def test_severities_are_valid(self):
        valid_severities = {"critical", "warning", "suggestion"}
        gt = load_ground_truth()
        for diff_name, entry in gt.items():
            for finding in entry["expected_findings"]:
                assert finding["severity"] in valid_severities, (
                    f"{diff_name}: invalid severity '{finding['severity']}'"
                )


# ---------------------------------------------------------------------------
# Agent quality tests (require GROQ_API_KEY)
# ---------------------------------------------------------------------------

@requires_groq
class TestAgentQuality:
    """Run the agent on benchmarks and check quality thresholds."""

    def test_overall_recall(self, eval_summary: EvalSummary):
        assert eval_summary.recall >= MIN_RECALL, (
            f"Recall {eval_summary.recall:.2f} below minimum {MIN_RECALL}"
        )

    def test_overall_precision(self, eval_summary: EvalSummary):
        assert eval_summary.precision >= MIN_PRECISION, (
            f"Precision {eval_summary.precision:.2f} below minimum {MIN_PRECISION}"
        )

    def test_overall_f1(self, eval_summary: EvalSummary):
        assert eval_summary.f1 >= MIN_F1, (
            f"F1 {eval_summary.f1:.2f} below minimum {MIN_F1}"
        )

    def test_false_positive_rate(self, eval_summary: EvalSummary):
        assert eval_summary.false_positive_rate <= MAX_FALSE_POSITIVE_RATE, (
            f"FPR {eval_summary.false_positive_rate:.2f} above max {MAX_FALSE_POSITIVE_RATE}"
        )

    def test_security_category_recall(self, eval_summary: EvalSummary):
        security = eval_summary.per_category.get("security", {})
        accuracy = security.get("accuracy", 0.0)
        assert accuracy >= 0.25, (
            f"Security recall {accuracy:.2f} below minimum 0.25"
        )

    def test_no_benchmark_fully_missed(self, eval_summary: EvalSummary):
        for result in eval_summary.results:
            if not result.errors:
                assert result.true_positives > 0, (
                    f"Agent found zero true positives for {result.diff_name}"
                )

    def test_results_serializable(self, eval_summary: EvalSummary):
        data = summary_to_json(eval_summary)
        serialized = json.dumps(data)
        assert len(serialized) > 0
        roundtrip = json.loads(serialized)
        assert roundtrip["aggregate"]["precision"] == data["aggregate"]["precision"]
