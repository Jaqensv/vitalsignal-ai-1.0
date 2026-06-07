"""Assess whether vital-sign columns are reliable enough for analysis."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd


MAX_MISSING_RATIO = 0.50
MIN_NIBP_MEASUREMENTS = 3
DEFAULT_FLAT_DURATION_SECONDS = 120
FLAT_DURATION_SECONDS: dict[str, int | None] = {
    "ART_MAP": 120,
    "NIBP_MAP": None,
    "HR": 600,
    "SpO2": None,
    "EtCO2": 900,
}

QualityStatus = Literal["absent", "too_incomplete", "flat", "usable"]


@dataclass(frozen=True)
class SignalQuality:
    """Summary of the quality checks applied to one signal."""

    status: QualityStatus
    total_samples: int
    available_samples: int
    missing_ratio: float


def _longest_constant_run(series: pd.Series) -> int:
    """Return the longest run of identical consecutive non-missing values."""
    groups = series.ne(series.shift()) | series.isna()
    run_lengths = series.notna().groupby(groups.cumsum()).sum()
    return int(run_lengths.max()) if not run_lengths.empty else 0


def assess_signal_quality(
    series: pd.Series,
    sample_interval_seconds: int = 1,
) -> SignalQuality:
    """Classify one signal without interpreting its medical meaning."""
    if sample_interval_seconds < 1:
        raise ValueError("sample_interval_seconds must be a positive integer")

    total_samples = len(series)
    available = series.dropna()
    available_samples = len(available)

    if total_samples == 0 or available_samples == 0:
        return SignalQuality("absent", total_samples, available_samples, 1.0)

    missing_ratio = 1 - (available_samples / total_samples)

    if series.name == "NIBP_MAP":
        status: QualityStatus = (
            "usable"
            if available_samples >= MIN_NIBP_MEASUREMENTS
            else "too_incomplete"
        )
        return SignalQuality(status, total_samples, available_samples, missing_ratio)

    flat_duration = FLAT_DURATION_SECONDS.get(
        str(series.name),
        DEFAULT_FLAT_DURATION_SECONDS,
    )
    longest_constant_duration = (
        _longest_constant_run(series) * sample_interval_seconds
    )

    if missing_ratio > MAX_MISSING_RATIO:
        status = "too_incomplete"
    elif flat_duration is not None and longest_constant_duration >= flat_duration:
        status = "flat"
    else:
        status = "usable"

    return SignalQuality(status, total_samples, available_samples, missing_ratio)


def assess_frame_quality(
    frame: pd.DataFrame,
    sample_interval_seconds: int = 1,
) -> dict[str, SignalQuality]:
    """Assess every signal column in a DataFrame."""
    return {
        column: assess_signal_quality(frame[column], sample_interval_seconds)
        for column in frame.columns
    }
