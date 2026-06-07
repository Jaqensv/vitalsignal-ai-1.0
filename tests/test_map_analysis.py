import pandas as pd

from vitalsignal.analysis.map_analysis import analyze_map


def test_analyze_map_uses_continuous_rules_for_art_map() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [60.0] * 60,
            "NIBP_MAP": [45.0, None, 130.0] + [None] * 57,
        }
    )

    analysis = analyze_map(frame)

    assert analysis.status == "continuous"
    assert analysis.source == "ART_MAP"
    assert len(analysis.episodes) == 1
    assert analysis.point_observations == ()


def test_analyze_map_returns_points_for_intermittent_nibp_map() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [None] * 7,
            "NIBP_MAP": [45.0, None, None, 75.0, None, None, 130.0],
        }
    )

    analysis = analyze_map(frame)

    assert analysis.status == "intermittent"
    assert analysis.source == "NIBP_MAP"
    assert analysis.episodes == ()
    assert len(analysis.point_observations) == 2
    assert analysis.point_observations[0].direction == "low"
    assert analysis.point_observations[0].severity == "severe"
    assert analysis.point_observations[1].direction == "high"
    assert analysis.point_observations[1].severity == "standard"


def test_analyze_map_does_not_infer_duration_between_nibp_measurements() -> None:
    frame = pd.DataFrame(
        {
            "NIBP_MAP": [60.0, None, None, None, None, 60.0, 75.0],
        }
    )

    analysis = analyze_map(frame, sample_interval_seconds=60)

    assert analysis.status == "intermittent"
    assert analysis.episodes == ()
    assert [point.time_seconds for point in analysis.point_observations] == [0, 300]


def test_analyze_map_reports_unavailable_source() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [None] * 5,
            "NIBP_MAP": [75.0, None, None, None, None],
        }
    )

    analysis = analyze_map(frame)

    assert analysis.status == "unavailable"
    assert analysis.source is None
    assert analysis.episodes == ()
    assert analysis.point_observations == ()


def test_analyze_map_groups_repeated_nibp_values_as_one_observation() -> None:
    frame = pd.DataFrame(
        {
            "NIBP_MAP": [63.0, None, 63.0, None, 63.0, None, 75.0],
        }
    )

    analysis = analyze_map(frame, sample_interval_seconds=2)

    assert len(analysis.point_observations) == 1
    assert analysis.point_observations[0].value == 63.0
    assert analysis.point_observations[0].time_seconds == 0


def test_same_nibp_value_after_long_gap_is_a_new_observation() -> None:
    frame = pd.DataFrame(
        {
            "NIBP_MAP": [63.0, None, None, 75.0, None, None, 63.0],
        }
    )

    analysis = analyze_map(frame, sample_interval_seconds=60)

    assert len(analysis.point_observations) == 2
    assert [point.time_seconds for point in analysis.point_observations] == [0, 360]
