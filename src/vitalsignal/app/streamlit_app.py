"""Minimal Streamlit interface for VitalSignal AI."""

from collections import Counter
from html import escape

import pandas as pd

from vitalsignal.analysis.case_search import SearchResult, search_interventions
from vitalsignal.analysis.anomaly_rules import (
    BRADYCARDIA_THRESHOLD,
    DESATURATION_THRESHOLD,
    HIGH_ETCO2_THRESHOLD,
    HYPERTENSION_THRESHOLD,
    HYPOTENSION_THRESHOLD,
    LOW_ETCO2_THRESHOLD,
    SEVERE_BRADYCARDIA_THRESHOLD,
    SEVERE_DESATURATION_THRESHOLD,
    SEVERE_HIGH_ETCO2_THRESHOLD,
    SEVERE_HYPERTENSION_THRESHOLD,
    SEVERE_HYPOTENSION_THRESHOLD,
    SEVERE_LOW_ETCO2_THRESHOLD,
    SEVERE_TACHYCARDIA_THRESHOLD,
    TACHYCARDIA_THRESHOLD,
)
from vitalsignal.analysis.pipeline import InterventionAnalysis
from vitalsignal.analysis.preprocessing import clean_impossible_values
from vitalsignal.app.main import run_case_analysis_with_frame
from vitalsignal.io.ai_report import has_openai_api_key
from vitalsignal.io.local_report import (
    ANOMALY_LABELS,
    MEDICAL_WARNING,
    PRIORITY_LABELS,
    _format_duration,
)
from vitalsignal.io.report_export import build_markdown_report, build_report_data
from vitalsignal.io.vitaldb_loader import DEFAULT_CACHE_DIR, VitalDBCaseAccessError, _cache_path


ANALYSIS_INTERVAL_SECONDS = 2
SEARCH_SCAN_INTERVAL_SECONDS = 2
SEARCH_MAX_CASES = 50


