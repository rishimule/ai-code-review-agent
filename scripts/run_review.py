"""Run the AI code review agent on a PR and post results as a comment.

Called by the GitHub Actions workflow. Reads PR metadata from environment
variables set by the workflow, runs the LangGraph pipeline, and posts the
formatted review as a PR issue comment.

Exits 0 on success or on handled failure — never blocks the PR.
"""

from __future__ import annotations

import logging
import os
import sys

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


def fetch_pr_diff(diff_url: str, token: str) -> str:
    """Fetch the raw unified diff for a PR."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    response = httpx.get(diff_url, headers=headers, follow_redirects=True, timeout=60)
    response.raise_for_status()
    return response.text


def post_pr_comment(repo: str, pr_number: str, body: str, token: str) -> None:
    """Post a comment on a PR via the Issues API."""
    url = f"{API_BASE}/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    response = httpx.post(url, headers=headers, json={"body": body}, timeout=30)
    response.raise_for_status()
    logger.info("Posted review comment on %s#%s", repo, pr_number)


def main() -> int:
    try:
        token = get_env("GITHUB_TOKEN")
        pr_diff_url = get_env("PR_DIFF_URL")
        pr_number = get_env("PR_NUMBER")
        repo = get_env("REPO_FULL_NAME")
        pr_url = f"https://github.com/{repo}/pull/{pr_number}"

        logger.info("Starting review for %s", pr_url)

        # Fetch the PR diff
        raw_diff = fetch_pr_diff(pr_diff_url, token)
        if not raw_diff.strip():
            logger.info("Empty diff, skipping review")
            return 0

        # Run the LangGraph pipeline
        from src.agent.graph import build_review_graph

        graph = build_review_graph()
        result = graph.invoke({"pr_url": pr_url, "raw_diff": raw_diff})

        review_body = result.get("formatted_review", "")
        if not review_body:
            logger.warning("Pipeline produced no review output")
            return 0

        # Post the review as a PR comment
        post_pr_comment(repo, pr_number, review_body, token)
        logger.info("Review posted successfully")
        return 0

    except Exception:
        logger.exception("Review failed — not blocking PR")
        return 0


if __name__ == "__main__":
    sys.exit(main())
