"""LangGraph node functions for the code review pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import PurePosixPath
from typing import Any, TypedDict

from langchain_groq import ChatGroq
from pydantic import ValidationError

from src.models.findings import ReviewFinding, ReviewSummary, Severity
from src.observability.cost import estimate_cost, estimate_review_cost
from src.prompts.review_prompt import format_review_prompt

logger = logging.getLogger(__name__)

try:
    from langfuse.decorators import langfuse_context, observe
except ImportError:
    langfuse_context = None  # type: ignore[assignment]

    def observe(*args, **kwargs):
        """No-op fallback when langfuse is not installed."""
        if args and callable(args[0]):
            return args[0]

        def decorator(fn):
            return fn

        return decorator


_MODEL_NAME = "llama-3.3-70b-versatile"


def _update_trace(**kwargs: Any) -> None:
    """Safely update the current Langfuse observation; no-op when disabled."""
    if langfuse_context is None:
        return
    try:
        langfuse_context.update_current_observation(**kwargs)
    except Exception:
        pass


SKIP_EXTENSIONS = frozenset({
    ".lock", ".md", ".json", ".yaml", ".yml", ".toml",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".so", ".dll",
})

_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.MULTILINE)


class ReviewState(TypedDict, total=False):
    """State passed through the LangGraph review pipeline."""

    pr_url: str
    raw_diff: str
    file_diffs: list[dict[str, str]]
    filtered_files: list[dict[str, str]]
    findings: list[dict[str, Any]]
    summary: dict[str, Any]
    formatted_review: str
    errors: list[str]


@observe(name="parse_diff")
def parse_diff(state: ReviewState) -> ReviewState:
    """Split a unified diff into per-file chunks."""
    raw_diff = state["raw_diff"]
    file_diffs: list[dict[str, str]] = []

    splits = _DIFF_HEADER_RE.split(raw_diff)
    # splits: [preamble, a_path1, b_path1, chunk1, a_path2, b_path2, chunk2, ...]
    i = 1
    while i + 2 < len(splits):
        b_path = splits[i + 1]
        chunk = splits[i + 2]
        file_diffs.append({"path": b_path, "diff": chunk.strip()})
        i += 3

    logger.info("Parsed %d file diffs", len(file_diffs))
    _update_trace(
        input={"diff_length": len(raw_diff)},
        output={"file_count": len(file_diffs)},
    )
    return {"file_diffs": file_diffs}


@observe(name="filter_files")
def filter_files(state: ReviewState) -> ReviewState:
    """Remove non-code files from the diff set."""
    file_diffs = state["file_diffs"]
    filtered: list[dict[str, str]] = []
    skipped_paths: list[str] = []

    for file_diff in file_diffs:
        ext = PurePosixPath(file_diff["path"]).suffix.lower()
        if ext in SKIP_EXTENSIONS:
            logger.debug("Skipping non-code file: %s", file_diff["path"])
            skipped_paths.append(file_diff["path"])
            continue
        filtered.append(file_diff)

    logger.info(
        "Filtered to %d code files (skipped %d)",
        len(filtered),
        len(skipped_paths),
    )
    _update_trace(
        input={"total_files": len(file_diffs)},
        output={"kept": len(filtered), "skipped": skipped_paths},
    )
    return {"filtered_files": filtered}


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Extract a JSON array from LLM output with fallback strategies."""
    stripped = text.strip()

    # Strategy 1: direct parse
    if stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Strategy 2: extract from markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", stripped, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: find any JSON array in the text
    array_match = re.search(r"\[.*]", stripped, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("No JSON array found in response", text, 0)


@observe(name="analyze_single_file")
def _analyze_single_file(
    llm: ChatGroq, path: str, diff: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Analyze a single file diff with the LLM.

    Returns (validated_findings, token_usage_dict).
    """
    prompt = format_review_prompt(file_diff=diff, file_path=path)
    response = llm.invoke(prompt)
    raw_text = response.content

    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    usage = getattr(response, "usage_metadata", None)
    if usage:
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        total_tokens = usage.get("total_tokens", 0) or (
            prompt_tokens + completion_tokens
        )

    cost = estimate_cost(_MODEL_NAME, prompt_tokens, completion_tokens)

    _update_trace(
        input={"file_path": path, "diff_length": len(diff)},
        output={"raw_response_length": len(raw_text)},
        model=_MODEL_NAME,
        usage={
            "input": prompt_tokens,
            "output": completion_tokens,
            "total": total_tokens,
        },
        metadata={"estimated_cost_usd": cost},
    )

    raw_findings = _extract_json_array(raw_text)

    validated: list[dict[str, Any]] = []
    for item in raw_findings:
        try:
            finding = ReviewFinding.model_validate(item)
            validated.append(finding.model_dump())
        except ValidationError as ve:
            logger.warning("Invalid finding for %s: %s", path, ve)

    token_usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    return validated, token_usage


@observe(name="analyze_files")
def analyze_files(state: ReviewState) -> ReviewState:
    """Send each file diff to Groq for analysis sequentially."""
    filtered_files = state["filtered_files"]
    findings: list[dict[str, Any]] = []
    errors: list[str] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    llm = ChatGroq(
        model=_MODEL_NAME,
        temperature=0,
        api_key=os.environ.get("GROQ_API_KEY"),
    )

    start_time = time.monotonic()

    for idx, file_diff in enumerate(filtered_files):
        path = file_diff["path"]
        diff = file_diff["diff"]
        logger.info("Analyzing file: %s", path)

        try:
            file_findings, token_usage = _analyze_single_file(llm, path, diff)
            findings.extend(file_findings)
            total_prompt_tokens += token_usage["prompt_tokens"]
            total_completion_tokens += token_usage["completion_tokens"]
            logger.info("Found %d issues in %s", len(file_findings), path)
        except json.JSONDecodeError as exc:
            msg = f"Failed to parse LLM JSON for {path}: {exc}"
            logger.warning(msg)
            errors.append(msg)
        except Exception as exc:
            msg = f"Error analyzing {path}: {exc}"
            logger.error(msg)
            errors.append(msg)

        # Rate-limit delay between Groq calls (skip after last file)
        if idx < len(filtered_files) - 1:
            time.sleep(1)

    elapsed = time.monotonic() - start_time
    total_tokens = total_prompt_tokens + total_completion_tokens
    cost_breakdown = estimate_review_cost(
        _MODEL_NAME, total_prompt_tokens, total_completion_tokens,
    )

    logger.info(
        "Analysis complete in %.2fs, %d total tokens (est. $%.6f)",
        elapsed,
        total_tokens,
        cost_breakdown["estimated_cost_usd"],
    )

    _update_trace(
        input={"file_count": len(filtered_files)},
        output={"findings_count": len(findings), "errors": errors},
        model=_MODEL_NAME,
        usage={
            "input": total_prompt_tokens,
            "output": total_completion_tokens,
            "total": total_tokens,
        },
        metadata={"cost_breakdown": cost_breakdown},
    )

    return {
        "findings": findings,
        "summary": {
            "tokens_used": total_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "latency_seconds": elapsed,
            "cost_breakdown": cost_breakdown,
        },
        "errors": errors,
    }


@observe(name="aggregate")
def aggregate(state: ReviewState) -> ReviewState:
    """Combine findings into a ReviewSummary."""
    raw_findings = state["findings"]
    partial = state.get("summary", {})

    all_findings: list[ReviewFinding] = []
    for item in raw_findings:
        all_findings.append(ReviewFinding.model_validate(item))

    stats: dict[str, int] = {}
    for finding in all_findings:
        sev = finding.severity.value
        cat = finding.category.value
        stats[sev] = stats.get(sev, 0) + 1
        stats[cat] = stats.get(cat, 0) + 1
    stats["total"] = len(all_findings)

    cost_breakdown = partial.get("cost_breakdown", {})
    cost_estimate = cost_breakdown.get("estimated_cost_usd", 0.0)

    summary = ReviewSummary(
        findings=all_findings,
        stats=stats,
        model_used=_MODEL_NAME,
        tokens_used=partial.get("tokens_used", 0),
        latency_seconds=partial.get("latency_seconds", 0.0),
        cost_estimate=cost_estimate,
    )

    logger.info("Aggregated %d findings (est. cost $%.6f)", len(all_findings), cost_estimate)
    _update_trace(
        input={"raw_findings_count": len(raw_findings)},
        output={"total": stats.get("total", 0), "cost_estimate": cost_estimate},
    )
    return {"summary": summary.model_dump()}


@observe(name="format_review")
def format_review(state: ReviewState) -> ReviewState:
    """Convert ReviewSummary to GitHub-formatted markdown."""
    summary = ReviewSummary.model_validate(state["summary"])
    lines: list[str] = []

    critical = summary.stats.get("critical", 0)
    warnings = summary.stats.get("warning", 0)
    suggestions = summary.stats.get("suggestion", 0)

    lines.append("## Code Review Summary")
    lines.append("")
    lines.append(
        f"**{summary.stats.get('total', 0)} issues found** "
        f"({critical} critical, {warnings} warnings, {suggestions} suggestions)"
    )
    lines.append("")
    lines.append(
        f"Model: `{summary.model_used}` | "
        f"Tokens: {summary.tokens_used} | "
        f"Time: {summary.latency_seconds:.1f}s | "
        f"Est. cost: ${summary.cost_estimate:.4f}"
    )
    lines.append("")

    severity_order = [Severity.CRITICAL, Severity.WARNING, Severity.SUGGESTION]
    severity_icons = {
        Severity.CRITICAL: "🔴",
        Severity.WARNING: "🟡",
        Severity.SUGGESTION: "🔵",
    }

    for severity in severity_order:
        matching = [f for f in summary.findings if f.severity == severity]
        if not matching:
            continue

        lines.append(
            f"### {severity_icons[severity]} {severity.value.title()} ({len(matching)})"
        )
        lines.append("")

        for finding in matching:
            lines.append(
                f"- **{finding.file_path}:{finding.line_number}** "
                f"[{finding.category.value}] (confidence: {finding.confidence:.0%})"
            )
            lines.append(f"  {finding.message}")
            if finding.suggested_fix:
                lines.append(f"  > **Fix:** {finding.suggested_fix}")
            lines.append("")

    if not summary.findings:
        lines.append("No issues found. The code looks good!")
        lines.append("")

    lines.append("---")
    lines.append(
        "*This review was generated by an automated analysis. Findings may include "
        "false positives. Always verify suggestions against your project context "
        "and requirements before applying changes.*"
    )

    formatted = "\n".join(lines)
    logger.info("Formatted review (%d chars)", len(formatted))
    return {"formatted_review": formatted}
