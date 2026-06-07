"""Run VitalSignal AI on a synthetic local intervention."""

import argparse
from collections.abc import Sequence

import pandas as pd

from vitalsignal.analysis.pipeline import analyze_intervention
from vitalsignal.analysis.scoring import calculate_priority_score
from vitalsignal.io.local_report import generate_local_report
from vitalsignal.io.report_export import build_markdown_report


def build_demo_frame() -> pd.DataFrame:
    """Build a small deterministic frame with known anomalies."""
    return pd.DataFrame(
        {
            "ART_MAP": [75.0, 76.0] * 15 + [60.0] * 30 + [74.0, 75.0] * 15,
            "HR": [82.0, 84.0] * 15 + [126.0] * 20 + [86.0, 88.0] * 20,
            "SpO2": [98.0, 99.0] * 45,
            "EtCO2": [35.0, 36.0] * 45,
        }
    )


def build_demo_report(output_format: str = "text") -> str:
    """Analyze the synthetic frame and return a deterministic report."""
    analysis = analyze_intervention(
        case_id=1,
        raw_frame=build_demo_frame(),
        sample_interval_seconds=2,
    )
    score = calculate_priority_score(analysis)
    if output_format == "markdown":
        return build_markdown_report(analysis, score)
    return generate_local_report(analysis, score)


def build_parser() -> argparse.ArgumentParser:
    """Build the demo command parser."""
    parser = argparse.ArgumentParser(
        description="Démonstration locale sans téléchargement VitalDB."
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown"],
        default="text",
        help="Format de sortie du rapport de démonstration",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local demo command."""
    args = build_parser().parse_args(argv)
    print(build_demo_report(args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
