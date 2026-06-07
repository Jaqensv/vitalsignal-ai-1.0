"""Generate a deterministic, non-diagnostic French report."""

from dataclasses import dataclass

from vitalsignal.analysis.map_analysis import PointObservation
from vitalsignal.analysis.anomaly_rules import AnomalyEpisode
from vitalsignal.analysis.pipeline import InterventionAnalysis
from vitalsignal.analysis.scoring import PriorityScore, ScoreContribution


MEDICAL_WARNING = (
    "Ce prototype est destiné à un usage éducatif et démonstratif. "
    "Il ne constitue pas un dispositif médical et ne fournit pas de diagnostic. "
    "Les résultats doivent être interprétés par un professionnel de santé qualifié."
)

SIGNAL_LABELS = {
    "ART_MAP": "pression artérielle moyenne invasive",
    "NIBP_MAP": "pression artérielle moyenne non invasive",
    "HR": "fréquence cardiaque",
    "SpO2": "saturation périphérique en oxygène",
    "EtCO2": "dioxyde de carbone en fin d'expiration",
}

SIGNAL_SHORT_LABELS = {
    "ART_MAP": "ART_MAP (pression artérielle moyenne invasive)",
    "NIBP_MAP": "NIBP_MAP (pression artérielle moyenne non invasive)",
    "HR": "HR (fréquence cardiaque)",
    "SpO2": "SpO2 (saturation périphérique en oxygène)",
    "EtCO2": "EtCO2 (dioxyde de carbone en fin d'expiration)",
}

ANOMALY_LABELS = {
    "hypotension": "hypotension",
    "hypertension": "hypertension",
    "desaturation": "désaturation",
    "tachycardia": "tachycardie",
    "bradycardia": "bradycardie",
    "low_etco2": "EtCO2 bas",
    "high_etco2": "EtCO2 élevé",
}

QUALIFICATION_LABELS = {
    "prolonged": "prolongée",
    "severe_transient": "sévère transitoire",
}

PRIORITY_LABELS = {
    "none": "aucune",
    "low": "faible",
    "moderate": "modérée",
    "high": "élevée",
    "very_high": "très élevée",
}

CONTRIBUTION_LABELS = {
    "global_primary_episode": "épisode principal retenu",
    "additional_severe_signals": "signaux sévères supplémentaires",
    "anomaly_burden": "charge temporelle d'anomalie",
    "anomaly_burden_cap": "plafonnement de la charge temporelle",
    "point_observations": "observations ponctuelles de pression",
    "multi_signal": "atteinte de plusieurs signaux",
    "simultaneity": "anomalies simultanées",
}


@dataclass(frozen=True)
class TimelineEvent:
    """One chronological event already detected by deterministic rules."""

    start_seconds: int
    end_seconds: int | None
    description: str


@dataclass(frozen=True)
class SignalGroupSummary:
    """Descriptive anomaly summary for one measured signal."""

    signal: str
    episode_count: int
    point_observation_count: int
    extreme_value: float | None
    unit: str
    anomaly_types: tuple[str, ...]


def generate_local_report(
    analysis: InterventionAnalysis,
    score: PriorityScore,
) -> str:
    """Return a readable French report based only on deterministic results."""
    lines = [
        f"Intervention VitalDB : intervention n° {analysis.case_id}",
        f"Durée analysée : {_format_duration(analysis.duration_seconds)}",
        (
            f"Indice de priorité : {score.value}/100 "
            f"({PRIORITY_LABELS[score.level]})"
        ),
        "",
        "Résumé technique :",
        f"- Épisodes continus détectés : {len(_collect_episodes(analysis))}.",
        (
            "- Observations ponctuelles de pression : "
            f"{len(analysis.map_analysis.point_observations)}."
        ),
        (
            "- Signaux impliqués dans l'indice : "
            f"{_format_affected_signals(score.affected_signals)}."
        ),
        "",
        "Source de pression artérielle moyenne :",
        f"- {_format_map_source(analysis)}",
        "",
        "Exploitabilité des signaux :",
        *_format_signal_availability(analysis),
        "",
        "Anomalies et observations :",
    ]

    episodes = _collect_episodes(analysis)
    if not episodes and not analysis.map_analysis.point_observations:
        lines.append("- Aucune anomalie répondant aux règles définies n'a été détectée.")
    else:
        lines.extend(f"- {_format_episode(episode)}" for episode in episodes)
        lines.extend(
            (
                f"- Observation ponctuelle de "
                f"{SIGNAL_LABELS[observation.signal]} : {observation.value:g} mmHg "
                f"à {_format_duration(observation.time_seconds)}, "
                f"niveau {observation.severity}."
            )
            for observation in analysis.map_analysis.point_observations
        )

    timeline_events = build_timeline_events(analysis)
    if timeline_events:
        lines.extend(["", "Timeline des anomalies :"])
        lines.extend(f"- {_format_timeline_event(event)}" for event in timeline_events)

    signal_groups = build_signal_group_summaries(analysis)
    if signal_groups:
        lines.extend(["", "Regroupement par signal :"])
        lines.extend(f"- {_format_signal_group_summary(group)}" for group in signal_groups)

    if score.contributions:
        lines.extend(["", "Contributions de l'indice :"])
        lines.extend(f"- {_format_contribution(item)}" for item in score.contributions)

    unavailable = _unavailable_analyses(analysis)
    if unavailable:
        lines.extend(["", "Limites liées aux signaux :"])
        lines.extend(f"- {message}" for message in unavailable)

    lines.extend(
        [
            "",
            "Interprétation :",
            (
                "L'indice sert uniquement à prioriser la revue de l'intervention. "
                "Il ne mesure pas une gravité clinique et ne permet pas d'établir "
                "la cause des anomalies observées."
            ),
            "",
            "Avertissement médical :",
            MEDICAL_WARNING,
        ]
    )
    return "\n".join(lines)


