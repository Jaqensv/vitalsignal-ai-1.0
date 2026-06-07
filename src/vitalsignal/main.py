"""Compatibility wrapper for the main command-line entry point."""

from vitalsignal.app.main import *  # noqa: F403
from vitalsignal.app.main import main


if __name__ == "__main__":
    raise SystemExit(main())
