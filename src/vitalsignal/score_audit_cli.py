"""Compatibility wrapper for the score audit command-line entry point."""

from vitalsignal.app.score_audit_command import *  # noqa: F403
from vitalsignal.app.score_audit_command import main


if __name__ == "__main__":
    raise SystemExit(main())