def main() -> None:
    """Render the Streamlit application."""
    import streamlit as st

    st.set_page_config(page_title="VitalSignal AI", layout="wide")
    _apply_pending_case_open(st)
    _inject_theme(st)
    st.sidebar.markdown(
        """
        <div class="vs-sidebar-brand">
          <div class="vs-logo">VS</div>
          <div>
            <h2>VitalSignal</h2>
            <p>Dashboard clinique éducatif</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    mode = st.sidebar.radio(
        "Navigation",
        ["Analyser une intervention", "Rechercher des anomalies"],
        key="navigation_mode",
    )

    st.markdown(
        """
        <section class="vs-hero">
          <div>
            <p class="vs-kicker">Monitoring peropératoire</p>
            <h1>VitalSignal AI</h1>
            <p>Priorisation déterministe et synthèse prudente des constantes VitalDB.</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.warning(MEDICAL_WARNING)

    if mode == "Analyser une intervention":
        _render_case_analysis_tab(st)
    else:
        _render_search_tab(st)


def _render_case_analysis_tab(st) -> None:
    """Render detailed analysis for one case_id."""
    selected_case_id = max(1, int(st.session_state.get("selected_case_id", 1)))
    st.sidebar.markdown("### Analyse")
    case_id_input = st.sidebar.text_input(
        "Identifiant d'intervention VitalDB",
        value=str(selected_case_id),
        key="analysis_case_id",
    )
    st.sidebar.caption(
        "Intervalle d'analyse : "
        f"{ANALYSIS_INTERVAL_SECONDS} seconde(s), fixé pour garder des résultats comparables."
    )
    has_api_key = has_openai_api_key()
    use_ai = st.sidebar.checkbox(
        "Activer la synthèse IA",
        value=False,
        disabled=not has_api_key,
    )
    if not has_api_key:
        st.sidebar.caption(_missing_openai_key_message())
    analyze_clicked = st.sidebar.button("Analyser l'intervention", use_container_width=True)

    if not analyze_clicked:
        st.markdown(
            """
            <div class="vs-empty-state">
              <h3>Analyse en attente</h3>
              <p>Choisis un identifiant d'intervention dans la barre latérale, puis lance l'analyse.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    case_id, validation_error = _parse_intervention_id(case_id_input)
    if validation_error is not None:
        st.error(validation_error)
        return

    cached_before_analysis = _is_cached_intervention(case_id, ANALYSIS_INTERVAL_SECONDS)
    try:
        raw_frame, analysis, score, report, ai_summary = run_case_analysis_with_frame(
            case_id,
            ANALYSIS_INTERVAL_SECONDS,
            use_ai=use_ai,
        )
    except VitalDBCaseAccessError as error:
        st.error(f"Intervention non accessible : {error}")
        return
    except (OSError, ValueError) as error:
        st.error(f"Analyse impossible : {error}")
        return

    report_data = build_report_data(analysis, score)
    signal_count = len(report_data["signal_groups"])
    st.caption(_data_source_message(cached_before_analysis))

    st.markdown("<h2 class='vs-section-title'>Vue d'ensemble</h2>", unsafe_allow_html=True)
    score_column, duration_column, event_column, signal_column = st.columns(4)
    score_column.markdown(
        _metric_card_html(
            "Indice de priorité",
            f"{score.value}/100",
            PRIORITY_LABELS[score.level],
            _priority_color(score.level),
        ),
        unsafe_allow_html=True,
    )
    duration_column.markdown(
        _metric_card_html(
            "Durée analysée",
            _format_duration(analysis.duration_seconds),
            f"intervention n° {analysis.case_id}",
            "#57e6c4",
        ),
        unsafe_allow_html=True,
    )
    event_column.markdown(
        _metric_card_html(
            "Épisodes détectés",
            str(len(report_data["timeline"])),
            "timeline déterministe",
            "#57e6c4",
        ),
        unsafe_allow_html=True,
    )
    signal_column.markdown(
        _metric_card_html(
            "Signaux concernés",
            str(signal_count),
            "avec anomalie détectée",
            "#57e6c4",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(_format_score_explanation(score.value, score.level), unsafe_allow_html=True)
    _render_stability_charts(st, raw_frame, analysis)

    if ai_summary is not None:
        st.markdown("<h2 class='vs-section-title'>Synthèse IA</h2>", unsafe_allow_html=True)
        if not ai_summary.used_ai:
            st.info(f"Synthèse locale utilisée : {ai_summary.fallback_reason}")
        st.markdown(
            f"<div class='vs-card vs-ai'>{_format_ai_summary_for_display(report)}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<h2 class='vs-section-title'>Lecture rapide</h2>", unsafe_allow_html=True)
    if report_data["timeline"]:
        st.markdown("**Principaux événements chronologiques détectés**")
        for event in report_data["timeline"][:5]:
            st.markdown(_event_card_html(event["text"]), unsafe_allow_html=True)
        if len(report_data["timeline"]) > 5:
            st.caption(
                f"{len(report_data['timeline']) - 5} événement(s) supplémentaire(s) "
                "dans le détail chronologique."
            )
    else:
        st.write("Aucune anomalie détectée dans la timeline.")

    if report_data["signal_groups"]:
        st.markdown("**Signaux concernés**")
        for group in report_data["signal_groups"]:
            st.markdown(_signal_card_html(group["text"]), unsafe_allow_html=True)

    with st.expander("Détail chronologique complet"):
        if report_data["timeline"]:
            for event in report_data["timeline"]:
                st.write(f"- {event['text']}")
        else:
            st.write("Aucune anomalie dans la timeline.")

    with st.expander("Exploitabilité des signaux"):
        for signal, seconds in analysis.analyzable_seconds.items():
            st.write(f"- {signal} : {_format_duration(seconds)} analysable(s)")

    with st.expander("Rapport déterministe complet"):
        st.markdown(build_markdown_report(analysis, score))

    st.markdown("<h2 class='vs-section-title'>Exports</h2>", unsafe_allow_html=True)
    st.download_button(
        "Télécharger le rapport Markdown",
        data=build_markdown_report(analysis, score),
        file_name=f"vitalsignal_intervention_{analysis.case_id}.md",
        mime="text/markdown",
    )

    st.download_button(
        "Télécharger le rapport JSON",
        data=_json_report(report_data),
        file_name=f"vitalsignal_intervention_{analysis.case_id}.json",
        mime="application/json",
    )


def _render_search_tab(st) -> None:
    """Render deterministic multi-case search."""
    st.sidebar.markdown("### Recherche")
    start_case_id_input = st.sidebar.text_input(
        "Première intervention",
        value="1",
        key="search_start_case_id",
    )
    end_case_id_input = st.sidebar.text_input(
        "Dernière intervention incluse",
        value="5",
        key="search_end_case_id",
    )
    st.sidebar.caption(
        "Intervalle du scan multi-cas : "
        f"{SEARCH_SCAN_INTERVAL_SECONDS} seconde(s), fixé pour rendre les résultats comparables."
    )
    st.sidebar.caption(
        f"Limite de sécurité : {SEARCH_MAX_CASES} interventions maximum par scan."
    )
    anomaly_filter = st.sidebar.selectbox(
        "Anomalie recherchée",
        options=list(_anomaly_filter_options().keys()),
        format_func=lambda value: _anomaly_filter_options()[value],
        index=0,
    )
    search_clicked = st.sidebar.button("Scanner les interventions", use_container_width=True)

    if not search_clicked:
        st.markdown(
            """
            <div class="vs-empty-state">
              <h3>Recherche en attente</h3>
              <p>Définis une plage d'interventions dans la barre latérale, puis lance le scan.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    start_case_id, end_case_id, validation_error = _parse_intervention_range(
        start_case_id_input,
        end_case_id_input,
    )
    if validation_error is not None:
        st.error(validation_error)
        return

    case_ids = list(range(start_case_id, end_case_id + 1))
    if len(case_ids) > SEARCH_MAX_CASES:
        st.error(
            "Scan refusé : "
            f"{len(case_ids)} interventions demandées, limite actuelle {SEARCH_MAX_CASES}. "
            "Réduis la plage pour éviter un chargement VitalDB trop long."
        )
        return

    cached_count = _cached_intervention_count(case_ids, SEARCH_SCAN_INTERVAL_SECONDS)
    progress_bar = st.progress(0)
    progress_text = st.empty()

    def update_progress(scanned: int, total: int, current_case_id: int) -> None:
        progress_bar.progress(scanned / total)
        progress_text.caption(
            f"Scan en cours : intervention {current_case_id} "
            f"({scanned}/{total})"
        )

    try:
        results = search_interventions(
            case_ids,
            anomaly_filter=anomaly_filter,
            interval=SEARCH_SCAN_INTERVAL_SECONDS,
            progress_callback=update_progress,
        )
    except VitalDBCaseAccessError as error:
        st.error(f"Recherche interrompue : {error}")
        return
    except (OSError, ValueError) as error:
        st.error(f"Recherche impossible : {error}")
        return
    finally:
        progress_bar.empty()
        progress_text.empty()

    st.caption(_multi_case_data_source_message(cached_count, len(case_ids)))
    rows = build_search_rows(results)
    if not rows:
        st.write("Aucune intervention correspondante.")
        return

    _render_anomaly_frequency_chart(st, results, scanned_count=len(case_ids))
    st.markdown(_search_table_html(rows), unsafe_allow_html=True)
    _render_search_actions(st, rows)


def _missing_openai_key_message() -> str:
    """Return the sidebar helper text shown when no OpenAI key is configured."""
    return "Veuillez entrer votre clé API OpenAI dans `.env` pour activer la synthèse IA."


def _is_cached_intervention(case_id: int, interval: int) -> bool:
    """Return whether one intervention is already available in the local cache."""
    cache_path = _cache_path(case_id, interval, DEFAULT_CACHE_DIR)
    return cache_path is not None and cache_path.exists()


def _cached_intervention_count(case_ids: list[int], interval: int) -> int:
    """Return how many requested interventions are already cached locally."""
    return sum(1 for case_id in case_ids if _is_cached_intervention(case_id, interval))


def _data_source_message(was_cached: bool) -> str:
    """Return the user-facing data source message for one analysis."""
    if was_cached:
        return "Source des données : cache local `cases/`."
    return "Source des données : VitalDB. Une copie locale a été enregistrée dans `cases/`."


def _multi_case_data_source_message(cached_count: int, total_count: int) -> str:
    """Return the user-facing data source message for one multi-case scan."""
    downloaded_count = max(total_count - cached_count, 0)
    if downloaded_count == 0:
        return (
            "Source des données : cache local `cases/` "
            f"({cached_count}/{total_count} interventions)."
        )
    if cached_count == 0:
        return (
            "Source des données : VitalDB. "
            f"{downloaded_count}/{total_count} interventions ont été téléchargées puis mises en cache."
        )
    return (
        "Source des données : cache local et VitalDB. "
        f"{cached_count}/{total_count} interventions déjà en cache ; "
        f"{downloaded_count}/{total_count} téléchargées puis mises en cache."
    )


def _render_search_actions(st, rows: list[dict[str, str | int]]) -> None:
    """Render actions to select one case from search results."""
    st.markdown("**Ouvrir une intervention**")
    for row in rows:
        if st.button(f"Ouvrir intervention {row['case_id']}", key=f"open_case_{row['case_id']}"):
            st.session_state["pending_open_case_id"] = int(row["case_id"])
            if hasattr(st, "rerun"):
                st.rerun()
            st.success("Intervention sélectionnée.")


def _render_search_results(st, rows: list[dict[str, str | int]]) -> None:
    """Compatibility wrapper for older tests around search actions."""
    _render_search_actions(st, rows)


def _apply_pending_case_open(st) -> None:
    """Apply a requested case opening before Streamlit widgets are created."""
    pending_case_id = st.session_state.pop("pending_open_case_id", None)
    if pending_case_id is None:
        return

    selected_case_id = int(pending_case_id)
    st.session_state["selected_case_id"] = selected_case_id
    st.session_state["analysis_case_id"] = str(selected_case_id)
    st.session_state["navigation_mode"] = "Analyser une intervention"


def _parse_intervention_id(raw_value: str) -> tuple[int | None, str | None]:
    """Parse one user-entered intervention identifier."""
    value = raw_value.strip()
    if not value:
        return None, "Identifiant d'intervention invalide : saisis un entier supérieur ou égal à 1."
    try:
        case_id = int(value)
    except ValueError:
        return None, "Identifiant d'intervention invalide : saisis un nombre entier."
    return case_id, _validate_intervention_id(case_id)


def _parse_intervention_range(
    raw_start: str,
    raw_end: str,
) -> tuple[int | None, int | None, str | None]:
    """Parse the user-entered multi-case search range."""
    start_case_id, start_error = _parse_intervention_id(raw_start)
    end_case_id, end_error = _parse_intervention_id(raw_end)
    if start_error is not None or end_error is not None:
        return None, None, "Plage d'interventions invalide : les identifiants doivent être des entiers supérieurs ou égaux à 1."
    assert start_case_id is not None
    assert end_case_id is not None
    return start_case_id, end_case_id, _validate_intervention_range(start_case_id, end_case_id)


def _validate_intervention_id(case_id: int) -> str | None:
    """Return a user-facing error when one intervention identifier is invalid."""
    if case_id < 1:
        return "Identifiant d'intervention invalide : saisis un entier supérieur ou égal à 1."
    return None


def _validate_intervention_range(start_case_id: int, end_case_id: int) -> str | None:
    """Return a user-facing error when a multi-case search range is invalid."""
    if start_case_id < 1 or end_case_id < 1:
        return "Plage d'interventions invalide : les identifiants doivent être supérieurs ou égaux à 1."
    if end_case_id < start_case_id:
        return "La dernière intervention doit être supérieure ou égale à la première."
    return None


def _render_anomaly_frequency_chart(
    st,
    results: list[SearchResult],
    scanned_count: int,
) -> None:
    """Render a horizontal bar chart summarizing anomaly frequency across cases."""
    figure = _build_anomaly_frequency_figure(results, scanned_count=scanned_count)
    if figure is None:
        return

    st.markdown("<h2 class='vs-section-title'>Fréquence des anomalies</h2>", unsafe_allow_html=True)
    st.caption(
        "Chaque barre indique le nombre d'interventions scannées où l'anomalie apparaît au moins une fois. "
        "Une même intervention peut apparaître dans plusieurs barres."
    )
    st.plotly_chart(figure, use_container_width=True)


def _build_anomaly_frequency_figure(
    results: list[SearchResult],
    scanned_count: int | None = None,
):
    """Build a Plotly horizontal bar chart for anomaly counts."""
    import plotly.graph_objects as go

    counts = Counter(
        anomaly
        for result in results
        for anomaly in set(result.matched_anomalies)
    )
    if not counts:
        return None

    sorted_items = sorted(counts.items(), key=lambda item: (item[1], _format_anomaly_label(item[0])))
    anomalies = [item[0] for item in sorted_items]
    labels = [_format_anomaly_label(anomaly) for anomaly in anomalies]
    values = [counts[anomaly] for anomaly in anomalies]
    total_cases = scanned_count if scanned_count is not None else len(results)
    colors = [_anomaly_family_color(anomaly) for anomaly in anomalies]
    x_axis_max = max(values) + max(1, int(total_cases * 0.12))
    tick_step = _case_count_tick_step(total_cases)
    bar_width = 0.42 if len(labels) == 1 else 0.58

    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": colors, "line": {"width": 0}},
            text=[f"{value}/{total_cases}" for value in values],
            textposition="outside",
            width=bar_width,
            hovertemplate="%{y}<br>%{x} intervention(s) concernée(s)<extra></extra>",
        )
    )
    figure.update_layout(
        height=max(220, 54 * len(labels)),
        margin={"l": 10, "r": 70, "t": 10, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16,31,49,0.45)",
        font={"color": "#eaf7f4"},
        showlegend=False,
        xaxis_title="Nombre d'interventions concernées",
        yaxis_title="",
    )
    figure.update_xaxes(
        gridcolor="rgba(144,224,214,0.10)",
        zerolinecolor="rgba(144,224,214,0.16)",
        dtick=tick_step,
        range=[0, x_axis_max],
        tickangle=0,
    )
    figure.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return figure


