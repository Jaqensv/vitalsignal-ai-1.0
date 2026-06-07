"""Analyze heart rate only when signal quality permits it."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from vitalsignal.analysis.anomaly_rules import (
    AnomalyEpisode,
    detect_bradycardia,
    detect_tachycardia,
)
from vitalsignal.analysis.signal_quality import QualityStatus, SignalQuality, assess_signal_quality


HeartRateAnalysisStatus = Literal["missing_column", "unusable", "analyzed"]


@dataclass(frozen=True)
class HeartRateAnalysis:
    """Result of heart-rate quality control and anomaly detection."""

    status: HeartRateAnalysisStatus
    quality: SignalQuality | None
    episodes: tuple[AnomalyEpisode, ...]
    reason: QualityStatus | None


def analyze_heart_rate(
    frame: pd.DataFrame,
    sample_interval_seconds: int = 1,
) -> HeartRateAnalysis:
    """Detect abnormal heart rate only when the signal is usable."""
    if "HR" not in frame.columns:
        return HeartRateAnalysis("missing_column", None, (), "absent")

    quality = assess_signal_quality(frame["HR"], sample_interval_seconds)
    if quality.status != "usable":
        return HeartRateAnalysis("unusable", quality, (), quality.status)

    episodes = (
        detect_tachycardia(frame["HR"], sample_interval_seconds)
        + detect_bradycardia(frame["HR"], sample_interval_seconds)
    )
    return HeartRateAnalysis("analyzed", quality, tuple(episodes), None)

