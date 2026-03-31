"""Export trace data to JSON for the Streamlit dashboard."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_EXPORT_DIR = Path("traces")


def build_trace_record(
    pr_url: str,
    summary: dict[str, Any],
    cost_breakdown: dict[str, float] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serialisable trace record from pipeline results."""
    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "pr_url": pr_url,
        "model_used": summary.get("model_used", ""),
        "tokens_used": summary.get("tokens_used", 0),
        "latency_seconds": summary.get("latency_seconds", 0.0),
        "findings_count": summary.get("stats", {}).get("total", 0),
        "stats": summary.get("stats", {}),
        "cost": cost_breakdown or {},
        "errors": errors or [],
    }


def export_trace(
    record: dict[str, Any],
    output_dir: Path | str = _DEFAULT_EXPORT_DIR,
) -> Path:
    """Write a trace record to a timestamped JSON file.

    Returns the path to the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"trace_{ts}.json"
    filepath = output_dir / filename

    filepath.write_text(json.dumps(record, indent=2, default=str))
    logger.info("Trace exported to %s", filepath)
    return filepath


def load_traces(trace_dir: Path | str = _DEFAULT_EXPORT_DIR) -> list[dict[str, Any]]:
    """Load all trace JSON files from a directory, newest first."""
    trace_dir = Path(trace_dir)
    if not trace_dir.exists():
        return []

    traces = []
    for path in sorted(trace_dir.glob("trace_*.json"), reverse=True):
        try:
            traces.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping corrupt trace %s: %s", path, exc)
    return traces
