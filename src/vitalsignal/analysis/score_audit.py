"""Build structured records and summaries for technical score calibration."""

from collections import Counter
from dataclasses import asdict
from statistics import mean, median
from typing import Any

from vitalsignal.analysis.pipeline import InterventionAnalysis
from vitalsignal.analysis.scoring import PriorityScore


def build_audit_record(
    analysis: InterventionAnalysis,
    score: PriorityScore,
) -> dict[str, Any]:
    """Build one JSON-compatible record for a scored intervention."""
    episodes = (
        analysis.map_analysis.episodes
        + analysis.spo2_analysis.episodes
        + analysis.heart_rate_analysis.episodes
        + analysis.etco2_analysis.episodes
    )
    episode_counts = Counter(episode.anomaly_type for episode in episodes)
    contribution_points = Counter()
    for contribution in score.contributions:
        contribution_points[contribution.category] += contribution.points

    return {
        "case_id": analysis.case_id,
        "duration_seconds": analysis.duration_seconds,
        "score": score.value,
        "level": score.level,
        "affected_signals": list(score.affected_signals),
        "analyzable_seconds": analysis.analyzable_seconds,
        "episode_counts": dict(episode_counts),
        "contribution_points": dict(contribution_points),
        "map_status": analysis.map_analysis.status,
        "spo2_status": analysis.spo2_analysis.status,
        "heart_rate_status": analysis.heart_rate_analysis.status,
        "etco2_status": analysis.etco2_analysis.status,
    }


def summarize_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize score distribution and dominant technical contributions."""
    if not records:
        raise ValueError("records must not be empty")

    scores = [record["score"] for record in records]
    durations = [record["duration_seconds"] for record in records]
    levels = Counter(record["level"] for record in records)
    contribution_totals = Counter()
    episode_totals = Counter()

    for record in records:
        contribution_totals.update(record["contribution_points"])
        episode_totals.update(record["episode_counts"])

    return {
        "case_count": len(records),
        "score": {
            "minimum": min(scores),
            "maximum": max(scores),
            "mean": round(mean(scores), 2),
            "median": median(scores),
            "count_at_100": scores.count(100),
            "count_at_0": scores.count(0),
        },
        "duration_seconds": {
            "minimum": min(durations),
            "maximum": max(durations),
            "mean": round(mean(durations), 2),
        },
        "level_counts": dict(levels),
        "episode_totals": dict(episode_totals),
        "contribution_totals": dict(contribution_totals),
    }