def _anomaly_family_color(anomaly: str) -> str:
    """Return one stable color by physiological signal family."""
    if anomaly in {"hypotension", "hypertension"}:
        return "#57e6c4"
    if anomaly == "desaturation":
        return "#7aa7ff"
    if anomaly in {"tachycardia", "bradycardia"}:
        return "#e0c26b"
    if anomaly in {"low_etco2", "high_etco2"}:
        return "#d38b6d"
    return "#9eb8c3"


def _case_count_tick_step(total_cases: int) -> int:
    """Return a readable x-axis tick step for case-count charts."""
    if total_cases <= 10:
        return 1
    if total_cases <= 25:
        return 5
    return 10


def build_search_rows(results: list[SearchResult]) -> list[dict[str, str | int]]:
    """Build Streamlit-friendly rows from deterministic search results."""
    return [
        {
            "case_id": result.case_id,
            "score": f"{result.score.value}/100",
            "niveau": PRIORITY_LABELS[result.score.level],
            "anomalies": ", ".join(_format_anomaly_label(item) for item in result.matched_anomalies),
        }
        for result in results
    ]


def _json_report(report_data: dict) -> str:
    """Serialize report data for Streamlit download."""
    import json

    return json.dumps(report_data, ensure_ascii=False, indent=2)


