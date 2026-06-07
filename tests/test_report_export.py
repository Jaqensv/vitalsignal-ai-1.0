import json

import pandas as pd

from vitalsignal.analysis.pipeline import analyze_intervention
from vitalsignal.io.report_export import build_markdown_report, build_report_data
from vitalsignal.analysis.scoring import calculate_priority_score


def _build_analysis_and_score():
    frame = pd.DataFrame(
        {
            "ART_MAP": [60.0] * 60,
            "HR": [80.0, 81.0] * 30,
            "SpO2": [98.0, 99.0] * 30,
            "EtCO2": [35.0, 36.0] * 30,
        }
    )
    analysis = analyze_intervention(42, frame)
    return analysis, calculate_priority_score(analysis)


def test_build_report_data_is_json_serializable() -> None:
    analysis, score = _build_analysis_and_score()

    report_data = build_report_data(analysis, score)
    serialized = json.dumps(report_data, ensure_ascii=False)

    assert report_data["case_id"] == 42
    assert report_data["priority_score"]["value"] == 25
    assert report_data["timeline"][0]["start_seconds"] == 0
    assert report_data["timeline"][0]["end_seconds"] == 60
    assert "hypotension prolongée" in report_data["timeline"][0]["text"]
    assert report_data["signal_groups"][0]["signal"] == "ART_MAP"
    assert report_data["signal_groups"][0]["episode_count"] == 1
    assert "pression artérielle moyenne invasive" in report_data["signal_groups"][0]["text"]
    assert "hypotension" in serialized
    assert "ne fournit pas de diagnostic" in serialized


def test_build_markdown_report_contains_local_summary() -> None:
    analysis, score = _build_analysis_and_score()

    markdown = build_markdown_report(analysis, score)

    assert markdown.startswith("# Rapport VitalSignal AI")
    assert "intervention n° `42`" in markdown
    assert "Indice de priorité : **25/100**" in markdown
    assert "## Exploitabilité des signaux" in markdown
    assert "## Timeline des anomalies" in markdown
    assert "00:00:00 -> 00:01:00" in markdown
    assert "## Regroupement par signal" in markdown
    assert "## Contributions de l'indice" in markdown
    assert "| Contribution | Points |" in markdown
    assert "```" not in markdown
