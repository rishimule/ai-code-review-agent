"""CLI entry point for the AI Code Review Agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv

from src.agent.graph import build_review_graph
from src.github_client.client import GitHubClient
from src.observability.cost import estimate_review_cost
from src.observability.export import build_trace_record, export_trace
from src.observability.setup import flush as flush_langfuse
from src.observability.setup import init_langfuse

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AI Code Review Agent - analyze a GitHub PR",
    )
    parser.add_argument(
        "--pr-url",
        required=True,
        help="GitHub pull request URL to review",
    )
    parser.add_argument(
        "--post-comments",
        action="store_true",
        default=False,
        help="Post review comments back to GitHub",
    )
    parser.add_argument(
        "--export-trace",
        action="store_true",
        default=False,
        help="Export trace data to JSON for the dashboard",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser.parse_args()


async def run(pr_url: str, post_comments: bool, export: bool) -> None:
    """Run the review pipeline on a pull request.

    Args:
        pr_url: Full GitHub pull request URL.
        post_comments: Whether to post results back to GitHub.
        export: Whether to export trace data to JSON.
    """
    client = GitHubClient()
    raw_diff = await client.get_pr_diff(pr_url)

    graph = build_review_graph()
    result = graph.invoke({"pr_url": pr_url, "raw_diff": raw_diff})

    logger.info("Review complete")
    sys.stdout.write(result["formatted_review"])

    if export:
        summary = result.get("summary", {})
        cost_breakdown = summary.get("cost_breakdown") or estimate_review_cost(
            summary.get("model_used", "llama-3.3-70b-versatile"),
            summary.get("prompt_tokens", 0),
            summary.get("completion_tokens", 0),
        )
        record = build_trace_record(
            pr_url=pr_url,
            summary=summary,
            cost_breakdown=cost_breakdown,
            errors=result.get("errors", []),
        )
        path = export_trace(record)
        logger.info("Trace exported to %s", path)

    if post_comments:
        logger.info("Posting comments to GitHub is not yet implemented")

    flush_langfuse()


def main() -> None:
    """Main entry point."""
    load_dotenv()
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    init_langfuse()
    asyncio.run(run(args.pr_url, args.post_comments, args.export_trace))


if __name__ == "__main__":
    main()
