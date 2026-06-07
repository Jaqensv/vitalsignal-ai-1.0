"""Command-line entry point for deterministic VitalDB intervention analysis."""

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Literal

import pandas as pd

from vitalsignal.io.ai_report import AISummary, generate_ai_summary
from vitalsignal.io.local_report import generate_local_report
from vitalsignal.analysis.pipeline import InterventionAnalysis, analyze_intervention
from vitalsignal.io.report_export import build_markdown_report, build_report_data
from vitalsignal.analysis.scoring import PriorityScore, calculate_priority_score
from vitalsignal.io.vitaldb_loader import load_case


CaseLoader = Callable[[int, int], pd.DataFrame]
ReportFormat = Literal["text", "json", "markdown"]


def run_case_analysis(
    case_id: int,
    interval: int = 2,
    loader: CaseLoader = load_case,
    use_ai: bool = False,
) -> tuple[InterventionAnalysis, PriorityScore, str, AISummary | None]:
    """Load and analyze one VitalDB intervention."""
    raw_frame, analysis, score, report, ai_summary = run_case_analysis_with_frame(
        case_id,
        interval,
        loader,
        use_ai,
    )
    return analysis, score, report, ai_summary


def run_case_analysis_with_frame(
    case_id: int,
    interval: int = 2,
    loader: CaseLoader = load_case,
    use_ai: bool = False,
) -> tuple[pd.DataFrame, InterventionAnalysis, PriorityScore, str, AISummary | None]:
    """Load and analyze one VitalDB intervention while keeping the raw frame."""
    raw_frame = loader(case_id, interval)
    analysis = analyze_intervention(case_id, raw_frame, interval)
    score = calculate_priority_score(analysis)
    local_report = generate_local_report(analysis, score)
    if not use_ai:
        return raw_frame, analysis, score, local_report, None

    ai_summary = generate_ai_summary(
        build_report_data(analysis, score),
        local_summary=local_report,
    )
    return raw_frame, analysis, score, ai_summary.text, ai_summary


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Analyse déterministe d'une intervention VitalDB."
    )
    parser.add_argument("case_id", type=int, help="Identifiant de l'intervention")
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Intervalle d'échantillonnage en secondes (défaut : 2)",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Tenter une synthèse IA optionnelle avec fallback local",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Format de sortie du rapport (défaut : text)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Chemin de fichier où écrire le rapport au lieu de l'afficher",
    )
    return parser


def render_cli_report(
    analysis: InterventionAnalysis,
    score: PriorityScore,
    report_text: str,
    ai_summary: AISummary | None,
    output_format: ReportFormat,
) -> str:
    """Render the analysis result in the requested CLI format."""
    if output_format == "text":
        if ai_summary is not None and not ai_summary.used_ai:
            return f"Synthèse locale utilisée ({ai_summary.fallback_reason}).\n\n{report_text}"
        return report_text

    if output_format == "markdown":
        if ai_summary is None:
            return build_markdown_report(analysis, score)
        return f"# Rapport VitalSignal AI\n\n```\n{report_text}\n```\n"

    data = build_report_data(analysis, score)
    if ai_summary is not None:
        data["ai_summary"] = asdict(ai_summary)
    return json.dumps(data, ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    args = build_parser().parse_args(argv)

    try:
        analysis, score, report, ai_summary = run_case_analysis(
            args.case_id,
            args.interval,
            use_ai=args.ai,
        )
    except (OSError, ValueError) as error:
        print(f"Analyse impossible : {error}")
        return 1

    rendered_report = render_cli_report(
        analysis,
        score,
        report,
        ai_summary,
        args.format,
    )
    if args.output is not None:
        args.output.write_text(rendered_report, encoding="utf-8")
    else:
        print(rendered_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
