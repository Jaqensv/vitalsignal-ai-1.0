"""Implementation of the deterministic score audit command."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from vitalsignal.analysis.pipeline import analyze_intervention
from vitalsignal.analysis.score_audit import build_audit_record, summarize_audit
from vitalsignal.analysis.scoring import calculate_priority_score
from vitalsignal.io.vitaldb_loader import load_case


DEFAULT_MAX_CASES = 50


def build_parser() -> argparse.ArgumentParser:
    """Build the score audit command parser."""
    parser = argparse.ArgumentParser(
        description="Audit déterministe de la distribution du score VitalSignal AI."
    )
    parser.add_argument(
        "--start-case-id",
        type=int,
        required=True,
        help="Premier case_id à auditer",
    )
    parser.add_argument(
        "--end-case-id",
        type=int,
        required=True,
        help="Dernier case_id à auditer, inclus",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Intervalle d'échantillonnage en secondes (défaut : 2)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Chemin de fichier JSON où écrire l'audit au lieu de l'afficher",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=DEFAULT_MAX_CASES,
        help=(
            "Nombre maximal de case_id à auditer pour éviter un scan involontaire "
            f"trop large (défaut : {DEFAULT_MAX_CASES})"
        ),
    )
    return parser


def build_score_audit(
    start_case_id: int,
    end_case_id: int,
    interval: int = 2,
) -> dict:
    """Build a JSON-compatible score audit over a case_id range."""
    records = []
    for case_id in range(start_case_id, end_case_id + 1):
        raw_frame = load_case(case_id, interval)
        analysis = analyze_intervention(case_id, raw_frame, interval)
        score = calculate_priority_score(analysis)
        records.append(build_audit_record(analysis, score))

    return {
        "summary": summarize_audit(records),
        "records": records,
    }


def render_score_audit(audit: dict) -> str:
    """Render a score audit as stable JSON."""
    return json.dumps(audit, ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the deterministic score audit command."""
    args = build_parser().parse_args(argv)
    if args.start_case_id < 1 or args.end_case_id < args.start_case_id:
        print("Intervalle de case_id invalide.")
        return 1
    if args.interval < 1:
        print("interval doit être un entier positif.")
        return 1
    if args.max_cases < 1:
        print("max-cases doit être un entier positif.")
        return 1

    requested_cases = args.end_case_id - args.start_case_id + 1
    if requested_cases > args.max_cases:
        print(
            f"Audit refusé : {requested_cases} case_id demandés, "
            f"limite actuelle {args.max_cases}. Augmente --max-cases si cet audit "
            "est volontaire."
        )
        return 1

    try:
        audit = build_score_audit(args.start_case_id, args.end_case_id, args.interval)
    except (OSError, ValueError) as error:
        print(f"Audit impossible : {error}")
        return 1

    rendered_audit = render_score_audit(audit)
    if args.output is not None:
        args.output.write_text(rendered_audit, encoding="utf-8")
    else:
        print(rendered_audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
