"""Compute an explainable technical priority score."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from vitalsignal.analysis.anomaly_rules import AnomalyEpisode
from vitalsignal.analysis.map_analysis import PointObservation
from vitalsignal.analysis.pipeline import InterventionAnalysis


PriorityLevel = Literal["none", "low", "moderate", "high", "very_high"]

EPISODE_BASE_POINTS = {
    ("prolonged",): 10,
    ("severe_transient",): 15,
    ("prolonged", "severe_transient"): 20,
}
GLOBAL_PRIMARY_EPISODE_BONUS = 5
ADDITIONAL_SEVERE_SIGNAL_POINTS = 5
MAX_ADDITIONAL_SEVERE_SIGNAL_POINTS = 15
BURDEN_POINTS_PER_SIGNAL = 10
MAX_BURDEN_POINTS = 20
STANDARD_POINT_OBSERVATION_POINTS = 2
SEVERE_POINT_OBSERVATION_POINTS = 5
MAX_POINT_OBSERVATION_POINTS = 5
MULTI_SIGNAL_POINTS = 3
MAX_MULTI_SIGNAL_POINTS = 10
SIMULTANEOUS_SIGNAL_POINTS = 7
MAX_SIMULTANEITY_POINTS = 20


@dataclass(frozen=True)
class ScoreContribution:
    """One explainable contribution to the priority score."""

    category: str
    points: int
    description: str


@dataclass(frozen=True)
class PriorityScore:
    """Technical priority score and its complete explanation."""

    value: int
    level: PriorityLevel
    affected_signals: tuple[str, ...]
    contributions: tuple[ScoreContribution, ...]


def calculate_priority_score(analysis: InterventionAnalysis) -> PriorityScore:
    """Calculate a duration-aware bounded score from deterministic results."""
    episodes = _collect_episodes(analysis)
    episodes_by_signal = _episodes_by_signal(episodes)
    contributions: list[ScoreContribution] = []

    primary_by_signal = {
        signal: max(
            signal_episodes,
            key=lambda episode: (
                EPISODE_BASE_POINTS[episode.qualifications],
                episode.duration_seconds,
            ),
        )
        for signal, signal_episodes in episodes_by_signal.items()
    }
    if primary_by_signal:
        global_primary = max(
            primary_by_signal.values(),
            key=lambda episode: (
                EPISODE_BASE_POINTS[episode.qualifications],
                episode.duration_seconds,
            ),
        )
        points = min(
            EPISODE_BASE_POINTS[global_primary.qualifications]
            + GLOBAL_PRIMARY_EPISODE_BONUS,
            25,
        )
        contributions.append(
            ScoreContribution(
                category="global_primary_episode",
                points=points,
                description=(
                    f"Most important episode on {global_primary.signal}: "
                    f"{global_primary.anomaly_type}, "
                    f"{', '.join(global_primary.qualifications)}"
                ),
            )
        )

    additional_severe_signals = sum(
        "severe_transient" in episode.qualifications
        for signal, episode in primary_by_signal.items()
        if signal != global_primary.signal
    ) if primary_by_signal else 0
    additional_severe_points = min(
        additional_severe_signals * ADDITIONAL_SEVERE_SIGNAL_POINTS,
        MAX_ADDITIONAL_SEVERE_SIGNAL_POINTS,
    )
    if additional_severe_points:
        contributions.append(
            ScoreContribution(
                category="additional_severe_signals",
                points=additional_severe_points,
                description=(
                    f"{additional_severe_signals} additional signals contain "
                    "a severe transient episode"
                ),
            )
        )

    burden_contributions = _score_anomaly_burden(
        episodes_by_signal,
        analysis.analyzable_seconds,
    )
    contributions.extend(burden_contributions)

    point_contribution = _score_point_observations(
        analysis.map_analysis.point_observations
    )
    if point_contribution is not None:
        contributions.append(point_contribution)

    affected_signals = set(episodes_by_signal) | {
        observation.signal
        for observation in analysis.map_analysis.point_observations
    }
    multi_signal_points = min(
        max(0, len(affected_signals) - 1) * MULTI_SIGNAL_POINTS,
        MAX_MULTI_SIGNAL_POINTS,
    )
    if multi_signal_points:
        contributions.append(
            ScoreContribution(
                category="multi_signal",
                points=multi_signal_points,
                description=f"{len(affected_signals)} signals contain anomalies",
            )
        )

    max_simultaneous_signals = _max_simultaneous_signals(episodes)
    simultaneity_points = min(
        max(0, max_simultaneous_signals - 1) * SIMULTANEOUS_SIGNAL_POINTS,
        MAX_SIMULTANEITY_POINTS,
    )
    if simultaneity_points:
        contributions.append(
            ScoreContribution(
                category="simultaneity",
                points=simultaneity_points,
                description=(
                    f"Anomalies overlap on {max_simultaneous_signals} signals"
                ),
            )
        )

    value = min(sum(item.points for item in contributions), 100)
    return PriorityScore(
        value=value,
        level=_priority_level(value),
        affected_signals=tuple(sorted(affected_signals)),
        contributions=tuple(contributions),
    )


def _collect_episodes(analysis: InterventionAnalysis) -> tuple[AnomalyEpisode, ...]:
    """Collect all continuous episodes without modifying them."""
    return (
        analysis.map_analysis.episodes
        + analysis.spo2_analysis.episodes
        + analysis.heart_rate_analysis.episodes
        + analysis.etco2_analysis.episodes
    )


def _episodes_by_signal(
    episodes: tuple[AnomalyEpisode, ...],
) -> dict[str, list[AnomalyEpisode]]:
    """Group episodes by their measured signal."""
    grouped: dict[str, list[AnomalyEpisode]] = defaultdict(list)
    for episode in episodes:
        grouped[episode.signal].append(episode)
    return dict(grouped)


def _score_anomaly_burden(
    episodes_by_signal: dict[str, list[AnomalyEpisode]],
    analyzable_seconds: dict[str, int],
) -> list[ScoreContribution]:
    """Score anomaly duration relative to each signal's analyzable duration."""
    contributions: list[ScoreContribution] = []
    total_points = 0

    for signal, episodes in episodes_by_signal.items():
        available_seconds = analyzable_seconds.get(signal, 0)
        if available_seconds <= 0:
            continue

        anomalous_seconds = _union_duration(episodes)
        ratio = min(anomalous_seconds / available_seconds, 1.0)
        points = round(ratio * BURDEN_POINTS_PER_SIGNAL)
        if not points:
            continue

        total_points += points
        contributions.append(
            ScoreContribution(
                category="anomaly_burden",
                points=points,
                description=(
                    f"{signal} anomaly burden: {anomalous_seconds}/"
                    f"{available_seconds} seconds ({ratio:.1%})"
                ),
            )
        )

    if total_points > MAX_BURDEN_POINTS:
        contributions.append(
            ScoreContribution(
                category="anomaly_burden_cap",
                points=MAX_BURDEN_POINTS - total_points,
                description="Anomaly burden contributions capped at 20 points",
            )
        )

    return contributions


