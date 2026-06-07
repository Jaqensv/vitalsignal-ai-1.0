import pandas as pd

from vitalsignal.analysis.heart_rate_analysis import analyze_heart_rate


def test_analyze_heart_rate_detects_both_episode_types() -> None:
    frame = pd.DataFrame(
        {
            "HR": (
                [80.0] * 5
                + [125.0] * 30
                + [80.0] * 5
                + [45.0] * 30
                + [80.0] * 5
            )
        }
    )

    analysis = analyze_heart_rate(frame)

    assert analysis.status == "analyzed"
    assert [episode.anomaly_type for episode in analysis.episodes] == [
        "tachycardia",
        "bradycardia",
    ]


def test_analyze_heart_rate_does_not_analyze_absent_signal() -> None:
    analysis = analyze_heart_rate(pd.DataFrame({"HR": [None] * 60}))

    assert analysis.status == "unusable"
    assert analysis.reason == "absent"
    assert analysis.episodes == ()


def test_analyze_heart_rate_does_not_analyze_too_incomplete_signal() -> None:
    frame = pd.DataFrame({"HR": [125.0] * 30 + [None] * 40})

    analysis = analyze_heart_rate(frame)

    assert analysis.status == "unusable"
    assert analysis.reason == "too_incomplete"
    assert analysis.episodes == ()


def test_analyze_heart_rate_does_not_analyze_flat_signal() -> None:
    analysis = analyze_heart_rate(pd.DataFrame({"HR": [125.0] * 600}))

    assert analysis.status == "unusable"
    assert analysis.reason == "flat"
    assert analysis.episodes == ()


def test_analyze_heart_rate_reports_missing_column() -> None:
    analysis = analyze_heart_rate(pd.DataFrame({"SpO2": [98.0]}))

    assert analysis.status == "missing_column"
    assert analysis.reason == "absent"
    assert analysis.quality is None
