"""Compatibility wrapper for the search command-line entry point."""

from vitalsignal.app.search_cli import *  # noqa: F403
from vitalsignal.app.search_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
