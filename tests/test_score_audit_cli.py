import json

import pandas as pd

from vitalsignal.score_audit_cli import (
    DEFAULT_MAX_CASES,
    build_parser,
    build_score_audit,
    main,
    render_score_audit,
)


def test_score_audit_cli_parser_reads_case_range() -> None:
    args = build_parser().parse_args(
        [
            "--start-case-id",
            "1",
            "--end-case-id",
            "10",
        ]
    )

    assert args.start_case_id == 1
    assert args.end_case_id == 10
    assert args.interval == 2
    assert args.max_cases == DEFAULT_MAX_CASES


def test_score_audit_cli_rejects_invalid_case_range() -> None:
    assert main(["--start-case-id", "10", "--end-case-id", "1"]) == 1


def test_score_audit_cli_rejects_too_large_audit() -> None:
    assert main(["--start-case-id", "1", "--end-case-id", "2", "--max-cases", "1"]) == 1


def test_score_audit_cli_rejects_invalid_interval() -> None:
    assert main(["--start-case-id", "1", "--end-case-id", "1", "--interval", "0"]) == 1


def test_render_score_audit_returns_json() -> None:
    audit = {
        "summary": {"case_count": 1},
        "records": [{"case_id": 42, "score": 25}],
    }

    rendered = render_score_audit(audit)
    parsed = json.loads(rendered)

    assert parsed["summary"]["case_count"] == 1
    assert parsed["records"][0]["case_id"] == 42


def test_build_score_audit_uses_deterministic_pipeline(monkeypatch) -> None:
    def fake_load_case(case_id: int, interval: int) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "ART_MAP": [60.0, 61.0] * 30,
                "HR": [80.0, 81.0] * 30,
            }
        )

    monkeypatch.setattr("vitalsignal.app.score_audit_command.load_case", fake_load_case)

    audit = build_score_audit(1, 2)

    assert audit["summary"]["case_count"] == 2
    assert audit["summary"]["score"]["maximum"] == 25
    assert [record["case_id"] for record in audit["records"]] == [1, 2]
