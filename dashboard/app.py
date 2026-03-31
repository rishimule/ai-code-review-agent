"""Streamlit dashboard for the AI Code Review Agent."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BENCHMARKS_DIR = PROJECT_ROOT / "benchmarks"
TRACES_DIR = PROJECT_ROOT / "traces"
EVAL_RESULTS_PATH = BENCHMARKS_DIR / "eval_results.json"
RESULTS_PATH = BENCHMARKS_DIR / "results.json"
MODEL_COMPARISON_PATH = BENCHMARKS_DIR / "model_comparison.json"
GROUND_TRUTH_PATH = BENCHMARKS_DIR / "ground_truth.json"

st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="\U0001f50d",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


SEVERITY_COLORS = {"critical": "#ff4b4b", "warning": "#ffa500", "suggestion": "#4b8bff"}
SEVERITY_ICONS = {"critical": "\U0001f534", "warning": "\U0001f7e1", "suggestion": "\U0001f535"}
CATEGORY_ICONS = {
    "security": "\U0001f512",
    "bug": "\U0001f41b",
    "performance": "\u26a1",
    "logic": "\U0001f9ee",
    "style": "\U0001f3a8",
}


def sev_icon(s: str) -> str:
    return SEVERITY_ICONS.get(s.lower(), "\u26aa")


def cat_icon(c: str) -> str:
    return CATEGORY_ICONS.get(c.lower(), "\U0001f4cb")


def render_finding(finding: dict) -> None:
    """Render a single finding inside a bordered container."""
    sev = finding.get("severity", "suggestion")
    cat = finding.get("category", "")
    # Handle Pydantic enum serialisation
    if isinstance(sev, dict):
        sev = sev.get("value", str(sev))
    if isinstance(cat, dict):
        cat = cat.get("value", str(cat))

    with st.container(border=True):
        st.markdown(
            f"{sev_icon(sev)} **{sev.upper()}** \u00b7 {cat_icon(cat)} {cat} \u00b7 "
            f"`{finding.get('file_path', '')}:{finding.get('line_number', '')}` \u00b7 "
            f"confidence: {finding.get('confidence', 0):.0%}"
        )
        st.markdown(finding.get("message", ""))
        if finding.get("suggested_fix"):
            st.markdown(f"> **Fix:** {finding['suggested_fix']}")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("\U0001f50d AI Code Review Agent")
    st.caption("Portfolio project demonstrating LLM agent engineering, evaluation methodology, and observability.")

    st.divider()

    st.markdown("**Links**")
    st.markdown(
        "- [GitHub Repository](https://github.com/rishimule/ai-code-review-agent)\n"
        "- [Langfuse Dashboard](https://cloud.langfuse.com)"
    )

    st.divider()

    st.markdown("**Tech Stack**")
    st.markdown(
        "- **LangGraph** \u2014 agent orchestration\n"
        "- **Groq** / Llama 3.3 70B \u2014 LLM\n"
        "- **Langfuse** \u2014 observability\n"
        "- **Pydantic** \u2014 structured output\n"
        "- **GitHub Actions** \u2014 CI/CD trigger"
    )

    st.divider()

    st.markdown("**Quick Start**")
    st.code("python -m src.agent.main \\\n  --pr-url <URL>", language="bash")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("AI Code Review Agent")
st.markdown(
    "An autonomous AI agent that reviews GitHub Pull Requests, identifies **bugs**, "
    "**security vulnerabilities**, and **code quality issues**, then posts structured inline comments. "
    "Built with **LangGraph** + **Groq** (Llama 3.3 70B) + **Langfuse**. "
    "[View on GitHub](https://github.com/rishimule/ai-code-review-agent)"
)

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_demo, tab_bench, tab_compare, tab_obs, tab_arch = st.tabs(
    ["\u25b6 Live Demo", "\U0001f4ca Benchmarks", "\U0001f504 Model Comparison", "\U0001f4e1 Observability", "\U0001f3d7 Architecture"]
)

# ===================================================================
# TAB 1 — Live Demo
# ===================================================================

with tab_demo:
    st.header("Live Demo")
    st.markdown("Run the review agent on a GitHub PR or paste a diff directly.")

    mode = st.radio("Input mode", ["GitHub PR URL", "Paste a diff"], horizontal=True)

    pr_url: str | None = None
    diff_text: str | None = None

    if mode == "GitHub PR URL":
        pr_url = st.text_input("PR URL", placeholder="https://github.com/owner/repo/pull/123")
    else:
        diff_text = st.text_area("Paste unified diff", height=250, placeholder="diff --git a/file.py b/file.py\n...")

    has_input = bool(pr_url) or bool(diff_text)
    has_key = bool(os.environ.get("GROQ_API_KEY"))

    if not has_key:
        st.info("Set the `GROQ_API_KEY` environment variable to enable live reviews.")

    run_clicked = st.button("Run Review", disabled=not has_input or not has_key, type="primary")

    if run_clicked:
        with st.spinner("Running review pipeline\u2026"):
            try:
                from src.agent.graph import build_review_graph

                if pr_url:
                    import asyncio
                    from src.github_client.client import GitHubClient

                    client = GitHubClient()
                    raw_diff = asyncio.run(client.get_pr_diff(pr_url))
                    run_url = pr_url
                else:
                    raw_diff = diff_text
                    run_url = "manual://pasted-diff"

                graph = build_review_graph()
                start = time.monotonic()
                result = graph.invoke({"pr_url": run_url, "raw_diff": raw_diff})
                elapsed = time.monotonic() - start

                summary = result.get("summary", {})
                findings = summary.get("findings", [])
                stats = summary.get("stats", {})

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Issues", stats.get("total", 0))
                c2.metric("Critical", stats.get("critical", 0))
                c3.metric("Warnings", stats.get("warning", 0))
                c4.metric("Suggestions", stats.get("suggestion", 0))

                st.caption(
                    f"Model: `{summary.get('model_used', 'N/A')}` \u00b7 "
                    f"Tokens: {summary.get('tokens_used', 0):,} \u00b7 "
                    f"Latency: {elapsed:.1f}s \u00b7 "
                    f"Est. cost: ${summary.get('cost_estimate', 0):.4f}"
                )

                if findings:
                    for f in findings:
                        render_finding(f)
                else:
                    st.success("No issues found. The code looks good!")

                with st.expander("Raw Markdown Output"):
                    st.markdown(result.get("formatted_review", ""))

                if result.get("errors"):
                    with st.expander("Errors"):
                        for err in result["errors"]:
                            st.error(err)

            except Exception as exc:
                st.error(f"Review failed: {exc}")

    # Sample output when idle
    if not run_clicked:
        st.markdown("---")
        st.subheader("Sample Output")
        st.caption("Example findings the agent produces when reviewing a PR with known vulnerabilities:")

        _samples = [
            {
                "severity": "critical",
                "category": "security",
                "file_path": "app/routes/users.py",
                "line_number": 15,
                "confidence": 0.95,
                "message": "SQL injection vulnerability: user input is directly interpolated into SQL query using f-string.",
                "suggested_fix": "Use parameterized queries: `cursor.execute('SELECT * FROM users WHERE name = %s', (name,))`",
            },
            {
                "severity": "warning",
                "category": "bug",
                "file_path": "utils/pagination.py",
                "line_number": 17,
                "confidence": 0.85,
                "message": "Off-by-one error: pagination start index uses `page * page_size` but pages are 1-indexed, causing first page to skip initial items.",
                "suggested_fix": "Use `(page - 1) * page_size` for 1-based page numbering.",
            },
            {
                "severity": "suggestion",
                "category": "style",
                "file_path": "services/auth.py",
                "line_number": 42,
                "confidence": 0.70,
                "message": "Consider extracting token validation logic into a decorator to reduce duplication across route handlers.",
                "suggested_fix": None,
            },
        ]
        for s in _samples:
            render_finding(s)

# ===================================================================
# TAB 2 — Benchmark Results
# ===================================================================

with tab_bench:
    st.header("Benchmark Results")
    st.markdown(
        "Evaluation against **10 synthetic PR diffs** with **30 known bugs** spanning "
        "security, logic, and code quality categories."
    )

    eval_data = load_json(RESULTS_PATH) or load_json(EVAL_RESULTS_PATH)

    if eval_data:
        agg = eval_data.get("aggregate", {})

        # Headline metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Precision", f"{agg.get('precision', 0):.1%}")
        c2.metric("Recall", f"{agg.get('recall', 0):.1%}")
        c3.metric("F1 Score", f"{agg.get('f1', 0):.1%}")
        c4.metric("False Positive Rate", f"{agg.get('false_positive_rate', 0):.1%}")

        st.divider()

        c1, c2, c3 = st.columns(3)
        c1.metric("True Positives", agg.get("true_positives", 0))
        c2.metric("False Positives", agg.get("false_positives", 0))
        c3.metric("False Negatives", agg.get("false_negatives", 0))

        st.divider()

        # Per-category
        st.subheader("Per-Category Accuracy")
        per_cat = eval_data.get("per_category", {})
        if per_cat:
            cat_rows = [
                {
                    "Category": f"{cat_icon(c)} {c.title()}",
                    "Detected": int(v.get("detected", 0)),
                    "Total": int(v.get("total", 0)),
                    "Accuracy": f"{v.get('accuracy', 0):.1%}",
                }
                for c, v in sorted(per_cat.items())
            ]
            st.dataframe(cat_rows, use_container_width=True, hide_index=True)

        # Per-benchmark table
        st.subheader("Per-Benchmark Breakdown")
        per_bench = eval_data.get("per_benchmark", [])
        if per_bench:
            bench_rows = [
                {
                    "Benchmark": b["diff"].replace(".diff", ""),
                    "TP": b.get("tp", 0),
                    "FP": b.get("fp", 0),
                    "FN": b.get("fn", 0),
                    "Precision": f"{b.get('precision', 0):.2f}",
                    "Recall": f"{b.get('recall', 0):.2f}",
                    "F1": f"{b.get('f1', 0):.2f}",
                    "Latency (s)": b.get("latency_s", 0),
                    "Tokens": b.get("tokens", 0),
                }
                for b in per_bench
            ]
            st.dataframe(bench_rows, use_container_width=True, hide_index=True)

            all_missed = [
                {"Benchmark": b["diff"].replace(".diff", ""), "Missed Finding": lbl}
                for b in per_bench
                for lbl in b.get("missed", [])
                if lbl
            ]
            if all_missed:
                with st.expander(f"Missed Findings ({len(all_missed)})"):
                    st.dataframe(all_missed, use_container_width=True, hide_index=True)

        st.caption(
            f"Total latency: {agg.get('total_latency_seconds', 0):.1f}s \u00b7 "
            f"Total tokens: {agg.get('total_tokens', 0):,}"
        )
    else:
        st.warning("No benchmark results found. Run the evaluation to generate them:")
        st.code("python -m src.eval.evaluator", language="bash")

        gt = load_json(GROUND_TRUTH_PATH)
        if gt:
            st.subheader("Available Benchmarks")
            rows = [
                {
                    "Diff": n.replace(".diff", ""),
                    "Description": e.get("description", ""),
                    "Expected Findings": len(e.get("expected_findings", [])),
                }
                for n, e in sorted(gt.items())
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

# ===================================================================
# TAB 3 — Model Comparison
# ===================================================================

with tab_compare:
    st.header("Model Comparison")
    st.markdown("Side-by-side quality, cost, and latency comparison across LLM models.")

    comparison_data = load_json(MODEL_COMPARISON_PATH)

    if comparison_data:
        rows = []
        for model, data in comparison_data.items():
            a = data.get("aggregate", {})
            rows.append(
                {
                    "Model": model,
                    "Precision": f"{a.get('precision', 0):.2f}",
                    "Recall": f"{a.get('recall', 0):.2f}",
                    "F1": f"{a.get('f1', 0):.2f}",
                    "FPR": f"{a.get('false_positive_rate', 0):.2f}",
                    "TP": a.get("true_positives", 0),
                    "FP": a.get("false_positives", 0),
                    "FN": a.get("false_negatives", 0),
                    "Latency (s)": a.get("total_latency_seconds", 0),
                    "Tokens": a.get("total_tokens", 0),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)

        # Per-category comparison
        all_cats: set[str] = set()
        for data in comparison_data.values():
            all_cats.update(data.get("per_category", {}).keys())

        if all_cats:
            st.subheader("Per-Category Recall by Model")
            cat_rows = []
            for cat in sorted(all_cats):
                row: dict = {"Category": f"{cat_icon(cat)} {cat.title()}"}
                for model, data in comparison_data.items():
                    v = data.get("per_category", {}).get(cat, {})
                    row[model] = f"{v.get('accuracy', 0):.1%}"
                cat_rows.append(row)
            st.dataframe(cat_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No model comparison data available yet.")
        st.code(
            "python -m src.eval.compare_models \\\n"
            "  --models llama-3.3-70b-versatile,llama-3.1-8b-instant",
            language="bash",
        )

        st.subheader("Available Models & Pricing")
        pricing_rows = [
            {
                "Model": "llama-3.3-70b-versatile",
                "Parameters": "70B",
                "Input ($/1M tokens)": "$0.59",
                "Output ($/1M tokens)": "$0.79",
                "Expected Quality": "High",
                "Speed": "Fast (Groq)",
            },
            {
                "Model": "llama-3.1-8b-instant",
                "Parameters": "8B",
                "Input ($/1M tokens)": "$0.05",
                "Output ($/1M tokens)": "$0.08",
                "Expected Quality": "Medium",
                "Speed": "Very Fast (Groq)",
            },
        ]
        st.dataframe(pricing_rows, use_container_width=True, hide_index=True)

# ===================================================================
# TAB 4 — Observability
# ===================================================================

with tab_obs:
    st.header("Observability")
    st.markdown("Trace data from pipeline runs \u2014 latency per step, token usage, and cost.")

    traces: list[dict] = []
    if TRACES_DIR.exists():
        for p in sorted(TRACES_DIR.glob("trace_*.json"), reverse=True):
            try:
                traces.append(json.loads(p.read_text()))
            except (json.JSONDecodeError, OSError):
                pass

    if traces:
        st.subheader(f"Recent Traces ({len(traces)})")

        trace_rows = [
            {
                "Timestamp": t.get("timestamp", "")[:19],
                "PR": t.get("pr_url", "")[-50:],
                "Model": t.get("model_used", ""),
                "Findings": t.get("findings_count", 0),
                "Tokens": t.get("tokens_used", 0),
                "Latency (s)": round(t.get("latency_seconds", 0), 1),
                "Cost ($)": f"${t.get('cost', {}).get('estimated_cost_usd', 0):.6f}",
            }
            for t in traces[:20]
        ]
        st.dataframe(trace_rows, use_container_width=True, hide_index=True)

        # Detail view
        display_traces = traces[:20]
        idx = st.selectbox(
            "Select trace for details",
            range(len(display_traces)),
            format_func=lambda i: (
                f"{display_traces[i].get('timestamp', '')[:19]} \u2014 "
                f"{display_traces[i].get('pr_url', '')[-50:]}"
            ),
        )
        trace = display_traces[idx]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Tokens", f"{trace.get('tokens_used', 0):,}")
        c2.metric("Latency", f"{trace.get('latency_seconds', 0):.1f}s")
        c3.metric("Findings", trace.get("findings_count", 0))
        c4.metric("Est. Cost", f"${trace.get('cost', {}).get('estimated_cost_usd', 0):.6f}")

        cost = trace.get("cost", {})
        if cost:
            st.subheader("Token Breakdown")
            tc1, tc2, tc3 = st.columns(3)
            tc1.metric("Prompt Tokens", f"{int(cost.get('prompt_tokens', 0)):,}")
            tc2.metric("Completion Tokens", f"{int(cost.get('completion_tokens', 0)):,}")
            tc3.metric("Total Tokens", f"{int(cost.get('total_tokens', 0)):,}")

        stats = trace.get("stats", {})
        if stats:
            st.subheader("Finding Distribution")
            scols = st.columns(min(len(stats), 6))
            for col, (k, v) in zip(scols, stats.items()):
                col.metric(k.title(), v)

        errors = trace.get("errors", [])
        if errors:
            with st.expander("Errors"):
                for err in errors:
                    st.error(err)

        with st.expander("Raw Trace JSON"):
            st.json(trace)
    else:
        st.info("No trace data found. Run a review with `--export-trace` to generate traces.")
        st.code("python -m src.agent.main --pr-url <URL> --export-trace", language="bash")

        # Show sample structure so the section isn't empty
        st.subheader("Sample Trace")
        st.caption("This is what a trace record looks like:")

        _sample_trace = {
            "timestamp": "2026-03-31T12:00:00+00:00",
            "pr_url": "https://github.com/owner/repo/pull/42",
            "model_used": "llama-3.3-70b-versatile",
            "tokens_used": 8500,
            "latency_seconds": 12.3,
            "findings_count": 5,
            "stats": {
                "total": 5,
                "critical": 2,
                "warning": 2,
                "suggestion": 1,
                "security": 3,
                "bug": 1,
                "style": 1,
            },
            "cost": {
                "model": "llama-3.3-70b-versatile",
                "prompt_tokens": 6200,
                "completion_tokens": 2300,
                "total_tokens": 8500,
                "estimated_cost_usd": 0.005477,
            },
            "errors": [],
        }

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Tokens", f"{_sample_trace['tokens_used']:,}")
        c2.metric("Latency", f"{_sample_trace['latency_seconds']:.1f}s")
        c3.metric("Findings", _sample_trace["findings_count"])
        c4.metric("Est. Cost", f"${_sample_trace['cost']['estimated_cost_usd']:.6f}")

        with st.expander("Sample JSON"):
            st.json(_sample_trace)

# ===================================================================
# TAB 5 — Architecture
# ===================================================================

with tab_arch:
    st.header("Architecture")
    st.markdown("The review pipeline is a **5-node LangGraph StateGraph** with linear flow.")

    # Graphviz diagram (natively supported by Streamlit)
    st.subheader("Pipeline Flow")
    st.graphviz_chart(
        """
        digraph {
            rankdir=LR
            node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, margin="0.3,0.15"]
            edge [color="#666666"]

            parse_diff [label="1. parse_diff\\nSplit unified diff\\ninto per-file chunks", fillcolor="#4CAF50", fontcolor="white"]
            filter_files [label="2. filter_files\\nRemove non-code files\\n(.lock, .md, .json, ...)", fillcolor="#2196F3", fontcolor="white"]
            analyze_files [label="3. analyze_files\\nLLM analysis per file\\n(Groq / Llama 3.3 70B)", fillcolor="#FF9800", fontcolor="white"]
            aggregate [label="4. aggregate\\nCombine findings into\\nReviewSummary", fillcolor="#9C27B0", fontcolor="white"]
            format_review [label="5. format_review\\nGenerate markdown\\nwith severity icons", fillcolor="#F44336", fontcolor="white"]

            parse_diff -> filter_files -> analyze_files -> aggregate -> format_review
        }
        """,
        use_container_width=True,
    )

    # Mermaid source for portability
    with st.expander("Mermaid Source"):
        st.code(
            "graph LR\n"
            "    A[parse_diff] --> B[filter_files]\n"
            "    B --> C[analyze_files]\n"
            "    C --> D[aggregate]\n"
            "    D --> E[format_review]",
            language="mermaid",
        )

    st.divider()

    # Node details
    st.subheader("Node Details")

    _nodes = [
        (
            "1. parse_diff",
            "Splits a unified diff into per-file chunks using regex. "
            "Each chunk contains the path and diff content for one file.",
        ),
        (
            "2. filter_files",
            "Removes non-code files based on extension (.lock, .md, .json, .yaml, images, binaries) "
            "to focus LLM analysis on meaningful code changes.",
        ),
        (
            "3. analyze_files",
            "Sends each file diff to the Groq API (Llama 3.3 70B, temperature=0) with a structured prompt. "
            "Extracts JSON findings with 3-tier fallback parsing (direct \u2192 markdown fences \u2192 regex). "
            "Includes 1s rate-limit delay between calls. Each call is traced with Langfuse.",
        ),
        (
            "4. aggregate",
            "Combines all per-file findings into a ReviewSummary via Pydantic validation. "
            "Computes severity/category stats and cost estimates.",
        ),
        (
            "5. format_review",
            "Converts the ReviewSummary into GitHub-flavored markdown grouped by severity level "
            "(\U0001f534 critical \u2192 \U0001f7e1 warning \u2192 \U0001f535 suggestion), "
            "with confidence scores and suggested fixes.",
        ),
    ]

    for name, desc in _nodes:
        with st.container(border=True):
            st.markdown(f"**{name}**")
            st.markdown(desc)

    st.divider()

    # State schema
    st.subheader("Pipeline State")
    st.code(
        'class ReviewState(TypedDict, total=False):\n'
        '    pr_url: str                          # Input PR URL\n'
        '    raw_diff: str                        # Raw unified diff\n'
        '    file_diffs: list[dict[str, str]]     # Per-file diff chunks\n'
        '    filtered_files: list[dict[str, str]] # Code-only files\n'
        '    findings: list[dict[str, Any]]       # Raw LLM findings\n'
        '    summary: dict[str, Any]              # Aggregated ReviewSummary\n'
        '    formatted_review: str                # Final markdown output\n'
        '    errors: list[str]                    # Non-fatal errors',
        language="python",
    )

    # Key design decisions
    st.subheader("Key Design Decisions")
    for title, desc in [
        (
            "File-by-file analysis",
            "Each file is analyzed independently, enabling focused prompts and staying within token limits.",
        ),
        (
            "3-tier JSON extraction",
            "Direct parse \u2192 markdown fence extraction \u2192 regex fallback. Handles inconsistent LLM output formats.",
        ),
        (
            "Pydantic validation",
            "Every finding passes through the ReviewFinding model, ensuring consistent structure.",
        ),
        (
            "Langfuse observability",
            "@observe decorators on all nodes trace inputs, outputs, token usage, and cost per step.",
        ),
        (
            "Groq free tier",
            "Llama 3.3 70B via Groq (1000 req/day, 100K tokens/day). Cost tracking shows what it would cost at scale.",
        ),
    ]:
        st.markdown(f"- **{title}:** {desc}")