def _render_stability_charts(
    st,
    raw_frame: pd.DataFrame,
    analysis: InterventionAnalysis,
) -> None:
    """Render Plotly charts for the technical stability of vital signs."""
    st.markdown(
        "<h2 class='vs-section-title'>Évolution de la stabilité technique des constantes</h2>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Les interruptions et pointillés indiquent des données absentes. "
        "Aucune valeur n'est interpolée. Les cercles bleus NIBP_MAP correspondent "
        "aux mesures réelles et intermittentes du brassard."
    )
    figures = _build_stability_figures(raw_frame, analysis.sample_interval_seconds)
    if not figures:
        st.info("Aucune donnée exploitable à afficher sous forme de graphique.")
        return

    columns = st.columns(2)
    for index, (title, figure) in enumerate(figures):
        with columns[index % 2]:
            st.markdown(f"**{title}**")
            st.plotly_chart(figure, use_container_width=True)


def _build_stability_figures(
    raw_frame: pd.DataFrame,
    interval_seconds: int,
) -> list[tuple[str, object]]:
    """Build the four Plotly figures used by the Streamlit dashboard."""
    import plotly.graph_objects as go

    frame = clean_impossible_values(raw_frame)
    figures: list[tuple[str, object]] = []

    pressure = _build_pressure_figure(go, frame, interval_seconds)
    if pressure is not None:
        figures.append(("Pression artérielle moyenne", pressure))

    for signal, title, unit, thresholds in (
        (
            "SpO2",
            "SpO2 (saturation périphérique en oxygène)",
            "%",
            (
                (DESATURATION_THRESHOLD, "Seuil désaturation", "#e0c26b"),
                (SEVERE_DESATURATION_THRESHOLD, "Seuil sévère", "#ff6b6b"),
            ),
        ),
        (
            "HR",
            "HR (fréquence cardiaque)",
            "bpm",
            (
                (BRADYCARDIA_THRESHOLD, "Bradycardie", "#e0c26b"),
                (SEVERE_BRADYCARDIA_THRESHOLD, "Bradycardie sévère", "#ff6b6b"),
                (TACHYCARDIA_THRESHOLD, "Tachycardie", "#e0c26b"),
                (SEVERE_TACHYCARDIA_THRESHOLD, "Tachycardie sévère", "#ff6b6b"),
            ),
        ),
        (
            "EtCO2",
            "EtCO2 (dioxyde de carbone en fin d'expiration)",
            "mmHg",
            (
                (LOW_ETCO2_THRESHOLD, "EtCO2 bas", "#e0c26b"),
                (SEVERE_LOW_ETCO2_THRESHOLD, "EtCO2 bas sévère", "#ff6b6b"),
                (HIGH_ETCO2_THRESHOLD, "EtCO2 haut", "#e0c26b"),
                (SEVERE_HIGH_ETCO2_THRESHOLD, "EtCO2 haut sévère", "#ff6b6b"),
            ),
        ),
    ):
        figure = _build_signal_figure(go, frame, signal, title, unit, thresholds, interval_seconds)
        if figure is not None:
            figures.append((title, figure))

    return figures


