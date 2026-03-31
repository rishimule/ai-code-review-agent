"""Streamlit dashboard for the AI Code Review Agent."""

from __future__ import annotations

import html
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
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS Injection
# ---------------------------------------------------------------------------

_CSS_FONTS_AND_GLOBALS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

:root {
    --bg-primary: #0A0A0F;
    --bg-secondary: #141420;
    --bg-card: #1A1A2E;
    --bg-card-hover: #1E1E35;
    --bg-glass: rgba(26, 26, 46, 0.6);
    --border-subtle: rgba(255, 255, 255, 0.06);
    --border-hover: rgba(255, 255, 255, 0.12);
    --text-primary: #E8E8ED;
    --text-secondary: #8888A0;
    --text-muted: #5A5A72;
    --accent-purple: #6C5CE7;
    --accent-blue: #4DA8FF;
    --accent-green: #00D68F;
    --accent-orange: #FFAA5C;
    --accent-red: #FF6B6B;
    --accent-gradient: linear-gradient(135deg, #6C5CE7 0%, #4DA8FF 100%);
    --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 20px rgba(0, 0, 0, 0.4);
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --transition-fast: 0.15s ease;
    --transition-normal: 0.25s ease;
    --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

html, body, [class*="css"] {
    font-family: var(--font-family) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.14); }

/* Main container */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 4rem;
    max-width: 1100px;
}

/* Hide default Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
</style>
"""

_CSS_STREAMLIT_OVERRIDES = """
<style>
/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
    background: rgba(20, 20, 32, 0.85) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border-right: 1px solid var(--border-subtle) !important;
}

/* ---- Tabs — pill style ---- */
[data-testid="stTabs"] > div:first-child {
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: 4px;
    border: 1px solid var(--border-subtle);
    gap: 4px;
    justify-content: center;
    max-width: 820px;
    margin: 0 auto 36px;
}
[data-testid="stTabs"] button {
    border-radius: var(--radius-md) !important;
    padding: 10px 22px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    color: var(--text-secondary) !important;
    background: transparent !important;
    border: none !important;
    transition: all var(--transition-normal) !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    background: var(--accent-purple) !important;
    color: white !important;
    box-shadow: 0 2px 12px rgba(108, 92, 231, 0.4) !important;
}
[data-testid="stTabs"] button:hover:not([aria-selected="true"]) {
    background: var(--bg-card-hover) !important;
    color: var(--text-primary) !important;
}
/* Hide tab underline indicator */
[data-testid="stTabs"] [role="tablist"] > div:last-child {
    display: none;
}

/* ---- Primary button ---- */
button[data-testid="stBaseButton-primary"] {
    background: var(--accent-gradient) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 10px 32px !important;
    transition: all var(--transition-normal) !important;
    box-shadow: 0 2px 12px rgba(108, 92, 231, 0.3) !important;
}
button[data-testid="stBaseButton-primary"]:hover {
    box-shadow: 0 4px 24px rgba(108, 92, 231, 0.5) !important;
    transform: translateY(-1px) !important;
}

/* ---- Text inputs ---- */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-family) !important;
    transition: border-color var(--transition-fast) !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: var(--accent-purple) !important;
    box-shadow: 0 0 0 3px rgba(108, 92, 231, 0.15) !important;
}

/* ---- Expanders ---- */
[data-testid="stExpander"] {
    background: var(--bg-glass) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-md) !important;
    overflow: hidden;
}
[data-testid="stExpander"] summary span {
    font-weight: 500 !important;
    color: var(--text-secondary) !important;
}

/* ---- Code blocks ---- */
[data-testid="stCode"] pre, pre {
    background: #0D0D14 !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-sm) !important;
}

/* ---- Divider ---- */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent 0%, var(--border-subtle) 20%, var(--border-subtle) 80%, transparent 100%) !important;
    margin: 36px 0 !important;
}

/* ---- Containers (bordered) ---- */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--bg-glass) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-md) !important;
    transition: all var(--transition-normal) !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: var(--border-hover) !important;
}