def build_timeline_events(analysis: InterventionAnalysis) -> tuple[TimelineEvent, ...]:
    """Build a chronological timeline from detected episodes and observations."""
    events = [
        TimelineEvent(
            episode.start_seconds,
            episode.end_seconds,
            _format_episode(episode),
        )
        for episode in _collect_episodes(analysis)
    ]
    events.extend(
        TimelineEvent(
            observation.time_seconds,
            None,
            _format_point_observation(observation),
        )
        for observation in analysis.map_analysis.point_observations
    )
    return tuple(
        sorted(
            events,
            key=lambda event: (event.start_seconds, event.end_seconds or -1),
        )
    )


def build_signal_group_summaries(
    analysis: InterventionAnalysis,
) -> tuple[SignalGroupSummary, ...]:
    """Group detected anomalies by measured signal without adding diagnosis."""
    episodes_by_signal: dict[str, list[AnomalyEpisode]] = {}
    for episode in _collect_episodes(analysis):
        episodes_by_signal.setdefault(episode.signal, []).append(episode)

    observations_by_signal: dict[str, list[PointObservation]] = {}
    for observation in analysis.map_analysis.point_observations:
        observations_by_signal.setdefault(observation.signal, []).append(observation)

    groups = []
    for signal in sorted(set(episodes_by_signal) | set(observations_by_signal)):
        episodes = episodes_by_signal.get(signal, [])
        observations = observations_by_signal.get(signal, [])
        values = [episode.extreme_value for episode in episodes] + [
            observation.value for observation in observations
        ]
        groups.append(
            SignalGroupSummary(
                signal=signal,
                episode_count=len(episodes),
                point_observation_count=len(observations),
                extreme_value=_select_group_extreme(signal, values),
                unit=_signal_unit(signal),
                anomaly_types=tuple(
                    sorted({episode.anomaly_type for episode in episodes})
                ),
            )
        )
    return tuple(groups)


def _collect_episodes(analysis: InterventionAnalysis) -> tuple[AnomalyEpisode, ...]:
    """Collect all detected continuous episodes."""
    return (
        analysis.map_analysis.episodes
        + analysis.spo2_analysis.episodes
        + analysis.heart_rate_analysis.episodes
        + analysis.etco2_analysis.episodes
    )


def _format_episode(episode: AnomalyEpisode) -> str:
    """Format one episode without adding a medical interpretation."""
    qualifications = " et ".join(
        QUALIFICATION_LABELS[item] for item in episode.qualifications
    )
    unit = "%" if episode.signal == "SpO2" else (
        "bpm" if episode.signal == "HR" else "mmHg"
    )
    return (
        f"{ANOMALY_LABELS[episode.anomaly_type]} {qualifications} sur "
        f"{SIGNAL_SHORT_LABELS[episode.signal]} : durée "
        f"{_format_duration(episode.duration_seconds)}, valeur extrême "
        f"{episode.extreme_value:g} {unit}."
    )


def _format_point_observation(observation: PointObservation) -> str:
    """Format one intermittent pressure observation without inferring duration."""
    return (
        f"observation ponctuelle sur {SIGNAL_SHORT_LABELS[observation.signal]} : "
        f"{observation.value:g} mmHg, niveau {observation.severity}."
    )


def _format_timeline_event(event: TimelineEvent) -> str:
    """Format one timeline event with start and optional end time."""
    if event.end_seconds is None:
        return f"{_format_clock_time(event.start_seconds)} : {event.description}"
    return (
        f"{_format_clock_time(event.start_seconds)} -> "
        f"{_format_clock_time(event.end_seconds)} : {event.description}"
    )