def _build_pressure_figure(go, frame: pd.DataFrame, interval_seconds: int):
    """Build one combined ART_MAP/NIBP_MAP pressure figure."""
    if "ART_MAP" not in frame.columns and "NIBP_MAP" not in frame.columns:
        return None
    if not _has_values(frame, ("ART_MAP", "NIBP_MAP")):
        return None

    figure = go.Figure()
    if "ART_MAP" in frame.columns and frame["ART_MAP"].notna().any():
        _add_line_trace(
            figure,
            frame,
            "ART_MAP",
            "ART_MAP (pression artérielle moyenne invasive)",
            "#57e6c4",
        )
        _add_missing_segments(figure, frame, "ART_MAP", interval_seconds)

    if "NIBP_MAP" in frame.columns and frame["NIBP_MAP"].notna().any():
        figure.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["NIBP_MAP"],
                mode="markers",
                name="NIBP_MAP (pression artérielle moyenne non invasive)",
                marker={
                    "color": "rgba(122,167,255,0.18)",
                    "line": {"color": "rgba(122,167,255,0.92)", "width": 0.8},
                    "size": 5,
                    "symbol": "circle-open",
                },
                hovertemplate="%{x}s · %{y:.0f} mmHg<extra>NIBP_MAP</extra>",
            )
        )
        _add_missing_segments(figure, frame, "NIBP_MAP", interval_seconds)

    _add_thresholds(
        figure,
        (
            (HYPOTENSION_THRESHOLD, "Hypotension", "#e0c26b"),
            (SEVERE_HYPOTENSION_THRESHOLD, "Hypotension sévère", "#ff6b6b"),
            (HYPERTENSION_THRESHOLD, "Hypertension", "#e0c26b"),
            (SEVERE_HYPERTENSION_THRESHOLD, "Hypertension sévère", "#ff6b6b"),
        ),
    )
    _style_figure(figure, "mmHg")
    return figure


def _build_signal_figure(
    go,
    frame: pd.DataFrame,
    signal: str,
    title: str,
    unit: str,
    thresholds: tuple[tuple[int, str, str], ...],
    interval_seconds: int,
):
    """Build one Plotly figure for a single continuous vital sign."""
    if signal not in frame.columns or not frame[signal].notna().any():
        return None

    figure = go.Figure()
    _add_line_trace(figure, frame, signal, title, "#57e6c4")
    _add_missing_segments(figure, frame, signal, interval_seconds)
    _add_thresholds(figure, thresholds)
    _style_figure(figure, unit)
    return figure


def _add_line_trace(figure, frame: pd.DataFrame, signal: str, name: str, color: str) -> None:
    """Add a real-value line trace without connecting missing gaps."""
    figure.add_trace(
        {
            "type": "scatter",
            "x": frame.index,
            "y": frame[signal],
            "mode": "lines",
            "name": name,
            "connectgaps": False,
            "line": {"color": color, "width": 1.6},
            "hovertemplate": f"%{{x}}s · %{{y:.1f}}<extra>{signal}</extra>",
        }
    )


