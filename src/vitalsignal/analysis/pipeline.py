"""Run the deterministic VitalSignal analysis pipeline on one intervention."""

from dataclasses import dataclass

import pandas as pd

from vitalsignal.analysis.etco2_analysis import EtCO2Analysis, analyze_etco2
from vitalsignal.analysis.heart_rate_analysis import HeartRateAnalysis, analyze_heart_rate
from vitalsignal.analysis.map_analysis import MAPAnalysis, analyze_map
from vitalsignal.analysis.preprocessing import clean_impossible_values
from vitalsignal.analysis.spo2_analysis import SpO2Analysis, analyze_spo2


@dataclass(frozen=True)
class InterventionAnalysis:
    """Structured deterministic analysis for one VitalDB intervention."""

    case_id: int
    sample_interval_seconds: int
    total_samples: int
    duration_seconds: int
    analyzable_seconds: dict[str, int]
    map_analysis: MAPAnalysis
    spo2_analysis: SpO2Analysis
    heart_rate_analysis: HeartRateAnalysis
    etco2_analysis: EtCO2Analysis


def analyze_intervention(
    case_id: int,
    raw_frame: pd.DataFrame,
    sample_interval_seconds: int = 1,
) -> InterventionAnalysis:
    """Clean and analyze all priority signals for one intervention."""
    if case_id < 1:
        raise ValueError("case_id must be a positive integer")
    if sample_interval_seconds < 1:
        raise ValueError("sample_interval_seconds must be a positive integer")

    cleaned_frame = clean_impossible_values(raw_frame)
    total_samples = len(cleaned_frame)
    analyzable_seconds = {
        signal: int(cleaned_frame[signal].notna().sum()) * sample_interval_seconds
        for signal in ("ART_MAP", "NIBP_MAP", "HR", "SpO2", "EtCO2")
        if signal in cleaned_frame.columns
    }

    return InterventionAnalysis(
        case_id=case_id,
        sample_interval_seconds=sample_interval_seconds,
        total_samples=total_samples,
        duration_seconds=total_samples * sample_interval_seconds,
        analyzable_seconds=analyzable_seconds,
        map_analysis=analyze_map(cleaned_frame, sample_interval_seconds),
        spo2_analysis=analyze_spo2(cleaned_frame, sample_interval_seconds),
        heart_rate_analysis=analyze_heart_rate(cleaned_frame, sample_interval_seconds),
        etco2_analysis=analyze_etco2(cleaned_frame, sample_interval_seconds),
    )