/* ---- Dataframe container ---- */
[data-testid="stDataFrame"] {
    border-radius: var(--radius-md) !important;
    overflow: hidden;
    border: 1px solid var(--border-subtle) !important;
}

/* ---- Graphviz ---- */
[data-testid="stGraphVizChart"] {
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 24px;
    margin: 16px 0;
}

/* ---- Selectbox ---- */
[data-testid="stSelectbox"] > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-sm) !important;
}

/* ---- Radio ---- */
[data-testid="stRadio"] > div > label {
    color: var(--text-secondary) !important;
}
</style>
"""

_CSS_CUSTOM_CLASSES = """
<style>
/* ---- Hero Section ---- */
.hero-section {
    text-align: center;
    padding: 48px 0 24px;
    max-width: 720px;
    margin: 0 auto;
}
.hero-badge {
    display: inline-block;
    background: var(--accent-gradient);
    color: white;
    font-size: 11px;
    font-weight: 600;
    padding: 6px 18px;
    border-radius: 20px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 24px;
}
.hero-title {
    font-size: 52px;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.08;
    color: var(--text-primary);
    margin: 0 0 20px;
}
.hero-gradient {
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero-subtitle {
    font-size: 17px;
    color: var(--text-secondary);
    line-height: 1.7;
    max-width: 560px;
    margin: 0 auto 28px;
}
.hero-pills {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
}
.hero-pill {
    display: inline-block;
    padding: 6px 16px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 20px;
    font-size: 13px;
    color: var(--text-secondary);
    font-weight: 500;
    transition: border-color var(--transition-fast);
}
.hero-pill:hover {
    border-color: var(--border-hover);
}

/* ---- Section Headers ---- */
.section-header {
    margin: 8px 0 24px;
}
.section-title {
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    margin: 0 0 6px;
    line-height: 1.2;
}
.section-subtitle {
    font-size: 15px;
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 0;
}

/* ---- Metric Cards ---- */
.metric-row {
    display: grid;
    gap: 16px;
    margin: 24px 0;
}
.metric-row-4 { grid-template-columns: repeat(4, 1fr); }
.metric-row-3 { grid-template-columns: repeat(3, 1fr); }
.metric-row-2 { grid-template-columns: repeat(2, 1fr); }
.metric-row-6 { grid-template-columns: repeat(6, 1fr); }

.metric-card {
    background: var(--bg-glass);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 22px 24px;
    position: relative;
    overflow: hidden;
    transition: all var(--transition-normal);
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--card-accent);
    opacity: 0.7;
}
.metric-card:hover {
    border-color: var(--border-hover);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}
.metric-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-muted);
    margin-bottom: 8px;
}
.metric-value {
    font-size: 30px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    line-height: 1.2;
}

@media (max-width: 768px) {
    .metric-row-4, .metric-row-3, .metric-row-6 {
        grid-template-columns: repeat(2, 1fr);
    }
    .hero-title { font-size: 36px; }
}

/* ---- Finding Cards ---- */
.finding-card {
    background: var(--finding-bg);
    border: 1px solid var(--border-subtle);
    border-left: 3px solid var(--finding-accent);
    border-radius: var(--radius-md);
    padding: 20px 24px;
    margin-bottom: 14px;
    transition: all var(--transition-normal);
}
.finding-card:hover {
    border-color: var(--border-hover);
    border-left-color: var(--finding-accent);
    box-shadow: var(--shadow-sm);
}
.finding-header {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}
.finding-severity {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    color: white;
    letter-spacing: 0.05em;
}
.finding-category {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
}
.finding-location {
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    color: var(--text-muted);
    background: var(--bg-card);
    padding: 2px 10px;
    border-radius: 4px;
}
.finding-confidence {
    font-size: 12px;
    color: var(--text-muted);
    margin-left: auto;
}
.finding-message {
    font-size: 15px;
    color: var(--text-primary);
    line-height: 1.7;
    margin: 0;
}
.finding-fix {
    margin-top: 14px;
    padding: 14px 16px;
    background: rgba(0, 214, 143, 0.06);
    border-radius: var(--radius-sm);
    border: 1px solid rgba(0, 214, 143, 0.12);
}
.finding-fix-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--accent-green);
    display: block;
    margin-bottom: 6px;
}
.finding-fix p {
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 0;
}

