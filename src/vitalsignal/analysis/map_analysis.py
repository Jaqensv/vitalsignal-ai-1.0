"""Analyze mean arterial pressure according to its measurement mode."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from vitalsignal.analysis.anomaly_rules import (
    HYPERTENSION_THRESHOLD,
    HYPOTENSION_THRESHOLD,
    SEVERE_HYPERTENSION_THRESHOLD,
    SEVERE_HYPOTENSION_THRESHOLD,
    AnomalyEpisode,
    detect_hypertension,
    detect_hypotension,
)
from vitalsignal.analysis.map_source import MAPSource, select_map_source


PressureDirection = Literal["low", "high"]
PressureSeverity = Literal["standard", "severe"]
MAPAnalysisStatus = Literal["unavailable", "continuous", "intermittent"]
NIBP_DUPLICATE_WINDOW_SECONDS = 120


@dataclass(frozen=True)
class PointObservation:
    """One abnormal intermittent pressure measurement."""

    signal: MAPSource
    time_seconds: int
    value: float
    direction: PressureDirection
    severity: PressureSeverity


@dataclass(frozen=True)
class MAPAnalysis:
    """Pressure analysis that preserves how the source was measured."""

    status: MAPAnalysisStatus
    source: MAPSource | None
    episodes: tuple[AnomalyEpisode, ...]
    point_observations: tuple[PointObservation, ...]


def analyze_map(
    frame: pd.DataFrame,
    sample_interval_seconds: int = 1,
) -> MAPAnalysis:
    """Analyze the best usable pressure source without inventing continuity."""
    selection = select_map_source(frame, sample_interval_seconds)
    if selection is None:
        return MAPAnalysis("unavailable", None, (), ())

    if selection.measurement_mode == "continuous":
        episodes = (
            detect_hypotension(
                selection.series,
                selection.source,
                sample_interval_seconds,
            )
            + detect_hypertension(
                selection.series,
                selection.source,
                sample_interval_seconds,
            )
        )
        return MAPAnalysis("continuous", selection.source, tuple(episodes), ())

    observations = _find_intermittent_observations(
        selection.series,
        selection.source,
        sample_interval_seconds,
    )
    return MAPAnalysis("intermittent", selection.source, (), tuple(observations))


def _find_intermittent_observations(
    series: pd.Series,
    signal: MAPSource,
    sample_interval_seconds: int,
) -> list[PointObservation]:
    """Return abnormal measurements without inferring what happened between them."""
    observations: list[PointObservation] = []
    previous_value: float | None = None
    previous_time_seconds: int | None = None

    for position, value in enumerate(series):
        if pd.isna(value):
            continue

        numeric_value = float(value)
        time_seconds = position * sample_interval_seconds
        is_repeated_measurement = (
            previous_value == numeric_value
            and previous_time_seconds is not None
            and time_seconds - previous_time_seconds <= NIBP_DUPLICATE_WINDOW_SECONDS
        )
        previous_value = numeric_value
        previous_time_seconds = time_seconds

        if is_repeated_measurement:
            continue

        if numeric_value < HYPOTENSION_THRESHOLD:
            observations.append(
                PointObservation(
                    signal=signal,
                    time_seconds=time_seconds,
                    value=numeric_value,
                    direction="low",
                    severity=(
                        "severe"
                        if numeric_value < SEVERE_HYPOTENSION_THRESHOLD
                        else "standard"
                    ),
                )
            )
        elif numeric_value > HYPERTENSION_THRESHOLD:
            observations.append(
                PointObservation(
                    signal=signal,
                    time_seconds=time_seconds,
                    value=numeric_value,
                    direction="high",
                    severity=(
                        "severe"
                        if numeric_value > SEVERE_HYPERTENSION_THRESHOLD
                        else "standard"
                    ),
                )
            )

    return observations
