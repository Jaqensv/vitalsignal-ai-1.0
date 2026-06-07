import pandas as pd

from vitalsignal.analysis.pipeline import analyze_intervention
from vitalsignal.analysis.score_audit import build_audit_record, summarize_audit
from vitalsignal.analysis.scoring import calculate_priority_score


def _build_record(case_id: int, pressure: list[float]) -> dict:
    frame = pd.DataFrame(
        {
            "ART_MAP": pressure,
            "HR": [80.0, 81.0] * (len(pressure) // 2),
        }
    )
    analysis = analyze_intervention(case_id, frame)
    return build_audit_record(analysis, calculate_priority_score(analysis))


def test_build_audit_record_contains_score_details() -> None:
    record = _build_record(1, [60.0] * 60)

    assert record["case_id"] == 1
    assert record["score"] == 25
    assert record["episode_counts"] == {"hypotension": 1}
    assert record["contribution_points"]["global_primary_episode"] == 15


def test_summarize_audit_describes_distribution() -> None:
    records = [
        _build_record(1, [60.0] * 60),
        _build_record(2, list(range(70, 130))),
    ]

    summary = summarize_audit(records)

    assert summary["case_count"] == 2
    assert summary["score"]["minimum"] == 0
    assert summary["score"]["maximum"] == 25
    assert summary["score"]["mean"] == 12.5
    assert summary["level_counts"] == {"moderate": 1, "none": 1}
