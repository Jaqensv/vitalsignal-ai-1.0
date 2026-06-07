import pandas as pd
import pytest

from vitalsignal.analysis.pipeline import analyze_intervention


def test_analyze_intervention_runs_all_priority_analyses() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [60.0] * 60,
            "NIBP_MAP": [None] * 60,
            "HR": [125.0] * 30 + list(range(80, 110)),
            "SpO2": [90.0] * 30 + list(range(70, 100)),
            "EtCO2": [24.0] * 30 + list(range(30, 60)),
        }
    )

    analysis = analyze_intervention(case_id=42, raw_frame=frame)

    assert analysis.case_id == 42
    assert analysis.total_samples == 60
    assert analysis.duration_seconds == 60
    assert analysis.analyzable_seconds["ART_MAP"] == 60
    assert analysis.analyzable_seconds["NIBP_MAP"] == 0
    assert len(analysis.map_analysis.episodes) == 1
    assert len(analysis.spo2_analysis.episodes) == 1
    assert len(analysis.heart_rate_analysis.episodes) == 1
    assert len(analysis.etco2_analysis.episodes) == 1


def test_analyze_intervention_cleans_impossible_values_before_analysis() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [70.0] * 60,
            "HR": [350.0] * 60,
            "SpO2": [101.0] * 60,
            "EtCO2": [200.0] * 60,
        }
    )

    analysis = analyze_intervention(case_id=1, raw_frame=frame)

    assert analysis.heart_rate_analysis.reason == "absent"
    assert analysis.spo2_analysis.reason == "absent"
    assert analysis.etco2_analysis.reason == "absent"


def test_analyze_intervention_preserves_missing_signal_information() -> None:
    analysis = analyze_intervention(
        case_id=3,
        raw_frame=pd.DataFrame({"HR": list(range(60, 120))}),
    )

    assert analysis.map_analysis.status == "unavailable"
    assert analysis.spo2_analysis.status == "missing_column"
    assert analysis.etco2_analysis.status == "missing_column"


@pytest.mark.parametrize(
    ("case_id", "sample_interval_seconds"),
    [(0, 1), (1, 0)],
)
def test_analyze_intervention_rejects_invalid_inputs(
    case_id: int,
    sample_interval_seconds: int,
) -> None:
    with pytest.raises(ValueError):
        analyze_intervention(
            case_id=case_id,
            raw_frame=pd.DataFrame(),
            sample_interval_seconds=sample_interval_seconds,
        )
