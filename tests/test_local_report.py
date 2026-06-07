import pandas as pd

from vitalsignal.io.local_report import MEDICAL_WARNING, generate_local_report
from vitalsignal.analysis.pipeline import analyze_intervention
from vitalsignal.analysis.scoring import calculate_priority_score


def test_report_describes_detected_episode_and_score() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [60.0] * 60,
            "HR": [80.0, 81.0] * 30,
            "SpO2": [98.0, 99.0] * 30,
            "EtCO2": [35.0, 36.0] * 30,
        }
    )
    analysis = analyze_intervention(42, frame)
    score = calculate_priority_score(analysis)

    report = generate_local_report(analysis, score)

    assert "intervention n° 42" in report
    assert "Indice de priorité : 25/100 (modérée)" in report
    assert "Résumé technique :" in report
    assert "Source de pression artérielle moyenne :" in report
    assert "Exploitabilité des signaux :" in report
    assert "Contributions de l'indice :" in report
    assert "Timeline des anomalies :" in report
    assert "00:00:00 -> 00:01:00" in report
    assert "Regroupement par signal :" in report
    assert "1 épisode continu" in report
    assert "hypotension prolongée" in report
    assert "ART_MAP (pression artérielle moyenne invasive)" in report
    assert "durée 1 min" in report
    assert MEDICAL_WARNING in report


def test_report_distinguishes_no_anomaly_from_unavailable_analysis() -> None:
    frame = pd.DataFrame({"HR": [80.0, 81.0] * 30})
    analysis = analyze_intervention(3, frame)
    score = calculate_priority_score(analysis)

    report = generate_local_report(analysis, score)

    assert "Aucune anomalie répondant aux règles définies" in report
    assert "Analyse de la pression artérielle moyenne impossible" in report
    assert "Analyse de saturation périphérique en oxygène impossible" in report
    assert "SpO2 (saturation périphérique en oxygène) : non exploitable" in report


def test_report_describes_intermittent_map_observations_as_points() -> None:
    frame = pd.DataFrame(
        {"NIBP_MAP": [45.0, None, None, 75.0, None, None, 130.0]}
    )
    analysis = analyze_intervention(7, frame, sample_interval_seconds=60)
    score = calculate_priority_score(analysis)

    report = generate_local_report(analysis, score)

    assert "Observation ponctuelle" in report
    assert "NIBP_MAP (pression artérielle moyenne non invasive)" in report
    assert "à 6 min" in report
    assert "00:00:00 : observation ponctuelle" in report
    assert "00:06:00 : observation ponctuelle" in report
    assert "2 observations ponctuelles" in report
    assert "durée" not in report.split("Anomalies et observations :", 1)[1].split(
        "Interprétation :", 1
    )[0]
