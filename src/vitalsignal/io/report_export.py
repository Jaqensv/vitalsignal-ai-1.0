"""Export deterministic intervention results to JSON-compatible data and Markdown."""

from dataclasses import asdict
from typing import Any

from vitalsignal.io.local_report import (
    MEDICAL_WARNING,
    PRIORITY_LABELS,
    _collect_episodes,
    _format_affected_signals,
    _format_contribution,
    _format_duration,
    _format_episode,
    _format_map_source,
    _format_signal_availability,
    _format_timeline_event,
    _format_signal_group_summary,
    _unavailable_analyses,
    build_signal_group_summaries,
    build_timeline_events,
)
from vitalsignal.analysis.pipeline import InterventionAnalysis
from vitalsignal.analysis.scoring import PriorityScore, ScoreContribution


def build_report_data(
    analysis: InterventionAnalysis,
    score: PriorityScore,
) -> dict[str, Any]:
    """Build JSON-compatible structured report data."""
    timeline_events = build_timeline_events(analysis)
    signal_groups = build_signal_group_summaries(analysis)
    return {
        "case_id": analysis.case_id,
        "analysis": asdict(analysis),
        "priority_score": asdict(score),
        "timeline": [
            {
                "start_seconds": event.start_seconds,
                "end_seconds": event.end_seconds,
                "text": _format_timeline_event(event),
            }
            for event in timeline_events
        ],
        "signal_groups": [
            {
                "signal": group.signal,
                "episode_count": group.episode_count,
                "point_observation_count": group.point_observation_count,
                "extreme_value": group.extreme_value,
                "unit": group.unit,
                "anomaly_types": list(group.anomaly_types),
                "text": _format_signal_group_summary(group),
            }
            for group in signal_groups
        ],
        "medical_warning": (
            "Ce prototype est destiné à un usage éducatif et démonstratif. "
            "Il ne constitue pas un dispositif médical et ne fournit pas de diagnostic."
        ),
        "context_limitations": [
            "Le contexte clinique complet n'est pas disponible.",
            "Les causes des anomalies détectées ne peuvent pas être établies.",
            "Les données VitalDB proviennent d'un centre hospitalier sud-coréen.",
        ],
    }


def build_markdown_report(
    analysis: InterventionAnalysis,
    score: PriorityScore,
) -> str:
    """Build a structured Markdown report from deterministic results."""
    episodes = _collect_episodes(analysis)
    lines = [
        "# Rapport VitalSignal AI",
        "",
        "## Synthèse",
        "",
        f"- Intervention VitalDB : intervention n° `{analysis.case_id}`",
        f"- Durée analysée : {_format_duration(analysis.duration_seconds)}",
        (
            f"- Indice de priorité : **{score.value}/100** "
            f"({PRIORITY_LABELS[score.level]})"
        ),
        (
            "- Signaux impliqués dans l'indice : "
            f"{_format_affected_signals(score.affected_signals)}"
        ),
        "",
        "## Source de pression artérielle moyenne",
        "",
        f"- {_format_map_source(analysis)}",
        "",
        "## Exploitabilité des signaux",
        "",
        *_format_signal_availability(analysis),
        "",
        "## Anomalies et observations",
        "",
    ]

    if not episodes and not analysis.map_analysis.point_observations:
        lines.append("- Aucune anomalie répondant aux règles définies n'a été détectée.")
    else:
        lines.extend(f"- {_format_episode(episode)}" for episode in episodes)
        lines.extend(
            (
                "- Observation ponctuelle de pression artérielle moyenne : "
                f"{observation.value:g} mmHg à "
                f"{_format_duration(observation.time_seconds)}, "
                f"niveau {observation.severity}."
            )
            for observation in analysis.map_analysis.point_observations
        )

    timeline_events = build_timeline_events(analysis)
    if timeline_events:
        lines.extend(["", "## Timeline des anomalies", ""])
        lines.extend(f"- {_format_timeline_event(event)}" for event in timeline_events)

    signal_groups = build_signal_group_summaries(analysis)
    if signal_groups:
        lines.extend(["", "## Regroupement par signal", ""])
        lines.extend(
            f"- {_format_signal_group_summary(group)}" for group in signal_groups
        )

    if score.contributions:
        lines.extend(
            [
                "",
                "## Contributions de l'indice",
                "",
                "| Contribution | Points |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            _format_markdown_contribution(contribution)
            for contribution in score.contributions
        )

    unavailable = _unavailable_analyses(analysis)
    if unavailable:
        lines.extend(["", "## Limites liées aux signaux", ""])
        lines.extend(f"- {message}" for message in unavailable)

    lines.extend(
        [
            "",
            "## Interprétation",
            "",
            (
                "L'indice sert uniquement à prioriser la revue de l'intervention. "
                "Il ne mesure pas une gravité clinique et ne permet pas d'établir "
                "la cause des anomalies observées."
            ),
            "",
            "## Avertissement médical",
            "",
            MEDICAL_WARNING,
        ]
    )
    return "\n".join(lines)


def _format_markdown_contribution(contribution: ScoreContribution) -> str:
    """Format one score contribution as a Markdown table row."""
    text = _format_contribution(contribution)
    label, points = text.rsplit(" : ", 1)
    return f"| {label} | {points.removesuffix('.')} |"
