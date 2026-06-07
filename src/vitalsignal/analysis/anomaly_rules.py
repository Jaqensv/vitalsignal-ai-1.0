"""Detect deterministic anomaly episodes in usable vital-sign data."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd


MAPSignal = Literal["ART_MAP", "NIBP_MAP"]
EpisodeQualification = Literal["prolonged", "severe_transient"]

HYPOTENSION_THRESHOLD = 65.0
HYPOTENSION_MIN_DURATION_SECONDS = 60
SEVERE_HYPOTENSION_THRESHOLD = 50.0
SEVERE_HYPOTENSION_MIN_DURATION_SECONDS = 15
HYPERTENSION_THRESHOLD = 120.0
HYPERTENSION_MIN_DURATION_SECONDS = 60
SEVERE_HYPERTENSION_THRESHOLD = 140.0
SEVERE_HYPERTENSION_MIN_DURATION_SECONDS = 15
DESATURATION_THRESHOLD = 92.0
DESATURATION_MIN_DURATION_SECONDS = 30
SEVERE_DESATURATION_THRESHOLD = 90.0
SEVERE_DESATURATION_MIN_DURATION_SECONDS = 15
TACHYCARDIA_THRESHOLD = 120.0
BRADYCARDIA_THRESHOLD = 50.0
HEART_RATE_MIN_DURATION_SECONDS = 30
SEVERE_TACHYCARDIA_THRESHOLD = 150.0
SEVERE_BRADYCARDIA_THRESHOLD = 40.0
SEVERE_HEART_RATE_MIN_DURATION_SECONDS = 15
LOW_ETCO2_THRESHOLD = 25.0
HIGH_ETCO2_THRESHOLD = 50.0
ETCO2_MIN_DURATION_SECONDS = 30
SEVERE_LOW_ETCO2_THRESHOLD = 20.0
SEVERE_HIGH_ETCO2_THRESHOLD = 60.0
SEVERE_ETCO2_MIN_DURATION_SECONDS = 15


@dataclass(frozen=True)
class AnomalyEpisode:
    """A continuous period during which one anomaly rule is satisfied."""

    anomaly_type: str
    signal: str
    start_seconds: int
    end_seconds: int
    duration_seconds: int
    extreme_value: float
    threshold: float
    qualifications: tuple[EpisodeQualification, ...]


def detect_hypotension(
    series: pd.Series,
    signal: MAPSignal,
    sample_interval_seconds: int = 1,
) -> list[AnomalyEpisode]:
    """Detect sustained periods where mean arterial pressure is below 65."""
    if sample_interval_seconds < 1:
        raise ValueError("sample_interval_seconds must be a positive integer")

    episodes: list[AnomalyEpisode] = []
    below_threshold = series.lt(HYPOTENSION_THRESHOLD) & series.notna()
    run_start: int | None = None

    for position, is_below in enumerate(below_threshold):
        if is_below and run_start is None:
            run_start = position
        elif not is_below and run_start is not None:
            _append_hypotension_episode(
                episodes,
                series,
                signal,
                run_start,
                position,
                sample_interval_seconds,
            )
            run_start = None

    if run_start is not None:
        _append_hypotension_episode(
            episodes,
            series,
            signal,
            run_start,
            len(series),
            sample_interval_seconds,
        )

    return episodes


def _append_hypotension_episode(
    episodes: list[AnomalyEpisode],
    series: pd.Series,
    signal: MAPSignal,
    start_position: int,
    end_position: int,
    sample_interval_seconds: int,
) -> None:
    """Append a qualifying episode using an exclusive end position."""
    duration_seconds = (end_position - start_position) * sample_interval_seconds
    episode_values = series.iloc[start_position:end_position]
    qualifications: list[EpisodeQualification] = []

    if duration_seconds >= HYPOTENSION_MIN_DURATION_SECONDS:
        qualifications.append("prolonged")

    severe_run_seconds = (
        _longest_true_run(episode_values.lt(SEVERE_HYPOTENSION_THRESHOLD))
        * sample_interval_seconds
    )
    if severe_run_seconds >= SEVERE_HYPOTENSION_MIN_DURATION_SECONDS:
        qualifications.append("severe_transient")

    if not qualifications:
        return

    episodes.append(
        AnomalyEpisode(
            anomaly_type="hypotension",
            signal=signal,
            start_seconds=start_position * sample_interval_seconds,
            end_seconds=end_position * sample_interval_seconds,
            duration_seconds=duration_seconds,
            extreme_value=float(episode_values.min()),
            threshold=HYPOTENSION_THRESHOLD,
            qualifications=tuple(qualifications),
        )
    )


def _longest_true_run(values: pd.Series) -> int:
    """Return the longest consecutive run of true values."""
    groups = values.ne(values.shift()).cumsum()
    true_run_lengths = values.groupby(groups).sum()
    return int(true_run_lengths.max()) if not true_run_lengths.empty else 0


def detect_hypertension(
    series: pd.Series,
    signal: MAPSignal,
    sample_interval_seconds: int = 1,
) -> list[AnomalyEpisode]:
    """Detect sustained or severe periods of high mean arterial pressure."""
    if sample_interval_seconds < 1:
        raise ValueError("sample_interval_seconds must be a positive integer")

    episodes: list[AnomalyEpisode] = []
    above_threshold = series.gt(HYPERTENSION_THRESHOLD) & series.notna()
    run_start: int | None = None

    for position, is_above in enumerate(above_threshold):
        if is_above and run_start is None:
            run_start = position
        elif not is_above and run_start is not None:
            _append_hypertension_episode(
                episodes,
                series,
                signal,
                run_start,
                position,
                sample_interval_seconds,
            )
            run_start = None

    if run_start is not None:
        _append_hypertension_episode(
            episodes,
            series,
            signal,
            run_start,
            len(series),
            sample_interval_seconds,
        )

    return episodes


def _append_hypertension_episode(
    episodes: list[AnomalyEpisode],
    series: pd.Series,
    signal: MAPSignal,
    start_position: int,
    end_position: int,
    sample_interval_seconds: int,
) -> None:
    """Append one qualifying high-pressure episode."""
    duration_seconds = (end_position - start_position) * sample_interval_seconds
    episode_values = series.iloc[start_position:end_position]
    qualifications: list[EpisodeQualification] = []

    if duration_seconds >= HYPERTENSION_MIN_DURATION_SECONDS:
        qualifications.append("prolonged")

    severe_run_seconds = (
        _longest_true_run(episode_values.gt(SEVERE_HYPERTENSION_THRESHOLD))
        * sample_interval_seconds
    )
    if severe_run_seconds >= SEVERE_HYPERTENSION_MIN_DURATION_SECONDS:
        qualifications.append("severe_transient")

    if not qualifications:
        return

    episodes.append(
        AnomalyEpisode(
            anomaly_type="hypertension",
            signal=signal,
            start_seconds=start_position * sample_interval_seconds,
            end_seconds=end_position * sample_interval_seconds,
            duration_seconds=duration_seconds,
            extreme_value=float(episode_values.max()),
            threshold=HYPERTENSION_THRESHOLD,
            qualifications=tuple(qualifications),
        )
    )


def detect_desaturation(
    series: pd.Series,
    sample_interval_seconds: int = 1,
) -> list[AnomalyEpisode]:
    """Detect sustained periods where oxygen saturation is below 92 percent."""
    if sample_interval_seconds < 1:
        raise ValueError("sample_interval_seconds must be a positive integer")

    episodes: list[AnomalyEpisode] = []
    below_threshold = series.lt(DESATURATION_THRESHOLD) & series.notna()
    run_start: int | None = None

    for position, is_below in enumerate(below_threshold):
        if is_below and run_start is None:
            run_start = position
        elif not is_below and run_start is not None:
            _append_desaturation_episode(
                episodes,
                series,
                run_start,
                position,
                sample_interval_seconds,
            )
            run_start = None

    if run_start is not None:
        _append_desaturation_episode(
            episodes,
            series,
            run_start,
            len(series),
            sample_interval_seconds,
        )

    return episodes


def _append_desaturation_episode(
    episodes: list[AnomalyEpisode],
    series: pd.Series,
    start_position: int,
    end_position: int,
    sample_interval_seconds: int,
) -> None:
    """Append one qualifying desaturation episode."""
    duration_seconds = (end_position - start_position) * sample_interval_seconds
    episode_values = series.iloc[start_position:end_position]
    qualifications: list[EpisodeQualification] = []

    if duration_seconds >= DESATURATION_MIN_DURATION_SECONDS:
        qualifications.append("prolonged")

    severe_run_seconds = (
        _longest_true_run(episode_values.lt(SEVERE_DESATURATION_THRESHOLD))
        * sample_interval_seconds
    )
    if severe_run_seconds >= SEVERE_DESATURATION_MIN_DURATION_SECONDS:
        qualifications.append("severe_transient")

    if not qualifications:
        return

    episodes.append(
        AnomalyEpisode(
            anomaly_type="desaturation",
            signal="SpO2",
            start_seconds=start_position * sample_interval_seconds,
            end_seconds=end_position * sample_interval_seconds,
            duration_seconds=duration_seconds,
            extreme_value=float(episode_values.min()),
            threshold=DESATURATION_THRESHOLD,
            qualifications=tuple(qualifications),
        )
    )


def detect_tachycardia(
    series: pd.Series,
    sample_interval_seconds: int = 1,
) -> list[AnomalyEpisode]:
    """Detect sustained or severe periods of high heart rate."""
    return _detect_heart_rate_anomaly(
        series=series,
        anomaly_type="tachycardia",
        threshold=TACHYCARDIA_THRESHOLD,
        severe_threshold=SEVERE_TACHYCARDIA_THRESHOLD,
        direction="high",
        sample_interval_seconds=sample_interval_seconds,
    )


def detect_bradycardia(
    series: pd.Series,
    sample_interval_seconds: int = 1,
) -> list[AnomalyEpisode]:
    """Detect sustained or severe periods of low heart rate."""
    return _detect_heart_rate_anomaly(
        series=series,
        anomaly_type="bradycardia",
        threshold=BRADYCARDIA_THRESHOLD,
        severe_threshold=SEVERE_BRADYCARDIA_THRESHOLD,
        direction="low",
        sample_interval_seconds=sample_interval_seconds,
    )


def _detect_heart_rate_anomaly(
    series: pd.Series,
    anomaly_type: Literal["tachycardia", "bradycardia"],
    threshold: float,
    severe_threshold: float,
    direction: Literal["high", "low"],
    sample_interval_seconds: int,
) -> list[AnomalyEpisode]:
    """Detect one type of abnormal heart-rate episode."""
    if sample_interval_seconds < 1:
        raise ValueError("sample_interval_seconds must be a positive integer")

    matches = (
        series.gt(threshold) if direction == "high" else series.lt(threshold)
    ) & series.notna()
    episodes: list[AnomalyEpisode] = []
    run_start: int | None = None

    for position, matches_rule in enumerate(matches):
        if matches_rule and run_start is None:
            run_start = position
        elif not matches_rule and run_start is not None:
            _append_heart_rate_episode(
                episodes,
                series,
                anomaly_type,
                threshold,
                severe_threshold,
                direction,
                run_start,
                position,
                sample_interval_seconds,
            )
            run_start = None

    if run_start is not None:
        _append_heart_rate_episode(
            episodes,
            series,
            anomaly_type,
            threshold,
            severe_threshold,
            direction,
            run_start,
            len(series),
            sample_interval_seconds,
        )

    return episodes


def _append_heart_rate_episode(
    episodes: list[AnomalyEpisode],
    series: pd.Series,
    anomaly_type: Literal["tachycardia", "bradycardia"],
    threshold: float,
    severe_threshold: float,
    direction: Literal["high", "low"],
    start_position: int,
    end_position: int,
    sample_interval_seconds: int,
) -> None:
    """Append one qualifying high- or low-heart-rate episode."""
    duration_seconds = (end_position - start_position) * sample_interval_seconds
    episode_values = series.iloc[start_position:end_position]
    qualifications: list[EpisodeQualification] = []

    if duration_seconds >= HEART_RATE_MIN_DURATION_SECONDS:
        qualifications.append("prolonged")

    severe_matches = (
        episode_values.gt(severe_threshold)
        if direction == "high"
        else episode_values.lt(severe_threshold)
    )
    severe_run_seconds = (
        _longest_true_run(severe_matches) * sample_interval_seconds
    )
    if severe_run_seconds >= SEVERE_HEART_RATE_MIN_DURATION_SECONDS:
        qualifications.append("severe_transient")

    if not qualifications:
        return

    extreme_value = (
        float(episode_values.max())
        if direction == "high"
        else float(episode_values.min())
    )
    episodes.append(
        AnomalyEpisode(
            anomaly_type=anomaly_type,
            signal="HR",
            start_seconds=start_position * sample_interval_seconds,
            end_seconds=end_position * sample_interval_seconds,
            duration_seconds=duration_seconds,
            extreme_value=extreme_value,
            threshold=threshold,
            qualifications=tuple(qualifications),
        )
    )


def detect_low_etco2(
    series: pd.Series,
    sample_interval_seconds: int = 1,
) -> list[AnomalyEpisode]:
    """Detect sustained or severe periods of low end-tidal carbon dioxide."""
    return _detect_etco2_anomaly(
        series,
        "low_etco2",
        LOW_ETCO2_THRESHOLD,
        SEVERE_LOW_ETCO2_THRESHOLD,
        "low",
        sample_interval_seconds,
    )


def detect_high_etco2(
    series: pd.Series,
    sample_interval_seconds: int = 1,
) -> list[AnomalyEpisode]:
    """Detect sustained or severe periods of high end-tidal carbon dioxide."""
    return _detect_etco2_anomaly(
        series,
        "high_etco2",
        HIGH_ETCO2_THRESHOLD,
        SEVERE_HIGH_ETCO2_THRESHOLD,
        "high",
        sample_interval_seconds,
    )


def _detect_etco2_anomaly(
    series: pd.Series,
    anomaly_type: Literal["low_etco2", "high_etco2"],
    threshold: float,
    severe_threshold: float,
    direction: Literal["high", "low"],
    sample_interval_seconds: int,
) -> list[AnomalyEpisode]:
    """Detect one type of abnormal end-tidal carbon-dioxide episode."""
    if sample_interval_seconds < 1:
        raise ValueError("sample_interval_seconds must be a positive integer")

    matches = (
        series.gt(threshold) if direction == "high" else series.lt(threshold)
    ) & series.notna()
    episodes: list[AnomalyEpisode] = []
    run_start: int | None = None

    for position, matches_rule in enumerate(matches):
        if matches_rule and run_start is None:
            run_start = position
        elif not matches_rule and run_start is not None:
            _append_etco2_episode(
                episodes,
                series,
                anomaly_type,
                threshold,
                severe_threshold,
                direction,
                run_start,
                position,
                sample_interval_seconds,
            )
            run_start = None

    if run_start is not None:
        _append_etco2_episode(
            episodes,
            series,
            anomaly_type,
            threshold,
            severe_threshold,
            direction,
            run_start,
            len(series),
            sample_interval_seconds,
        )

    return episodes


def _append_etco2_episode(
    episodes: list[AnomalyEpisode],
    series: pd.Series,
    anomaly_type: Literal["low_etco2", "high_etco2"],
    threshold: float,
    severe_threshold: float,
    direction: Literal["high", "low"],
    start_position: int,
    end_position: int,
    sample_interval_seconds: int,
) -> None:
    """Append one qualifying low- or high-end-tidal carbon-dioxide episode."""
    duration_seconds = (end_position - start_position) * sample_interval_seconds
    episode_values = series.iloc[start_position:end_position]
    qualifications: list[EpisodeQualification] = []

    if duration_seconds >= ETCO2_MIN_DURATION_SECONDS:
        qualifications.append("prolonged")

    severe_matches = (
        episode_values.gt(severe_threshold)
        if direction == "high"
        else episode_values.lt(severe_threshold)
    )
    severe_run_seconds = (
        _longest_true_run(severe_matches) * sample_interval_seconds
    )
    if severe_run_seconds >= SEVERE_ETCO2_MIN_DURATION_SECONDS:
        qualifications.append("severe_transient")

    if not qualifications:
        return

    extreme_value = (
        float(episode_values.max())
        if direction == "high"
        else float(episode_values.min())
    )
    episodes.append(
        AnomalyEpisode(
            anomaly_type=anomaly_type,
            signal="EtCO2",
            start_seconds=start_position * sample_interval_seconds,
            end_seconds=end_position * sample_interval_seconds,
            duration_seconds=duration_seconds,
            extreme_value=extreme_value,
            threshold=threshold,
            qualifications=tuple(qualifications),
        )
    )
