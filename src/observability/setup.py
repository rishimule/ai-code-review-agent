"""Initialize Langfuse observability with graceful fallback.

If LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set, Langfuse tracing is
enabled.  Otherwise the agent runs normally with console-only logging.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_enabled = False
_client: Optional["Langfuse"] = None  # type: ignore[name-defined]


def init_langfuse() -> bool:
    """Configure Langfuse from environment variables.

    Returns True if Langfuse is active, False otherwise.
    """
    global _enabled, _client  # noqa: PLW0603

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        logger.info(
            "Langfuse keys not found -- running with console-only observability"
        )
        _enabled = False
        return False

    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        _enabled = True
        logger.info("Langfuse tracing enabled")
        return True
    except Exception as exc:
        logger.warning("Failed to initialise Langfuse: %s", exc)
        _enabled = False
        return False


def is_enabled() -> bool:
    """Return whether Langfuse tracing is currently active."""
    return _enabled


def flush() -> None:
    """Flush any pending Langfuse events.  No-op when disabled."""
    if not _enabled or _client is None:
        return
    try:
        _client.flush()
    except Exception as exc:
        logger.warning("Langfuse flush failed: %s", exc)