def _add_missing_segments(
    figure,
    frame: pd.DataFrame,
    signal: str,
    interval_seconds: int,
) -> None:
    """Add dotted baseline segments showing missing data without interpolation."""
    series = frame[signal]
    valid = series.dropna()
    if valid.empty:
        return

    y_min = float(valid.min())
    y_max = float(valid.max())
    baseline = y_min - max((y_max - y_min) * 0.08, 1.0)

    run_start: int | None = None
    missing = series.isna().tolist()
    times = list(frame.index)
    for position, is_missing in enumerate(missing):
        if is_missing and run_start is None:
            run_start = position
        elif not is_missing and run_start is not None:
            _add_missing_segment_shape(
                figure,
                times[run_start],
                times[position - 1] + interval_seconds,
                baseline,
            )
            run_start = None

    if run_start is not None:
        _add_missing_segment_shape(
            figure,
            times[run_start],
            times[-1] + interval_seconds,
            baseline,
        )


def _add_missing_segment_shape(figure, start: int, end: int, y_value: float) -> None:
    """Draw one dotted missing-data segment."""
    figure.add_shape(
        type="line",
        x0=start,
        x1=end,
        y0=y_value,
        y1=y_value,
        line={"color": "rgba(158,184,195,0.8)", "width": 2, "dash": "dot"},
    )


def _add_thresholds(figure, thresholds: tuple[tuple[int, str, str], ...]) -> None:
    """Add clinical-rule thresholds with labels anchored at the chart right edge."""
    for value, label, color in thresholds:
        figure.add_hline(
            y=value,
            line_dash="dash",
            line_color=color,
            opacity=0.5,
            annotation_text=f"{label} ({value})",
            annotation_position="top right",
            annotation_font_color=color,
            annotation_font_size=10,
        )


def _style_figure(figure, y_title: str) -> None:
    """Apply the dark dashboard style to one Plotly figure."""
    figure.update_layout(
        height=280,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16,31,49,0.45)",
        font={"color": "#eaf7f4"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
        xaxis_title="Temps depuis le début (secondes)",
        yaxis_title=y_title,
    )
    figure.update_xaxes(
        gridcolor="rgba(144,224,214,0.10)",
        zerolinecolor="rgba(144,224,214,0.16)",
    )
    figure.update_yaxes(
        gridcolor="rgba(144,224,214,0.10)",
        zerolinecolor="rgba(144,224,214,0.16)",
    )


def _has_values(frame: pd.DataFrame, signals: tuple[str, ...]) -> bool:
    """Return whether at least one of the requested signals contains real values."""
    return any(signal in frame.columns and frame[signal].notna().any() for signal in signals)


def _format_score_explanation(value: int, level: str) -> str:
    """Explain the technical priority index scale for the Streamlit UI."""
    return (
        "<div class='vs-card'>"
        f"<p class='vs-card-title'>Niveau actuel : {PRIORITY_LABELS[level]}</p>"
        "<p class='vs-muted'>Indice de priorisation technique, sans valeur de gravité clinique.</p>"
        "<div class='vs-scale'>"
        "<span><b>0</b> aucune</span>"
        "<span><b>1-24</b> faible</span>"
        "<span><b>25-49</b> modérée</span>"
        "<span><b>50-74</b> élevée</span>"
        "<span><b>75-100</b> très élevée</span>"
        "</div>"
        "</div>"
    )


def _format_ai_summary_for_display(text: str) -> str:
    """Format AI text as short Markdown bullets for the Streamlit UI."""
    paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
    if not paragraphs:
        return ""

    formatted = []
    for paragraph in paragraphs:
        if paragraph.startswith(("- ", "* ")):
            formatted.append(f"<p>{escape(paragraph)}</p>")
        else:
            formatted.append(f"<p>- {escape(paragraph)}</p>")
    return "".join(formatted)


def _metric_card_html(title: str, value: str, subtitle: str, color: str) -> str:
    """Build a dashboard-style metric card."""
    return (
        "<div class='vs-card vs-metric'>"
        f"<p class='vs-card-title'>{escape(title)}</p>"
        f"<div class='vs-metric-row'><span>{escape(value)}</span>"
        f"<i style='background:{escape(color)}'></i></div>"
        f"<p class='vs-muted'>{escape(subtitle)}</p>"
        "</div>"
    )


def _event_card_html(text: str) -> str:
    """Build a compact event card."""
    return (
        "<div class='vs-card vs-event'>"
        "<span class='vs-marker'></span>"
        f"<p>{escape(text)}</p>"
        "</div>"
    )


def _signal_card_html(text: str) -> str:
    """Build a compact signal card."""
    return (
        "<div class='vs-card vs-signal'>"
        "<span class='vs-marker'></span>"
        f"<p>{escape(text)}</p>"
        "</div>"
    )


