"""Logging bootstrap for the application."""

from __future__ import annotations

import logging


def configure_logging() -> None:
    """Configure root logger once for local and CI runs."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
