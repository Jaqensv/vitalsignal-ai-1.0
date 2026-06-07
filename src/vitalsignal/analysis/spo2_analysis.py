"""Analyze oxygen saturation only when signal quality permits it."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from vitalsignal.analysis.anomaly_rules import AnomalyEpisode, detect_desaturation
from vitalsignal.analysis.signal_quality import QualityStatus, SignalQuality, assess_signal_quality


SpO2AnalysisStatus = Literal["missing_column", "unusable", "analyzed"]


@dataclass(frozen=True)
class SpO2Analysis:
    """Result of oxygen-saturation quality control and anomaly detection."""

    status: SpO2AnalysisStatus
    quality: SignalQuality | None
    episodes: tuple[AnomalyEpisode, ...]
    reason: QualityStatus | None


def analyze_spo2(
    frame: pd.DataFrame,
    sample_interval_seconds: int = 1,
) -> SpO2Analysis:
    """Detect desaturation only when the oxygen-saturation signal is usable."""
    if "SpO2" not in frame.columns:
        return SpO2Analysis("missing_column", None, (), "absent")

    quality = assess_signal_quality(frame["SpO2"], sample_interval_seconds)
    if quality.status != "usable":
        return SpO2Analysis("unusable", quality, (), quality.status)

    episodes = detect_desaturation(frame["SpO2"], sample_interval_seconds)
    return SpO2Analysis("analyzed", quality, tuple(episodes), None)