def _format_signal_group_summary(group: SignalGroupSummary) -> str:
    """Format one grouped signal summary in non-diagnostic language."""
    parts = []
    if group.episode_count:
        episode_word = "épisode continu" if group.episode_count == 1 else "épisodes continus"
        parts.append(f"{group.episode_count} {episode_word}")
    if group.point_observation_count:
        observation_word = (
            "observation ponctuelle"
            if group.point_observation_count == 1
            else "observations ponctuelles"
        )
        parts.append(f"{group.point_observation_count} {observation_word}")
    if not parts:
        parts.append("aucune anomalie détectée")

    anomaly_text = ""
    if group.anomaly_types:
        labels = ", ".join(ANOMALY_LABELS[item] for item in group.anomaly_types)
        anomaly_text = f" ({labels})"

    extreme_text = ""
    if group.extreme_value is not None:
        extreme_text = f", valeur extrême {group.extreme_value:g} {group.unit}"

    return (
        f"{SIGNAL_SHORT_LABELS[group.signal]} : "
        f"{' et '.join(parts)}{anomaly_text}{extreme_text}."
    )


def _select_group_extreme(signal: str, values: list[float]) -> float | None:
    """Select the most relevant extreme value for display."""
    if not values:
        return None
    if signal in ("ART_MAP", "NIBP_MAP", "SpO2", "EtCO2"):
        return min(values)
    if signal == "HR":
        return max(values, key=lambda value: abs(value - 80))
    return values[0]


def _signal_unit(signal: str) -> str:
    """Return the display unit for one signal."""
    if signal == "SpO2":
        return "%"
    if signal == "HR":
        return "bpm"
    return "mmHg"


def _format_affected_signals(signals: tuple[str, ...]) -> str:
    """Format affected signals with their medical meaning."""
    if not signals:
        return "aucun"
    return ", ".join(SIGNAL_SHORT_LABELS.get(signal, signal) for signal in signals)


def _format_map_source(analysis: InterventionAnalysis) -> str:
    """Describe which pressure source was used and how it was interpreted."""
    if analysis.map_analysis.source is None:
        return "aucune source exploitable pour MAP (pression artérielle moyenne)."
    mode = (
        "analyse continue"
        if analysis.map_analysis.status == "continuous"
        else "observations ponctuelles sans inférer la durée"
    )
    return f"{SIGNAL_SHORT_LABELS[analysis.map_analysis.source]} utilisée en {mode}."


def _format_signal_availability(analysis: InterventionAnalysis) -> list[str]:
    """Summarize analyzable duration and analysis status per priority signal."""
    lines = []
    for signal, status, reason in (
        (
            analysis.map_analysis.source or "ART_MAP",
            analysis.map_analysis.status,
            None if analysis.map_analysis.status != "unavailable" else "absent",
        ),
        ("SpO2", analysis.spo2_analysis.status, analysis.spo2_analysis.reason),
        ("HR", analysis.heart_rate_analysis.status, analysis.heart_rate_analysis.reason),
        ("EtCO2", analysis.etco2_analysis.status, analysis.etco2_analysis.reason),
    ):
        analyzable_seconds = analysis.analyzable_seconds.get(signal, 0)
        label = SIGNAL_SHORT_LABELS.get(signal, signal)
        if status in ("continuous", "intermittent", "analyzed"):
            lines.append(
                f"- {label} : exploitable, "
                f"{_format_duration(analyzable_seconds)} analysable."
            )
        else:
            lines.append(f"- {label} : non exploitable (raison : {reason}).")
    return lines


def _format_contribution(contribution: ScoreContribution) -> str:
    """Format one score contribution in French."""
    label = CONTRIBUTION_LABELS.get(contribution.category, contribution.category)
    points = "point" if abs(contribution.points) == 1 else "points"
    return f"{label} : {contribution.points:+d} {points}."


def _unavailable_analyses(analysis: InterventionAnalysis) -> list[str]:
    """Describe analyses that could not be performed reliably."""
    messages: list[str] = []

    if analysis.map_analysis.status == "unavailable":
        messages.append("Analyse de la pression artérielle moyenne impossible.")

    signal_analyses = (
        ("SpO2", analysis.spo2_analysis),
        ("HR", analysis.heart_rate_analysis),
        ("EtCO2", analysis.etco2_analysis),
    )
    for signal, signal_analysis in signal_analyses:
        if signal_analysis.status != "analyzed":
            messages.append(
                f"Analyse de {SIGNAL_LABELS[signal]} impossible ou non fiable "
                f"(raison : {signal_analysis.reason})."
            )

    return messages


def _format_duration(seconds: int) -> str:
    """Format a duration using hours, minutes and seconds."""
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} h")
    if minutes:
        parts.append(f"{minutes} min")
    if remaining_seconds or not parts:
        parts.append(f"{remaining_seconds} s")
    return " ".join(parts)


def _format_clock_time(seconds: int) -> str:
    """Format seconds from recording start as HH:MM:SS."""
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
