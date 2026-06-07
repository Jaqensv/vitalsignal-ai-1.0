from vitalsignal.analysis.case_search import SearchResult
from vitalsignal.app.streamlit_app import (
    ANALYSIS_INTERVAL_SECONDS,
    SEARCH_MAX_CASES,
    SEARCH_SCAN_INTERVAL_SECONDS,
    _apply_pending_case_open,
    _build_anomaly_frequency_figure,
    _case_count_tick_step,
    _data_source_message,
    _format_ai_summary_for_display,
    _format_score_explanation,
    _multi_case_data_source_message,
    _build_stability_figures,
    _json_report,
    _metric_card_html,
    _missing_openai_key_message,
    _parse_intervention_id,
    _parse_intervention_range,
    _priority_color,
    _render_search_results,
    _search_table_html,
    _validate_intervention_id,
    _validate_intervention_range,
    build_search_rows,
)
from vitalsignal.analysis.pipeline import analyze_intervention
from vitalsignal.analysis.scoring import calculate_priority_score

import pandas as pd


class FakeColumn:
    def __init__(self, clicked: bool) -> None:
        self.clicked = clicked
        self.writes = []

    def write(self, value) -> None:
        self.writes.append(value)

    def button(self, label: str, key: str) -> bool:
        return self.clicked


class FakeStreamlit:
    def __init__(self, clicked: bool) -> None:
        self.clicked = clicked
        self.session_state = {}
        self.success_messages = []

    def columns(self, spec: list[int]) -> list[FakeColumn]:
        return [FakeColumn(False), FakeColumn(False), FakeColumn(False), FakeColumn(False), FakeColumn(self.clicked)]

    def button(self, label: str, key: str) -> bool:
        return self.clicked

    def markdown(self, text: str) -> None:
        return None

    def success(self, message: str) -> None:
        self.success_messages.append(message)


def test_json_report_serializes_french_text() -> None:
    rendered = _json_report({"message": "saturation périphérique en oxygène"})

    assert "saturation périphérique en oxygène" in rendered


def test_missing_openai_key_message_mentions_env() -> None:
    message = _missing_openai_key_message()

    assert "clé API OpenAI" in message
    assert ".env" in message


def test_search_scan_interval_is_fixed_for_comparable_results() -> None:
    assert SEARCH_SCAN_INTERVAL_SECONDS == 2


def test_analysis_interval_is_fixed_for_comparable_results() -> None:
    assert ANALYSIS_INTERVAL_SECONDS == 2


def test_search_scan_has_ui_safety_limit() -> None:
    assert SEARCH_MAX_CASES == 50


def test_case_count_tick_step_adapts_to_scan_size() -> None:
    assert _case_count_tick_step(10) == 1
    assert _case_count_tick_step(25) == 5
    assert _case_count_tick_step(50) == 10


def test_validate_intervention_id_rejects_negative_values() -> None:
    assert _validate_intervention_id(-1) is not None
    assert _validate_intervention_id(0) is not None
    assert _validate_intervention_id(1) is None


def test_parse_intervention_id_rejects_invalid_user_input() -> None:
    assert _parse_intervention_id("-1")[1] is not None
    assert _parse_intervention_id("0")[1] is not None
    assert _parse_intervention_id("abc")[1] == (
        "Identifiant d'intervention invalide : saisis un nombre entier."
    )
    assert _parse_intervention_id(" 42 ") == (42, None)


def test_validate_intervention_range_rejects_negative_values() -> None:
    assert _validate_intervention_range(-1, 5) is not None
    assert _validate_intervention_range(1, -5) is not None
    assert _validate_intervention_range(5, 1) == (
        "La dernière intervention doit être supérieure ou égale à la première."
    )
    assert _validate_intervention_range(1, 5) is None


def test_parse_intervention_range_rejects_invalid_user_input() -> None:
    assert _parse_intervention_range("-1", "5")[2] is not None
    assert _parse_intervention_range("1", "-5")[2] is not None
    assert _parse_intervention_range("a", "5")[2] is not None
    assert _parse_intervention_range("5", "1")[2] == (
        "La dernière intervention doit être supérieure ou égale à la première."
    )
    assert _parse_intervention_range("1", "5") == (1, 5, None)


def test_data_source_message_explains_cache_or_vitaldb() -> None:
    assert "cache local" in _data_source_message(True)
    assert "VitalDB" in _data_source_message(False)
    assert "cases/" in _data_source_message(False)


def test_multi_case_data_source_message_explains_cache_mix() -> None:
    assert "cache local" in _multi_case_data_source_message(5, 5)
    assert "5/5" in _multi_case_data_source_message(5, 5)
    assert "VitalDB" in _multi_case_data_source_message(0, 5)
    assert "5/5 interventions ont été téléchargées" in _multi_case_data_source_message(0, 5)
    mixed = _multi_case_data_source_message(2, 5)
    assert "cache local et VitalDB" in mixed
    assert "2/5 interventions déjà en cache" in mixed
    assert "3/5 téléchargées" in mixed


def test_build_search_rows_formats_results() -> None:
    frame = pd.DataFrame({"ART_MAP": [60.0] * 60})
    analysis = analyze_intervention(42, frame)
    score = calculate_priority_score(analysis)

    rows = build_search_rows(
        [
            SearchResult(
                case_id=42,
                score=score,
                analysis=analysis,
                matched_anomalies=("hypotension",),
            )
        ]
    )

    assert rows == [
        {
            "case_id": 42,
            "score": "25/100",
            "niveau": "modérée",
            "anomalies": "hypotension",
        }
    ]


