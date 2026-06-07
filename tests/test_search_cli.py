import pandas as pd

from vitalsignal.analysis.case_search import SearchResult
from vitalsignal.analysis.pipeline import analyze_intervention
from vitalsignal.analysis.scoring import calculate_priority_score
from vitalsignal.search_cli import (
    DEFAULT_MAX_CASES,
    build_search_summary,
    build_parser,
    main,
    render_search_results,
)


def test_search_cli_parser_reads_case_range_and_anomaly() -> None:
    args = build_parser().parse_args(
        [
            "--start-case-id",
            "1",
            "--end-case-id",
            "10",
            "--anomaly",
            "desaturation",
        ]
    )

    assert args.start_case_id == 1
    assert args.end_case_id == 10
    assert args.anomaly == "desaturation"
    assert args.interval == 2
    assert args.format == "text"
    assert args.max_cases == DEFAULT_MAX_CASES


def test_search_cli_rejects_invalid_case_range() -> None:
    assert main(["--start-case-id", "10", "--end-case-id", "1"]) == 1


def test_search_cli_rejects_too_large_scan() -> None:
    assert main(["--start-case-id", "1", "--end-case-id", "2", "--max-cases", "1"]) == 1


def test_search_cli_rejects_invalid_max_cases() -> None:
    assert main(["--start-case-id", "1", "--end-case-id", "1", "--max-cases", "0"]) == 1


def test_search_cli_parser_accepts_json_output() -> None:
    args = build_parser().parse_args(
        [
            "--start-case-id",
            "1",
            "--end-case-id",
            "10",
            "--format",
            "json",
            "--output",
            "search.json",
        ]
    )

    assert args.format == "json"
    assert str(args.output) == "search.json"


def test_search_cli_parser_accepts_csv_output() -> None:
    args = build_parser().parse_args(
        [
            "--start-case-id",
            "1",
            "--end-case-id",
            "10",
            "--format",
            "csv",
            "--output",
            "search.csv",
        ]
    )

    assert args.format == "csv"
    assert str(args.output) == "search.csv"


def test_render_search_results_can_return_json() -> None:
    frame = pd.DataFrame({"ART_MAP": [60.0] * 60})
    analysis = analyze_intervention(42, frame)
    score = calculate_priority_score(analysis)
    result = SearchResult(
        case_id=42,
        score=score,
        analysis=analysis,
        matched_anomalies=("hypotension",),
    )

    summary = build_search_summary(1, 5, "hypotension", 2, 1)
    rendered = render_search_results([result], "json", summary)

    assert '"summary": {' in rendered
    assert '"scanned_cases": 5' in rendered
    assert '"matched_cases": 1' in rendered
    assert '"case_id": 42' in rendered
    assert '"matched_anomalies": [' in rendered
    assert '"hypotension"' in rendered


def test_render_search_results_can_return_csv() -> None:
    frame = pd.DataFrame({"ART_MAP": [60.0] * 60})
    analysis = analyze_intervention(42, frame)
    score = calculate_priority_score(analysis)
    result = SearchResult(
        case_id=42,
        score=score,
        analysis=analysis,
        matched_anomalies=("hypotension",),
    )

    rendered = render_search_results([result], "csv")

    assert rendered.splitlines()[0] == "case_id,score,level,matched_anomalies"
    assert "42,25,moderate,hypotension" in rendered


def test_render_search_results_text_includes_summary() -> None:
    summary = build_search_summary(1, 5, "any", 2, 0)

    rendered = render_search_results([], "text", summary)

    assert "interventions 1 à 5" in rendered
    assert "5 scanné(s)" in rendered
    assert "0 résultat(s)" in rendered
    assert "Aucune intervention correspondante." in rendered
