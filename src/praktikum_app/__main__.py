"""Application entrypoint."""

from __future__ import annotations

import sys

from praktikum_app.presentation.qt.app import run


def main() -> int:
    """Run the desktop application."""
    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
