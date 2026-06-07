import pandas as pd

from vitalsignal.analysis.pipeline import analyze_intervention
from vitalsignal.analysis.scoring import calculate_priority_score


def test_score_uses_only_main_episode_per_signal() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [60.0] * 60 + [70.0] + [60.0] * 60,
            "HR": [80.0, 81.0] * 60 + [80.0],
        }
    )

    score = calculate_priority_score(analyze_intervention(1, frame))

    primary = [
        item
        for item in score.contributions
        if item.category == "global_primary_episode"
    ]
    assert len(primary) == 1
    assert primary[0].points == 15


def test_score_adds_normalized_anomaly_burden() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [60.0] * 60 + [70.0] * 60,
            "HR": [80.0, 81.0] * 60,
        }
    )

    score = calculate_priority_score(analyze_intervention(1, frame))

    burden = [item for item in score.contributions if item.category == "anomaly_burden"]
    assert burden[0].points == 5
    assert "50.0%" in burden[0].description


def test_score_weights_intermittent_map_observations_conservatively() -> None:
    frame = pd.DataFrame(
        {"NIBP_MAP": [45.0, None, None, 60.0, None, None, 130.0]}
    )

    score = calculate_priority_score(analyze_intervention(1, frame))

    assert score.value == 5
    assert score.affected_signals == ("NIBP_MAP",)


def test_score_adds_multi_signal_and_simultaneity_bonuses() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [60.0] * 60,
            "HR": [125.0] * 30 + [80.0, 81.0] * 15,
            "SpO2": [98.0, 99.0] * 30,
            "EtCO2": [35.0, 36.0] * 30,
        }
    )

    score = calculate_priority_score(analyze_intervention(1, frame))

    categories = [item.category for item in score.contributions]
    assert "multi_signal" in categories
    assert "simultaneity" in categories
    assert score.affected_signals == ("ART_MAP", "HR")


def test_score_keeps_additional_severe_signals_visible() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [45.0] * 15 + [70.0] * 15,
            "HR": [155.0] * 15 + [80.0, 81.0] * 7 + [80.0],
            "SpO2": [98.0, 99.0] * 15,
            "EtCO2": [35.0, 36.0] * 15,
        }
    )

    score = calculate_priority_score(analyze_intervention(1, frame))

    additional = [
        item
        for item in score.contributions
        if item.category == "additional_severe_signals"
    ]
    assert additional[0].points == 5


def test_score_is_zero_without_detected_anomaly() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": list(range(70, 130)),
            "HR": list(range(60, 120)),
            "SpO2": [98.0, 99.0] * 30,
            "EtCO2": [35.0, 36.0] * 30,
        }
    )

    score = calculate_priority_score(analyze_intervention(1, frame))

    assert score.value == 0
    assert score.level == "none"
    assert score.affected_signals == ()
