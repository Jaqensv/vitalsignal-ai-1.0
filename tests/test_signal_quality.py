import pandas as pd
import pytest

from vitalsignal.analysis.signal_quality import assess_frame_quality, assess_signal_quality


def test_assess_signal_quality_detects_absent_signal() -> None:
    quality = assess_signal_quality(pd.Series([None, None, None]))

    assert quality.status == "absent"
    assert quality.available_samples == 0
    assert quality.missing_ratio == 1.0


def test_assess_signal_quality_detects_too_incomplete_signal() -> None:
    quality = assess_signal_quality(pd.Series([80.0, None, None, None]))

    assert quality.status == "too_incomplete"
    assert quality.missing_ratio == pytest.approx(0.75)


def test_assess_signal_quality_detects_flat_signal() -> None:
    quality = assess_signal_quality(pd.Series([80.0] * 600, name="HR"))

    assert quality.status == "flat"


def test_stable_spo2_is_not_marked_flat_too_early() -> None:
    quality = assess_signal_quality(pd.Series([98.0] * 3600, name="SpO2"))

    assert quality.status == "usable"


def test_repeated_nibp_map_is_not_checked_as_flat() -> None:
    quality = assess_signal_quality(
        pd.Series([75.0, 75.0, 75.0], name="NIBP_MAP")
    )

    assert quality.status == "usable"


def test_sparse_nibp_map_can_be_usable() -> None:
    signal = pd.Series([75.0, None, None, 76.0, None, None, 74.0], name="NIBP_MAP")

    quality = assess_signal_quality(signal)

    assert quality.status == "usable"
    assert quality.missing_ratio > 0.50


def test_nibp_map_with_too_few_measurements_is_incomplete() -> None:
    quality = assess_signal_quality(pd.Series([75.0, None], name="NIBP_MAP"))

    assert quality.status == "too_incomplete"


def test_flat_check_detects_consecutive_run_with_other_values() -> None:
    signal = pd.Series([79.0, 81.0] + [80.0] * 600, name="HR")

    quality = assess_signal_quality(signal)

    assert quality.status == "flat"


def test_assess_frame_quality_classifies_each_column() -> None:
    frame = pd.DataFrame(
        {
            "HR": list(range(60, 180)),
            "SpO2": [98.0] * 120,
        }
    )

    quality = assess_frame_quality(frame)

    assert quality["HR"].status == "usable"
    assert quality["SpO2"].status == "usable"