def _search_table_html(rows: list[dict[str, str | int]]) -> str:
    """Build a dashboard-style search result table."""
    body = "".join(
        "<tr>"
        f"<td>{escape(str(row['case_id']))}</td>"
        f"<td>{escape(str(row['score']))}</td>"
        f"<td><span class='vs-pill'>{escape(str(row['niveau']))}</span></td>"
        f"<td>{escape(str(row['anomalies']))}</td>"
        "</tr>"
        for row in rows
    )
    return (
        "<div class='vs-card vs-table-wrap'>"
        "<table class='vs-table'>"
        "<thead><tr><th>Intervention</th><th>Indice</th><th>Priorité</th><th>Anomalies</th></tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</div>"
    )


def _priority_color(level: str) -> str:
    """Return a dashboard accent color for one priority level."""
    return {
        "none": "#57e6c4",
        "low": "#57e6c4",
        "moderate": "#e0c26b",
        "high": "#d38b6d",
        "very_high": "#ff6b6b",
    }.get(level, "#57e6c4")


def _anomaly_filter_options() -> dict[str, str]:
    """Return French labels for deterministic anomaly filters."""
    return {
        "any": "Toutes les anomalies",
        "hypotension": "Hypotension",
        "hypertension": "Hypertension",
        "desaturation": "Désaturation",
        "tachycardia": "Tachycardie",
        "bradycardia": "Bradycardie",
        "low_etco2": "EtCO2 bas",
        "high_etco2": "EtCO2 élevé",
    }


def _format_anomaly_label(anomaly: str) -> str:
    """Format one anomaly name for UI display."""
    if anomaly == "any":
        return "toutes les anomalies"
    return ANOMALY_LABELS.get(anomaly, anomaly)


