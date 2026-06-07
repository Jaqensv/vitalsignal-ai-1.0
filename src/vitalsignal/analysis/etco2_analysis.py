"""Analyze end-tidal carbon dioxide only when signal quality permits it."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from vitalsignal.analysis.anomaly_rules import (
    AnomalyEpisode,
    detect_high_etco2,
    detect_low_etco2,
)
from vitalsignal.analysis.signal_quality import QualityStatus, SignalQuality, assess_signal_quality


EtCO2AnalysisStatus = Literal["missing_column", "unusable", "analyzed"]


@dataclass(frozen=True)
class EtCO2Analysis:
    """Result of end-tidal carbon-dioxide quality control and detection."""

    status: EtCO2AnalysisStatus
    quality: SignalQuality | None
    episodes: tuple[AnomalyEpisode, ...]
    reason: QualityStatus | None


def analyze_etco2(
    frame: pd.DataFrame,
    sample_interval_seconds: int = 1,
) -> EtCO2Analysis:
    """Detect abnormal end-tidal carbon dioxide only on a usable signal."""
    if "EtCO2" not in frame.columns:
        return EtCO2Analysis("missing_column", None, (), "absent")

    quality = assess_signal_quality(frame["EtCO2"], sample_interval_seconds)
    if quality.status != "usable":
        return EtCO2Analysis("unusable", quality, (), quality.status)

    episodes = (
        detect_low_etco2(frame["EtCO2"], sample_interval_seconds)
        + detect_high_etco2(frame["EtCO2"], sample_interval_seconds)
    )
    return EtCO2Analysis("analyzed", quality, tuple(episodes), None)

