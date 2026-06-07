import pandas as pd

from vitalsignal.analysis.etco2_analysis import analyze_etco2


def test_analyze_etco2_detects_low_and_high_episodes() -> None:
    frame = pd.DataFrame(
        {
            "EtCO2": (
                [35.0] * 5
                + [24.0] * 30
                + [35.0] * 5
                + [55.0] * 30
                + [35.0] * 5
            )
        }
    )

    analysis = analyze_etco2(frame)

    assert analysis.status == "analyzed"
    assert [episode.anomaly_type for episode in analysis.episodes] == [
        "low_etco2",
        "high_etco2",
    ]


def test_analyze_etco2_does_not_analyze_absent_signal() -> None:
    analysis = analyze_etco2(pd.DataFrame({"EtCO2": [None] * 60}))

    assert analysis.status == "unusable"
    assert analysis.reason == "absent"


def test_analyze_etco2_does_not_analyze_flat_signal() -> None:
    analysis = analyze_etco2(pd.DataFrame({"EtCO2": [55.0] * 900}))

    assert analysis.status == "unusable"
    assert analysis.reason == "flat"
    assert analysis.episodes == ()


def test_analyze_etco2_reports_missing_column() -> None:
    analysis = analyze_etco2(pd.DataFrame({"HR": [80.0]}))

    assert analysis.status == "missing_column"
    assert analysis.reason == "absent"
