"""Search multiple VitalDB interventions using deterministic anomaly rules."""

from dataclasses import dataclass
from collections.abc import Callable
from typing import Literal

import pandas as pd

from vitalsignal.analysis.pipeline import InterventionAnalysis, analyze_intervention
from vitalsignal.analysis.scoring import PriorityScore, calculate_priority_score
from vitalsignal.io.vitaldb_loader import load_case


CaseLoader = Callable[[int, int], pd.DataFrame]
ProgressCallback = Callable[[int, int, int], None]


AnomalyFilter = Literal[
    "any",
    "hypotension",
    "hypertension",
    "desaturation",
    "tachycardia",
    "bradycardia",
    "low_etco2",
    "high_etco2",
]


@dataclass(frozen=True)
class SearchResult:
    """One deterministic match in a multi-intervention scan."""

    case_id: int
    score: PriorityScore
    analysis: InterventionAnalysis
    matched_anomalies: tuple[str, ...]


def search_interventions(
    case_ids: list[int],
    anomaly_filter: AnomalyFilter = "any",
    interval: int = 2,
    loader: CaseLoader | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[SearchResult]:
    """Scan interventions deterministically and return matching cases."""
    results: list[SearchResult] = []
    selected_loader = loader if loader is not None else load_case
    total_cases = len(case_ids)

    for index, case_id in enumerate(case_ids, start=1):
        raw_frame = selected_loader(case_id, interval)
        analysis = analyze_intervention(case_id, raw_frame, interval)
        score = calculate_priority_score(analysis)

        matched_anomalies = _matched_anomalies(analysis, anomaly_filter)
        if matched_anomalies:
            results.append(
                SearchResult(
                    case_id=case_id,
                    score=score,
                    analysis=analysis,
                    matched_anomalies=matched_anomalies,
                )
            )
        if progress_callback is not None:
            progress_callback(index, total_cases, case_id)

    return sorted(results, key=lambda result: result.score.value, reverse=True)


def _matched_anomalies(
    analysis: InterventionAnalysis,
    anomaly_filter: AnomalyFilter,
) -> tuple[str, ...]:
    """Return anomaly types matching the requested deterministic filter."""
    episodes = (
        analysis.map_analysis.episodes
        + analysis.spo2_analysis.episodes
        + analysis.heart_rate_analysis.episodes
        + analysis.etco2_analysis.episodes
    )
    anomaly_types = {episode.anomaly_type for episode in episodes}

    if anomaly_filter == "any":
        return tuple(sorted(anomaly_types))

    if anomaly_filter in anomaly_types:
        return (anomaly_filter,)

    return ()
