"""Application entrypoint."""

from __future__ import annotations

import logging
import sys
from uuid import uuid4

from praktikum_app.infrastructure.logging_config import configure_logging
from praktikum_app.presentation.qt.app import run

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Run the desktop application."""
    configure_logging()
    try:
        return run(sys.argv)
    except Exception:
        correlation_id = str(uuid4())
        LOGGER.exception(
            "event=app_start_failed correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )
        print(f"Не удалось запустить приложение. correlation_id={correlation_id}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