def _inject_theme(st) -> None:
    """Inject a light dashboard theme inspired by the visual reference."""
    st.markdown(
        """
        <style>
        :root {
            --vs-bg: #07131f;
            --vs-bg-2: #0b1b2b;
            --vs-panel: #101f31;
            --vs-panel-2: #13263a;
            --vs-glass: rgba(16, 31, 49, 0.78);
            --vs-cyan: #57e6c4;
            --vs-cyan-soft: rgba(87, 230, 196, 0.15);
            --vs-blue: #7aa7ff;
            --vs-text: #eaf7f4;
            --vs-muted: #9eb8c3;
            --vs-line: rgba(144, 224, 214, 0.14);
            --vs-danger: #ff6b6b;
            --vs-warm: #e0c26b;
        }
        .stApp {
            background:
                radial-gradient(circle at 12% 6%, rgba(87, 230, 196, 0.22), transparent 24rem),
                radial-gradient(circle at 88% 12%, rgba(122, 167, 255, 0.18), transparent 28rem),
                linear-gradient(135deg, var(--vs-bg) 0%, var(--vs-bg-2) 52%, #081522 100%);
            color: var(--vs-text);
        }
        .block-container {
            padding-top: 1.1rem;
            max-width: 1220px;
        }
        .block-container,
        .block-container p,
        .block-container li,
        .block-container span,
        .block-container label {
            color: var(--vs-text);
        }
        section[data-testid="stSidebar"] {
            background: rgba(5, 14, 24, 0.96);
            border-right: 1px solid var(--vs-line);
        }
        section[data-testid="stSidebar"] * {
            color: rgba(255, 255, 255, 0.88);
        }
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p {
            color: rgba(255, 255, 255, 0.78) !important;
        }
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background: rgba(255, 255, 255, 0.06);
            border-color: var(--vs-line);
            color: var(--vs-text);
        }
        .vs-sidebar-brand {
            display: flex;
            align-items: center;
            gap: 0.85rem;
            padding: 0.7rem 0 1.2rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            margin-bottom: 1rem;
        }
        .vs-logo {
            display: grid;
            place-items: center;
            width: 42px;
            height: 42px;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--vs-cyan), var(--vs-blue));
            color: #06111d !important;
            font-weight: 900;
            box-shadow: 0 0 22px rgba(87, 230, 196, 0.32);
        }
        .vs-sidebar-brand h2 {
            margin: 0;
            color: white;
            font-size: 1.05rem;
            letter-spacing: -0.02em;
        }
        .vs-sidebar-brand p {
            margin: 0.1rem 0 0;
            font-size: 0.78rem;
        }
        .vs-hero {
            border-radius: 28px;
            padding: 1.8rem 2rem;
            margin-bottom: 1.1rem;
            background:
                linear-gradient(135deg, rgba(16, 31, 49, 0.92), rgba(10, 24, 38, 0.88)),
                radial-gradient(circle at top right, rgba(87, 230, 196, 0.20), transparent 18rem);
            color: white;
            border: 1px solid var(--vs-line);
            box-shadow: 0 22px 60px rgba(0, 0, 0, 0.30);
            backdrop-filter: blur(14px);
        }
        .vs-hero h1 {
            color: white;
            margin: 0;
            font-size: 2.2rem;
            letter-spacing: -0.04em;
        }
        .vs-hero p {
            margin: 0.2rem 0 0;
            color: rgba(255, 255, 255, 0.82);
        }
        .vs-kicker {
            text-transform: uppercase;
            font-size: 0.78rem;
            letter-spacing: 0.12em;
            font-weight: 700;
            color: var(--vs-cyan) !important;
        }
        .vs-card {
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.02)),
                var(--vs-glass);
            border: 1px solid var(--vs-line);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 18px 46px rgba(0, 0, 0, 0.22);
            color: var(--vs-text);
            backdrop-filter: blur(14px);
        }
        .vs-card * {
            color: var(--vs-text);
        }
        .vs-card-title {
            margin: 0 0 0.35rem;
            color: var(--vs-text);
            font-weight: 800;
            line-height: 1.2;
        }
        .vs-muted {
            margin: 0;
            color: var(--vs-muted) !important;
            font-size: 0.92rem;
            line-height: 1.25;
        }
        .vs-section-title {
            color: var(--vs-text);
            font-size: 1.25rem;
            letter-spacing: -0.03em;
            margin: 1.15rem 0 0.75rem;
        }
        .vs-metric-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }
        .vs-metric {
            min-height: 136px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .vs-metric-row span {
            color: var(--vs-text);
            min-width: 0;
            overflow-wrap: anywhere;
            font-size: clamp(1.05rem, 1.45vw, 1.35rem);
            font-weight: 850;
            letter-spacing: -0.035em;
            line-height: 1.05;
        }
        .vs-metric-row i {
            flex: 0 0 auto;
            display: inline-block;
            width: 12px;
            height: 44px;
            border-radius: 999px;
            box-shadow: 0 0 22px rgba(87, 230, 196, 0.22);
        }
        .vs-scale {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.55rem;
            margin-top: 0.8rem;
        }
        .vs-scale span {
            border-radius: 12px;
            padding: 0.55rem 0.6rem;
            background: rgba(255, 255, 255, 0.045);
            border: 1px solid var(--vs-line);
            color: var(--vs-text);
            font-size: 0.86rem;
        }
        .vs-ai {
            border-left: 5px solid var(--vs-cyan);
        }
        .vs-ai p {
            margin: 0.45rem 0;
            color: var(--vs-text);
            line-height: 1.5;
        }
        .vs-event {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            border-left: 0;
            color: var(--vs-text);
        }
        .vs-signal {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            border-left: 0;
            color: var(--vs-text);
        }
        .vs-event p,
        .vs-signal p {
            margin: 0;
            line-height: 1.45;
        }
        .vs-marker {
            flex: 0 0 auto;
            width: 10px;
            height: 10px;
            margin-top: 0.38rem;
            border-radius: 999px;
            background: var(--vs-cyan);
            box-shadow: 0 0 16px rgba(87, 230, 196, 0.48);
        }
        .vs-event .vs-marker {
            background: var(--vs-warm);
            box-shadow: 0 0 16px rgba(224, 194, 107, 0.42);
        }
        .vs-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.2rem 0.55rem;
            background: var(--vs-cyan-soft);
            color: var(--vs-cyan) !important;
            font-weight: 800;
            font-size: 0.84rem;
        }
        .vs-table-wrap {
            padding: 0;
            overflow: hidden;
        }
        .vs-table {
            width: 100%;
            border-collapse: collapse;
            color: var(--vs-text);
        }
        .vs-table th {
            background: rgba(255, 255, 255, 0.04);
            color: var(--vs-muted);
            text-align: left;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 0.85rem 1rem;
        }
        .vs-table td {
            padding: 0.85rem 1rem;
            border-top: 1px solid var(--vs-line);
            color: var(--vs-text);
            vertical-align: top;
        }
        .vs-empty-state {
            border-radius: 28px;
            padding: 2rem;
            min-height: 260px;
            background: rgba(16, 31, 49, 0.62);
            border: 1px dashed var(--vs-line);
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-shadow: 0 18px 46px rgba(0, 0, 0, 0.18);
        }
        .vs-empty-state h3 {
            color: var(--vs-text);
            margin: 0 0 0.4rem;
            font-size: 1.35rem;
        }
        .vs-empty-state p {
            color: var(--vs-muted);
            margin: 0;
        }
        div[data-testid="stTabs"] button {
            font-weight: 700;
        }
        div[data-testid="stButton"] button {
            border-radius: 14px;
            border: 0;
            background: var(--vs-panel);
            color: white !important;
            box-shadow: 0 10px 20px rgba(32, 35, 49, 0.18);
        }
        div[data-testid="stButton"] button * {
            color: white !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button {
            background: linear-gradient(135deg, var(--vs-cyan), var(--vs-blue));
            color: #06111d !important;
            font-weight: 800;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button * {
            color: #06111d !important;
        }
        div[data-testid="stDownloadButton"] button {
            border-radius: 14px;
            border: 1px solid var(--vs-line);
            background: rgba(87, 230, 196, 0.10);
            color: var(--vs-text) !important;
            font-weight: 800;
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
        }
        div[data-testid="stDownloadButton"] button * {
            color: var(--vs-text) !important;
        }
        div[data-testid="stDownloadButton"] button:hover {
            border-color: var(--vs-cyan);
            background: rgba(87, 230, 196, 0.16);
        }
        div[data-testid="stAlert"] {
            background: rgba(16, 31, 49, 0.74);
            color: var(--vs-text);
            border: 1px solid var(--vs-line);
        }
        div[data-testid="stAlert"] * {
            color: var(--vs-text) !important;
        }
        @media (max-width: 900px) {
            .vs-scale {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