def test_render_search_results_can_select_case_id() -> None:
    fake_st = FakeStreamlit(clicked=True)

    _render_search_results(
        fake_st,
        [
            {
                "case_id": 42,
                "score": "25/100",
                "niveau": "modérée",
                "anomalies": "hypotension",
            }
        ],
    )

    assert fake_st.session_state["pending_open_case_id"] == 42
    assert fake_st.success_messages


def test_apply_pending_case_open_switches_to_analysis_mode() -> None:
    fake_st = FakeStreamlit(clicked=False)
    fake_st.session_state["pending_open_case_id"] = 42

    _apply_pending_case_open(fake_st)

    assert fake_st.session_state["selected_case_id"] == 42
    assert fake_st.session_state["analysis_case_id"] == "42"
    assert fake_st.session_state["navigation_mode"] == "Analyser une intervention"
    assert "pending_open_case_id" not in fake_st.session_state


def test_build_anomaly_frequency_figure_counts_cases_per_anomaly() -> None:
    frame = pd.DataFrame({"ART_MAP": [60.0] * 60})
    analysis = analyze_intervention(42, frame)
    score = calculate_priority_score(analysis)
    figure = _build_anomaly_frequency_figure(
        [
            SearchResult(
                case_id=42,
                score=score,
                analysis=analysis,
                matched_anomalies=("hypotension", "tachycardia", "tachycardia"),
            ),
            SearchResult(
                case_id=43,
                score=score,
                analysis=analysis,
                matched_anomalies=("hypotension",),
            ),
        ],
        scanned_count=5,
    )

    assert figure is not None
    bar = figure.data[0]
    values_by_label = dict(zip(bar.y, bar.x, strict=True))
    assert values_by_label["hypotension"] == 2
    assert values_by_label["tachycardie"] == 1
    assert list(bar.text) == ["1/5", "2/5"]
    assert figure.layout.xaxis.tickangle == 0
    assert figure.layout.xaxis.dtick == 1
    assert figure.layout.xaxis.range[1] > max(bar.x)


def test_build_anomaly_frequency_figure_keeps_single_bar_compact() -> None:
    frame = pd.DataFrame({"SpO2": [91.0] * 60})
    analysis = analyze_intervention(42, frame)
    score = calculate_priority_score(analysis)
    figure = _build_anomaly_frequency_figure(
        [
            SearchResult(
                case_id=42,
                score=score,
                analysis=analysis,
                matched_anomalies=("desaturation",),
            )
        ],
        scanned_count=16,
    )

    assert figure is not None
    bar = figure.data[0]
    assert list(bar.text) == ["1/16"]
    assert bar.width == 0.42


def test_format_score_explanation_explains_scale_in_french() -> None:
    explanation = _format_score_explanation(45, "moderate")

    assert "Niveau actuel : modérée" in explanation
    assert "<b>1-24</b> faible" in explanation
    assert "<b>75-100</b> très élevée" in explanation
    assert "pas mesure de gravité clinique" in explanation


def test_format_ai_summary_for_display_creates_short_bullets() -> None:
    rendered = _format_ai_summary_for_display(
        "Premier point explicatif.\n\n- Deuxième point déjà formaté."
    )

    assert rendered.startswith("<p>- Premier point explicatif.</p>")
    assert "<p>- Deuxième point déjà formaté.</p>" in rendered


def test_metric_card_html_escapes_content() -> None:
    rendered = _metric_card_html("Score", "<45>", "modérée", "#fff")

    assert "&lt;45&gt;" in rendered
    assert "vs-card" in rendered
    assert "vs-metric" in rendered


def test_priority_color_maps_levels() -> None:
    assert _priority_color("moderate") == "#e0c26b"
    assert _priority_color("unknown") == "#57e6c4"


def test_search_table_html_renders_rows() -> None:
    rendered = _search_table_html(
        [
            {
                "case_id": 42,
                "score": "25/100",
                "niveau": "modérée",
                "anomalies": "hypotension",
            }
        ]
    )

    assert "Intervention" in rendered
    assert "Indice" in rendered
    assert "<td>42</td>" in rendered
    assert "vs-pill" in rendered


def test_build_stability_figures_combines_pressure_sources_and_keeps_four_blocks() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [70.0, 71.0, None, 73.0],
            "NIBP_MAP": [None, 72.0, None, 74.0],
            "SpO2": [98.0, None, 97.0, 96.0],
            "HR": [80.0, 82.0, None, 84.0],
            "EtCO2": [35.0, 36.0, None, 37.0],
        },
        index=pd.Index([0, 2, 4, 6], name="time_seconds"),
    )

    figures = _build_stability_figures(frame, interval_seconds=2)

    assert len(figures) == 4
    pressure_title, pressure_figure = figures[0]
    assert pressure_title == "Pression artérielle moyenne"
    assert any("ART_MAP" in trace.name for trace in pressure_figure.data)
    assert any("NIBP_MAP" in trace.name for trace in pressure_figure.data)
    nibp_trace = next(trace for trace in pressure_figure.data if "NIBP_MAP" in trace.name)
    assert nibp_trace.marker.size == 5
    assert nibp_trace.marker.symbol == "circle-open"
    assert nibp_trace.marker.line.width == 0.8
    assert not any("Hypotension (65)" == trace.name for trace in pressure_figure.data)
    assert any("Hypotension (65)" == annotation.text for annotation in pressure_figure.layout.annotations)
    assert any(shape.line.dash == "dot" for shape in pressure_figure.layout.shapes)