def _union_duration(episodes: list[AnomalyEpisode]) -> int:
    """Return total episode duration without double-counting overlaps."""
    intervals = sorted((episode.start_seconds, episode.end_seconds) for episode in episodes)
    total = 0
    current_start: int | None = None
    current_end: int | None = None

    for start, end in intervals:
        if current_start is None:
            current_start, current_end = start, end
        elif start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end

    if current_start is not None and current_end is not None:
        total += current_end - current_start
    return total


def _max_simultaneous_signals(episodes: tuple[AnomalyEpisode, ...]) -> int:
    """Return the maximum number of distinct signals abnormal at once."""
    events: list[tuple[int, int, str]] = []
    for episode in episodes:
        events.append((episode.start_seconds, 1, episode.signal))
        events.append((episode.end_seconds, -1, episode.signal))

    active_counts: dict[str, int] = defaultdict(int)
    maximum = 0
    for _, event_type, signal in sorted(events, key=lambda event: (event[0], event[1])):
        active_counts[signal] += event_type
        if active_counts[signal] == 0:
            del active_counts[signal]
        maximum = max(maximum, len(active_counts))
    return maximum


def _score_point_observations(
    observations: tuple[PointObservation, ...],
) -> ScoreContribution | None:
    """Score intermittent pressure observations with a conservative cap."""
    points = sum(
        SEVERE_POINT_OBSERVATION_POINTS
        if observation.severity == "severe"
        else STANDARD_POINT_OBSERVATION_POINTS
        for observation in observations
    )
    points = min(points, MAX_POINT_OBSERVATION_POINTS)
    if not points:
        return None
    return ScoreContribution(
        category="point_observations",
        points=points,
        description=f"{len(observations)} abnormal intermittent MAP observations",
    )


def _priority_level(value: int) -> PriorityLevel:
    """Map the numeric technical score to a readable priority level."""
    if value == 0:
        return "none"
    if value < 25:
        return "low"
    if value < 50:
        return "moderate"
    if value < 75:
        return "high"
    return "very_high"