/* ---- Styled Tables ---- */
.styled-table-wrap {
    overflow-x: auto;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    margin: 16px 0;
}
.styled-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}
.styled-table thead tr {
    background: var(--bg-card);
}
.styled-table th {
    padding: 14px 18px;
    text-align: left;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-subtle);
}
.styled-table td {
    padding: 12px 18px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border-subtle);
}
.styled-table tr:last-child td { border-bottom: none; }
.styled-table tr:hover td { background: rgba(255, 255, 255, 0.02); }
.styled-table td.hl {
    color: var(--text-primary);
    font-weight: 600;
}

/* ---- Info Banners ---- */
.info-banner {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 16px 20px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    margin: 16px 0;
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.6;
}
.info-banner.info {
    background: rgba(77, 168, 255, 0.06);
    border-color: rgba(77, 168, 255, 0.15);
}
.info-banner.warning {
    background: rgba(255, 170, 92, 0.06);
    border-color: rgba(255, 170, 92, 0.15);
}
.info-banner.success {
    background: rgba(0, 214, 143, 0.06);
    border-color: rgba(0, 214, 143, 0.15);
}
.info-banner .banner-icon {
    font-size: 18px;
    flex-shrink: 0;
    margin-top: 1px;
}

/* ---- Caption ---- */
.styled-caption {
    font-size: 13px;
    color: var(--text-muted);
    margin: 12px 0;
    line-height: 1.5;
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS_FONTS_AND_GLOBALS, unsafe_allow_html=True)
    st.markdown(_CSS_STREAMLIT_OVERRIDES, unsafe_allow_html=True)
    st.markdown(_CSS_CUSTOM_CLASSES, unsafe_allow_html=True)


inject_css()

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


SEVERITY_COLORS = {
    "critical": "var(--accent-red)",
    "warning": "var(--accent-orange)",
    "suggestion": "var(--accent-blue)",
}
SEVERITY_BG = {
    "critical": "rgba(255, 107, 107, 0.07)",
    "warning": "rgba(255, 170, 92, 0.07)",
    "suggestion": "rgba(77, 168, 255, 0.07)",
}


def _esc(text: str) -> str:
    return html.escape(str(text)) if text else ""


