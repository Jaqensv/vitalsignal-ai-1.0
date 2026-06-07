import pandas as pd

from vitalsignal.main import build_parser, render_cli_report, run_case_analysis


def test_run_case_analysis_connects_loader_pipeline_score_and_report() -> None:
    def fake_loader(case_id: int, interval: int) -> pd.DataFrame:
        assert case_id == 42
        assert interval == 2
        return pd.DataFrame(
            {
                "ART_MAP": [60.0, 61.0] * 30,
                "HR": [80.0, 81.0] * 30,
                "SpO2": [98.0, 99.0] * 30,
                "EtCO2": [35.0, 36.0] * 30,
            }
        )

    analysis, score, report, ai_summary = run_case_analysis(42, loader=fake_loader)

    assert analysis.case_id == 42
    assert score.value == 25
    assert "intervention n° 42" in report
    assert ai_summary is None


def test_build_parser_reads_case_id_and_interval() -> None:
    args = build_parser().parse_args(["42", "--interval", "2"])

    assert args.case_id == 42
    assert args.interval == 2


def test_build_parser_uses_two_second_default_interval() -> None:
    args = build_parser().parse_args(["42"])

    assert args.interval == 2


def test_build_parser_accepts_ai_flag() -> None:
    args = build_parser().parse_args(["42", "--ai"])

    assert args.ai is True


def test_build_parser_accepts_format_and_output() -> None:
    args = build_parser().parse_args(
        ["42", "--format", "json", "--output", "report.json"]
    )

    assert args.format == "json"
    assert str(args.output) == "report.json"


def test_render_cli_report_can_return_json() -> None:
    def fake_loader(case_id: int, interval: int) -> pd.DataFrame:
        return pd.DataFrame({"ART_MAP": [60.0, 61.0] * 30})

    analysis, score, report, ai_summary = run_case_analysis(42, loader=fake_loader)
    rendered = render_cli_report(analysis, score, report, ai_summary, "json")

    assert '"case_id": 42' in rendered
    assert '"priority_score"' in rendered
