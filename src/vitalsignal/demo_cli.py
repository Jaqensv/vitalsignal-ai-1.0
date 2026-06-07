"""Compatibility wrapper for the local demo command."""

from vitalsignal.app.demo_cli import *  # noqa: F403
from vitalsignal.app.demo_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
