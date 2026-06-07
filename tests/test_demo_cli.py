from vitalsignal.app.demo_cli import build_demo_frame, build_demo_report


def test_build_demo_frame_contains_expected_signals() -> None:
    frame = build_demo_frame()

    assert {"ART_MAP", "HR", "SpO2", "EtCO2"}.issubset(frame.columns)
    assert len(frame) > 0


def test_build_demo_report_contains_known_anomalies() -> None:
    report = build_demo_report()

    assert "hypotension" in report
    assert "tachycardie" in report
    assert "Timeline des anomalies" in report


def test_build_demo_report_can_return_markdown() -> None:
    report = build_demo_report("markdown")

    assert report.startswith("# Rapport VitalSignal AI")
    assert "## Timeline des anomalies" in report