def render_hero() -> None:
    st.markdown("""
    <div class="hero-section">
        <div class="hero-badge">AI-Powered Code Intelligence</div>
        <h1 class="hero-title">Code Review<br><span class="hero-gradient">Agent</span></h1>
        <p class="hero-subtitle">
            Autonomous AI that reviews Pull Requests, identifies bugs,
            security vulnerabilities, and code quality issues &mdash; then posts
            structured inline comments.
        </p>
        <div class="hero-pills">
            <span class="hero-pill">LangGraph</span>
            <span class="hero-pill">Groq / Llama 3.3 70B</span>
            <span class="hero-pill">Langfuse</span>
            <span class="hero-pill">Pydantic</span>
            <span class="hero-pill">GitHub Actions</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = "") -> None:
    sub_html = f'<p class="section-subtitle">{_esc(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f'<div class="section-header">'
        f'<h2 class="section-title">{_esc(title)}</h2>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, accent: str = "var(--accent-purple)") -> str:
    return (
        f'<div class="metric-card" style="--card-accent: {accent};">'
        f'<div class="metric-label">{_esc(label)}</div>'
        f'<div class="metric-value">{_esc(value)}</div>'
        f'</div>'
    )


def render_metric_row(metrics: list[dict]) -> None:
    n = len(metrics)
    cards = "".join(
        metric_card(m["label"], m["value"], m.get("accent", "var(--accent-purple)"))
        for m in metrics
    )
    st.markdown(
        f'<div class="metric-row metric-row-{n}">{cards}</div>',
        unsafe_allow_html=True,
    )


def render_finding(finding: dict) -> None:
    sev = finding.get("severity", "suggestion")
    cat = finding.get("category", "")
    if isinstance(sev, dict):
        sev = sev.get("value", str(sev))
    if isinstance(cat, dict):
        cat = cat.get("value", str(cat))

    color = SEVERITY_COLORS.get(sev.lower(), "var(--text-muted)")
    bg = SEVERITY_BG.get(sev.lower(), "rgba(255,255,255,0.03)")
    fp = _esc(finding.get("file_path", ""))
    ln = _esc(str(finding.get("line_number", "")))
    conf = finding.get("confidence", 0)
    msg = _esc(finding.get("message", ""))
    fix = finding.get("suggested_fix")

    fix_html = ""
    if fix:
        fix_html = (
            '<div class="finding-fix">'
            '<span class="finding-fix-label">Suggested Fix</span>'
            f'<p>{_esc(fix)}</p>'
            '</div>'
        )

    st.markdown(
        f'<div class="finding-card" style="--finding-accent: {color}; --finding-bg: {bg};">'
        f'<div class="finding-header">'
        f'<span class="finding-severity" style="background:{color};">{_esc(sev.upper())}</span>'
        f'<span class="finding-category">{_esc(cat.title())}</span>'
        f'<span class="finding-location">{fp}:{ln}</span>'
        f'<span class="finding-confidence">{conf:.0%} confidence</span>'
        f'</div>'
        f'<p class="finding-message">{msg}</p>'
        f'{fix_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_styled_table(rows: list[dict], highlight_col: str = "") -> None:
    if not rows:
        return
    headers = list(rows[0].keys())
    thead = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    tbody = ""
    for row in rows:
        cells = ""
        for h in headers:
            cls = ' class="hl"' if h == highlight_col else ""
            cells += f"<td{cls}>{_esc(str(row.get(h, '')))}</td>"
        tbody += f"<tr>{cells}</tr>"

    st.markdown(
        f'<div class="styled-table-wrap">'
        f'<table class="styled-table"><thead><tr>{thead}</tr></thead>'
        f'<tbody>{tbody}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def info_banner(text: str, variant: str = "info") -> None:
    icons = {"info": "\u2139\ufe0f", "warning": "\u26a0\ufe0f", "success": "\u2705"}
    icon = icons.get(variant, "\u2139\ufe0f")
    st.markdown(
        f'<div class="info-banner {variant}">'
        f'<span class="banner-icon">{icon}</span>'
        f'<span>{_esc(text)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def styled_caption(text: str) -> None:
    st.markdown(f'<p class="styled-caption">{_esc(text)}</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar (minimal)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        '<div style="padding:8px 0;">'
        '<div style="font-size:18px;font-weight:700;color:var(--text-primary);margin-bottom:2px;">'
        'AI Code Review Agent</div>'
        '<div style="font-size:13px;color:var(--text-muted);">v1.0</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        "- [GitHub Repository](https://github.com/rishimule/ai-code-review-agent)\n"
        "- [Langfuse Dashboard](https://cloud.langfuse.com)"
    )

    st.divider()

    st.markdown("**Quick Start**")
    st.code("python -m src.agent.main \\\n  --pr-url <URL>", language="bash")

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------

render_hero()

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_demo, tab_bench, tab_compare, tab_obs, tab_arch = st.tabs(
    ["Live Demo", "Benchmarks", "Model Comparison", "Observability", "Architecture"]
)

# ===================================================================
# TAB 1 — Live Demo
# ===================================================================

with tab_demo:
    section_header("Live Demo", "Run the review agent on a GitHub PR or paste a diff directly.")

    mode = st.radio("Input mode", ["GitHub PR URL", "Paste a diff"], horizontal=True)

    pr_url: str | None = None
    diff_text: str | None = None

    if mode == "GitHub PR URL":
        pr_url = st.text_input("PR URL", placeholder="https://github.com/owner/repo/pull/123")
    else:
        diff_text = st.text_area(
            "Paste unified diff", height=250,
            placeholder="diff --git a/file.py b/file.py\n...",
        )

    has_input = bool(pr_url) or bool(diff_text)
    has_key = bool(os.environ.get("GROQ_API_KEY"))

    if not has_key:
        info_banner("Set the GROQ_API_KEY environment variable to enable live reviews.", "info")

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

                render_metric_row([
                    {"label": "Total Issues", "value": str(stats.get("total", 0)), "accent": "var(--accent-purple)"},
                    {"label": "Critical", "value": str(stats.get("critical", 0)), "accent": "var(--accent-red)"},
                    {"label": "Warnings", "value": str(stats.get("warning", 0)), "accent": "var(--accent-orange)"},
                    {"label": "Suggestions", "value": str(stats.get("suggestion", 0)), "accent": "var(--accent-blue)"},
                ])

                styled_caption(
                    f"Model: {summary.get('model_used', 'N/A')} \u00b7 "
                    f"Tokens: {summary.get('tokens_used', 0):,} \u00b7 "
                    f"Latency: {elapsed:.1f}s \u00b7 "
                    f"Est. cost: ${summary.get('cost_estimate', 0):.4f}"
                )

                if findings:
                    for f in findings:
                        render_finding(f)
                else:
                    info_banner("No issues found. The code looks good!", "success")

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
        st.divider()
        section_header("Sample Output", "Example findings the agent produces when reviewing a PR with known vulnerabilities.")

        _samples = [
            {
                "severity": "critical",
                "category": "security",
                "file_path": "app/routes/users.py",
                "line_number": 15,
                "confidence": 0.95,
                "message": "SQL injection vulnerability: user input is directly interpolated into SQL query using f-string.",
                "suggested_fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE name = %s', (name,))",
            },
            {
                "severity": "warning",
                "category": "bug",
                "file_path": "utils/pagination.py",
                "line_number": 17,
                "confidence": 0.85,
                "message": "Off-by-one error: pagination start index uses `page * page_size` but pages are 1-indexed, causing first page to skip initial items.",
                "suggested_fix": "Use (page - 1) * page_size for 1-based page numbering.",
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
    section_header(
        "Benchmark Results",
        "Evaluation against 10 synthetic PR diffs with 30 known bugs spanning security, logic, and code quality categories.",
    )

    eval_data = load_json(RESULTS_PATH) or load_json(EVAL_RESULTS_PATH)

    if eval_data:
        agg = eval_data.get("aggregate", {})

        render_metric_row([
            {"label": "Precision", "value": f"{agg.get('precision', 0):.1%}", "accent": "var(--accent-green)"},
            {"label": "Recall", "value": f"{agg.get('recall', 0):.1%}", "accent": "var(--accent-blue)"},
            {"label": "F1 Score", "value": f"{agg.get('f1', 0):.1%}", "accent": "var(--accent-purple)"},
            {"label": "False Positive Rate", "value": f"{agg.get('false_positive_rate', 0):.1%}", "accent": "var(--accent-orange)"},
        ])

        render_metric_row([
            {"label": "True Positives", "value": str(agg.get("true_positives", 0)), "accent": "var(--accent-green)"},
            {"label": "False Positives", "value": str(agg.get("false_positives", 0)), "accent": "var(--accent-red)"},
            {"label": "False Negatives", "value": str(agg.get("false_negatives", 0)), "accent": "var(--accent-orange)"},
        ])

        st.divider()

        section_header("Per-Category Accuracy")
        per_cat = eval_data.get("per_category", {})
        if per_cat:
            cat_rows = [
                {
                    "Category": c.title(),
                    "Detected": int(v.get("detected", 0)),
                    "Total": int(v.get("total", 0)),
                    "Accuracy": f"{v.get('accuracy', 0):.1%}",
                }
                for c, v in sorted(per_cat.items())
            ]
            render_styled_table(cat_rows, highlight_col="Accuracy")

        section_header("Per-Benchmark Breakdown")
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
                    render_styled_table(all_missed)

        styled_caption(
            f"Total latency: {agg.get('total_latency_seconds', 0):.1f}s \u00b7 "
            f"Total tokens: {agg.get('total_tokens', 0):,}"
        )
    else:
        info_banner("No benchmark results found. Run the evaluation to generate them.", "warning")
        st.code("python -m src.eval.evaluator", language="bash")

        gt = load_json(GROUND_TRUTH_PATH)
        if gt:
            section_header("Available Benchmarks")
            rows = [
                {
                    "Diff": n.replace(".diff", ""),
                    "Description": e.get("description", ""),
                    "Expected Findings": len(e.get("expected_findings", [])),
                }
                for n, e in sorted(gt.items())
            ]
            render_styled_table(rows, highlight_col="Expected Findings")

# ===================================================================
# TAB 3 — Model Comparison
# ===================================================================

with tab_compare:
    section_header(
        "Model Comparison",
        "Side-by-side quality, cost, and latency comparison across LLM models.",
    )

    comparison_data = load_json(MODEL_COMPARISON_PATH)

    if comparison_data:
        rows = []
        for model, data in comparison_data.items():
            a = data.get("aggregate", {})
            rows.append({
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
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

        all_cats: set[str] = set()
        for data in comparison_data.values():
            all_cats.update(data.get("per_category", {}).keys())

        if all_cats:
            section_header("Per-Category Recall by Model")
            cat_rows = []
            for cat in sorted(all_cats):
                row: dict = {"Category": cat.title()}
                for model, data in comparison_data.items():
                    v = data.get("per_category", {}).get(cat, {})
                    row[model] = f"{v.get('accuracy', 0):.1%}"
                cat_rows.append(row)
            render_styled_table(cat_rows, highlight_col="Category")
    else:
        info_banner("No model comparison data available yet.", "info")
        st.code(
            "python -m src.eval.compare_models \\\n"
            "  --models llama-3.3-70b-versatile,llama-3.1-8b-instant",
            language="bash",
        )

        section_header("Available Models & Pricing")
        pricing_rows = [
            {
                "Model": "llama-3.3-70b-versatile",
                "Parameters": "70B",
                "Input ($/1M)": "$0.59",
                "Output ($/1M)": "$0.79",
                "Quality": "High",
                "Speed": "Fast (Groq)",
            },
            {
                "Model": "llama-3.1-8b-instant",
                "Parameters": "8B",
                "Input ($/1M)": "$0.05",
                "Output ($/1M)": "$0.08",
                "Quality": "Medium",
                "Speed": "Very Fast (Groq)",
            },
        ]
        render_styled_table(pricing_rows, highlight_col="Model")

# ===================================================================
# TAB 4 — Observability
# ===================================================================

with tab_obs:
    section_header(
        "Observability",
        "Trace data from pipeline runs \u2014 latency per step, token usage, and cost.",
    )

    traces: list[dict] = []
    if TRACES_DIR.exists():
        for p in sorted(TRACES_DIR.glob("trace_*.json"), reverse=True):
            try:
                traces.append(json.loads(p.read_text()))
            except (json.JSONDecodeError, OSError):
                pass

    if traces:
        section_header(f"Recent Traces ({len(traces)})")

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

        render_metric_row([
            {"label": "Total Tokens", "value": f"{trace.get('tokens_used', 0):,}", "accent": "var(--accent-purple)"},
            {"label": "Latency", "value": f"{trace.get('latency_seconds', 0):.1f}s", "accent": "var(--accent-blue)"},
            {"label": "Findings", "value": str(trace.get("findings_count", 0)), "accent": "var(--accent-orange)"},
            {"label": "Est. Cost", "value": f"${trace.get('cost', {}).get('estimated_cost_usd', 0):.6f}", "accent": "var(--accent-green)"},
        ])

        cost = trace.get("cost", {})
        if cost:
            section_header("Token Breakdown")
            render_metric_row([
                {"label": "Prompt Tokens", "value": f"{int(cost.get('prompt_tokens', 0)):,}", "accent": "var(--accent-blue)"},
                {"label": "Completion Tokens", "value": f"{int(cost.get('completion_tokens', 0)):,}", "accent": "var(--accent-purple)"},
                {"label": "Total Tokens", "value": f"{int(cost.get('total_tokens', 0)):,}", "accent": "var(--accent-green)"},
            ])

        stats = trace.get("stats", {})
        if stats:
            section_header("Finding Distribution")
            stat_metrics = [
                {"label": k.title(), "value": str(v), "accent": "var(--accent-purple)"}
                for k, v in list(stats.items())[:6]
            ]
            render_metric_row(stat_metrics)

        errors = trace.get("errors", [])
        if errors:
            with st.expander("Errors"):
                for err in errors:
                    st.error(err)

        with st.expander("Raw Trace JSON"):
            st.json(trace)
    else:
        info_banner("No trace data found. Run a review with --export-trace to generate traces.", "info")
        st.code("python -m src.agent.main --pr-url <URL> --export-trace", language="bash")

        section_header("Sample Trace", "This is what a trace record looks like.")

        _sample_trace = {
            "timestamp": "2026-03-31T12:00:00+00:00",
            "pr_url": "https://github.com/owner/repo/pull/42",
            "model_used": "llama-3.3-70b-versatile",
            "tokens_used": 8500,
            "latency_seconds": 12.3,
            "findings_count": 5,
            "stats": {
                "total": 5, "critical": 2, "warning": 2, "suggestion": 1,
                "security": 3, "bug": 1, "style": 1,
            },
            "cost": {
                "model": "llama-3.3-70b-versatile",
                "prompt_tokens": 6200, "completion_tokens": 2300,
                "total_tokens": 8500, "estimated_cost_usd": 0.005477,
            },
            "errors": [],
        }

        render_metric_row([
            {"label": "Total Tokens", "value": f"{_sample_trace['tokens_used']:,}", "accent": "var(--accent-purple)"},
            {"label": "Latency", "value": f"{_sample_trace['latency_seconds']:.1f}s", "accent": "var(--accent-blue)"},
            {"label": "Findings", "value": str(_sample_trace["findings_count"]), "accent": "var(--accent-orange)"},
            {"label": "Est. Cost", "value": f"${_sample_trace['cost']['estimated_cost_usd']:.6f}", "accent": "var(--accent-green)"},
        ])

        with st.expander("Sample JSON"):
            st.json(_sample_trace)

# ===================================================================
# TAB 5 — Architecture
# ===================================================================

with tab_arch:
    section_header(
        "Architecture",
        "The review pipeline is a 5-node LangGraph StateGraph with linear flow.",
    )

    section_header("Pipeline Flow")
    st.graphviz_chart(
        """
        digraph {
            rankdir=LR
            bgcolor="transparent"
            node [shape=box, style="rounded,filled", fontname="Inter, Helvetica", fontsize=11,
                  margin="0.35,0.2", penwidth=0]
            edge [color="#3A3A55", penwidth=1.5, arrowsize=0.8]

            parse_diff [label="1. parse_diff\\nSplit unified diff\\ninto per-file chunks",
                        fillcolor="#162016", fontcolor="#00D68F"]
            filter_files [label="2. filter_files\\nRemove non-code files\\n(.lock, .md, .json, ...)",
                          fillcolor="#161625", fontcolor="#4DA8FF"]
            analyze_files [label="3. analyze_files\\nLLM analysis per file\\n(Groq / Llama 3.3 70B)",
                           fillcolor="#251616", fontcolor="#FFAA5C"]
            aggregate [label="4. aggregate\\nCombine findings into\\nReviewSummary",
                       fillcolor="#1a162e", fontcolor="#6C5CE7"]
            format_review [label="5. format_review\\nGenerate markdown\\nwith severity icons",
                           fillcolor="#251616", fontcolor="#FF6B6B"]

            parse_diff -> filter_files -> analyze_files -> aggregate -> format_review
        }
        """,
        use_container_width=True,
    )

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

    section_header("Node Details")

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
            "(critical \u2192 warning \u2192 suggestion), with confidence scores and suggested fixes.",
        ),
    ]

    for name, desc in _nodes:
        with st.container(border=True):
            st.markdown(f"**{name}**")
            st.markdown(desc)

    st.divider()

    section_header("Pipeline State")
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

    section_header("Key Design Decisions")
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
