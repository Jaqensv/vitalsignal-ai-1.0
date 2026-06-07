"""Command-line entry point for deterministic multi-intervention search."""

import argparse
import csv
import json
from dataclasses import dataclass, asdict
from io import StringIO
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from vitalsignal.analysis.case_search import (
    AnomalyFilter,
    SearchResult,
    search_interventions,
)


SearchOutputFormat = Literal["text", "json", "csv"]
DEFAULT_MAX_CASES = 50


@dataclass(frozen=True)
class SearchSummary:
    """Metadata describing one deterministic multi-case search."""

    start_case_id: int
    end_case_id: int
    scanned_cases: int
    matched_cases: int
    anomaly_filter: str
    interval_seconds: int


def build_parser() -> argparse.ArgumentParser:
    """Build the search command parser."""
    parser = argparse.ArgumentParser(
        description="Recherche déterministe d'interventions VitalDB par anomalie."
    )
    parser.add_argument(
        "--start-case-id",
        type=int,
        required=True,
        help="Premier case_id à scanner",
    )
    parser.add_argument(
        "--end-case-id",
        type=int,
        required=True,
        help="Dernier case_id à scanner, inclus",
    )
    parser.add_argument(
        "--anomaly",
        choices=[
            "any",
            "hypotension",
            "hypertension",
            "desaturation",
            "tachycardia",
            "bradycardia",
            "low_etco2",
            "high_etco2",
        ],
        default="any",
        help="Type d'anomalie à rechercher",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Intervalle d'échantillonnage en secondes (défaut : 2)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "csv"],
        default="text",
        help="Format de sortie des résultats (défaut : text)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Chemin de fichier où écrire les résultats au lieu de les afficher",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=DEFAULT_MAX_CASES,
        help=(
            "Nombre maximal de case_id à scanner pour éviter un scan involontaire "
            f"trop large (défaut : {DEFAULT_MAX_CASES})"
        ),
    )
    return parser


def render_search_results(
    results: list[SearchResult],
    output_format: SearchOutputFormat = "text",
    summary: SearchSummary | None = None,
) -> str:
    """Render deterministic search results for CLI output."""
    if output_format == "json":
        return json.dumps(
            {
                "summary": asdict(summary) if summary is not None else None,
                "results": [
                    {
                        "case_id": result.case_id,
                        "score": result.score.value,
                        "level": result.score.level,
                        "matched_anomalies": list(result.matched_anomalies),
                    }
                    for result in results
                ]
            },
            ensure_ascii=False,
            indent=2,
        )

    if output_format == "csv":
        buffer = StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["case_id", "score", "level", "matched_anomalies"],
        )
        writer.writeheader()
        writer.writerows(
            {
                "case_id": result.case_id,
                "score": result.score.value,
                "level": result.score.level,
                "matched_anomalies": ",".join(result.matched_anomalies),
            }
            for result in results
        )
        return buffer.getvalue()

    if not results:
        lines = []
        if summary is not None:
            lines.extend(_format_text_summary(summary))
        lines.append("Aucune intervention correspondante.")
        return "\n".join(lines)

    lines = []
    if summary is not None:
        lines.extend(_format_text_summary(summary))
        lines.append("")
    lines.append("intervention | indice | niveau | anomalies")
    lines.extend(
        (
            f"{result.case_id} | {result.score.value}/100 | "
            f"{result.score.level} | {', '.join(result.matched_anomalies)}"
        )
        for result in results
    )
    return "\n".join(lines)


def build_search_summary(
    start_case_id: int,
    end_case_id: int,
    anomaly_filter: str,
    interval_seconds: int,
    matched_cases: int,
) -> SearchSummary:
    """Build metadata for one search run."""
    return SearchSummary(
        start_case_id=start_case_id,
        end_case_id=end_case_id,
        scanned_cases=end_case_id - start_case_id + 1,
        matched_cases=matched_cases,
        anomaly_filter=anomaly_filter,
        interval_seconds=interval_seconds,
    )


def _format_text_summary(summary: SearchSummary) -> list[str]:
    """Format search metadata for text output."""
    return [
        (
            "Recherche : "
            f"interventions {summary.start_case_id} à {summary.end_case_id}, "
            f"{summary.scanned_cases} scanné(s), "
            f"{summary.matched_cases} résultat(s)."
        ),
        (
            f"Filtre : {summary.anomaly_filter}, "
            f"intervalle : {summary.interval_seconds} s."
        ),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the deterministic multi-intervention search."""
    args = build_parser().parse_args(argv)
    if args.start_case_id < 1 or args.end_case_id < args.start_case_id:
        print("Intervalle de case_id invalide.")
        return 1
    if args.max_cases < 1:
        print("max-cases doit être un entier positif.")
        return 1

    case_ids = list(range(args.start_case_id, args.end_case_id + 1))
    if len(case_ids) > args.max_cases:
        print(
            f"Scan refusé : {len(case_ids)} case_id demandés, "
            f"limite actuelle {args.max_cases}. Augmente --max-cases si ce scan "
            "est volontaire."
        )
        return 1

    results = search_interventions(
        case_ids,
        anomaly_filter=args.anomaly,
        interval=args.interval,
    )
    summary = build_search_summary(
        args.start_case_id,
        args.end_case_id,
        args.anomaly,
        args.interval,
        len(results),
    )

    rendered_results = render_search_results(results, args.format, summary)
    if args.output is not None:
        args.output.write_text(rendered_results, encoding="utf-8")
    else:
        print(rendered_results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
