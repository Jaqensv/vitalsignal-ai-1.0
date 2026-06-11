import pandas as pd

from vitalsignal.analysis.spo2_analysis import analyze_spo2


def test_analyze_spo2_detects_desaturation_on_usable_signal() -> None:
    frame = pd.DataFrame({"SpO2": [98.0] * 10 + [89.0] * 30 + [98.0] * 10})

    analysis = analyze_spo2(frame)

    assert analysis.status == "analyzed"
    assert analysis.reason is None
    assert len(analysis.episodes) == 1


def test_analyze_spo2_does_not_analyze_absent_signal() -> None:
    frame = pd.DataFrame({"SpO2": [None] * 60})

    analysis = analyze_spo2(frame)

    assert analysis.status == "unusable"
    assert analysis.reason == "absent"
    assert analysis.episodes == ()


def test_analyze_spo2_does_not_analyze_too_incomplete_signal() -> None:
    frame = pd.DataFrame({"SpO2": [90.0] * 30 + [None] * 40})

    analysis = analyze_spo2(frame)

    assert analysis.status == "unusable"
    assert analysis.reason == "too_incomplete"
    assert analysis.episodes == ()


def test_analyze_spo2_accepts_long_stable_signal() -> None:
    frame = pd.DataFrame({"SpO2": [88.0] * 600})

    analysis = analyze_spo2(frame)

    assert analysis.status == "analyzed"
    assert analysis.reason is None
    assert len(analysis.episodes) == 1


def test_analyze_spo2_reports_missing_column() -> None:
    analysis = analyze_spo2(pd.DataFrame({"HR": [80.0]}))

    assert analysis.status == "missing_column"
    assert analysis.reason == "absent"
    assert analysis.quality is None
