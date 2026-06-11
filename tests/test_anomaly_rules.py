import pandas as pd

from vitalsignal.analysis.anomaly_rules import (
    detect_bradycardia,
    detect_desaturation,
    detect_high_etco2,
    detect_hypertension,
    detect_hypotension,
    detect_low_etco2,
    detect_tachycardia,
)


def test_detect_hypotension_finds_sustained_episode() -> None:
    signal = pd.Series([70.0] * 10 + [60.0] * 60 + [70.0] * 10)

    episodes = detect_hypotension(signal, signal="ART_MAP")

    assert len(episodes) == 1
    assert episodes[0].signal == "ART_MAP"
    assert episodes[0].start_seconds == 10
    assert episodes[0].end_seconds == 70
    assert episodes[0].duration_seconds == 60
    assert episodes[0].extreme_value == 60.0
    assert episodes[0].qualifications == ("prolonged",)


def test_detect_hypotension_ignores_short_episode() -> None:
    signal = pd.Series([60.0] * 59 + [70.0])

    assert detect_hypotension(signal, signal="NIBP_MAP") == []


def test_missing_value_interrupts_hypotension_episode() -> None:
    signal = pd.Series([60.0] * 40 + [None] + [60.0] * 40)

    assert detect_hypotension(signal, signal="ART_MAP") == []


def test_detect_hypotension_uses_sample_interval() -> None:
    signal = pd.Series([60.0] * 30)

    episodes = detect_hypotension(
        signal,
        signal="ART_MAP",
        sample_interval_seconds=2,
    )

    assert episodes[0].duration_seconds == 60
    assert episodes[0].end_seconds == 60


def test_detect_hypotension_keeps_short_severe_episode() -> None:
    signal = pd.Series([70.0] * 5 + [45.0] * 15 + [70.0] * 5)

    episodes = detect_hypotension(signal, signal="ART_MAP")

    assert len(episodes) == 1
    assert episodes[0].duration_seconds == 15
    assert episodes[0].qualifications == ("severe_transient",)


def test_one_episode_can_have_both_hypotension_qualifications() -> None:
    signal = pd.Series([60.0] * 30 + [45.0] * 20 + [60.0] * 30)

    episodes = detect_hypotension(signal, signal="ART_MAP")

    assert len(episodes) == 1
    assert episodes[0].duration_seconds == 80
    assert episodes[0].qualifications == ("prolonged", "severe_transient")


def test_severe_duration_must_be_continuous() -> None:
    signal = pd.Series([45.0] * 10 + [55.0] + [45.0] * 10)

    assert detect_hypotension(signal, signal="ART_MAP") == []


def test_detect_hypertension_finds_prolonged_episode() -> None:
    signal = pd.Series([100.0] * 5 + [125.0] * 60 + [100.0] * 5)

    episodes = detect_hypertension(signal, signal="ART_MAP")

    assert len(episodes) == 1
    assert episodes[0].anomaly_type == "hypertension"
    assert episodes[0].extreme_value == 125.0
    assert episodes[0].qualifications == ("prolonged",)


def test_detect_hypertension_keeps_short_severe_episode() -> None:
    signal = pd.Series([145.0] * 15)

    episodes = detect_hypertension(signal, signal="ART_MAP")

    assert len(episodes) == 1
    assert episodes[0].duration_seconds == 15
    assert episodes[0].qualifications == ("severe_transient",)


def test_one_episode_can_have_both_hypertension_qualifications() -> None:
    signal = pd.Series([125.0] * 30 + [145.0] * 20 + [125.0] * 30)

    episodes = detect_hypertension(signal, signal="ART_MAP")

    assert len(episodes) == 1
    assert episodes[0].qualifications == ("prolonged", "severe_transient")


def test_missing_value_interrupts_hypertension_episode() -> None:
    signal = pd.Series([125.0] * 40 + [None] + [125.0] * 40)

    assert detect_hypertension(signal, signal="ART_MAP") == []


def test_detect_desaturation_finds_sustained_episode() -> None:
    signal = pd.Series([98.0] * 5 + [89.0] * 30 + [98.0] * 5)

    episodes = detect_desaturation(signal)

    assert len(episodes) == 1
    assert episodes[0].anomaly_type == "desaturation"
    assert episodes[0].signal == "SpO2"
    assert episodes[0].start_seconds == 5
    assert episodes[0].duration_seconds == 30
    assert episodes[0].extreme_value == 89.0


def test_detect_desaturation_ignores_short_episode() -> None:
    signal = pd.Series([89.0] * 29 + [98.0])

    assert detect_desaturation(signal) == []


def test_missing_value_interrupts_desaturation_episode() -> None:
    signal = pd.Series([89.0] * 20 + [None] + [89.0] * 20)

    assert detect_desaturation(signal) == []


def test_detect_desaturation_uses_sample_interval() -> None:
    signal = pd.Series([89.0] * 15)

    episodes = detect_desaturation(signal, sample_interval_seconds=2)

    assert len(episodes) == 1
    assert episodes[0].duration_seconds == 30


def test_detect_desaturation_keeps_short_severe_episode() -> None:
    signal = pd.Series([98.0] * 5 + [84.0] * 15 + [98.0] * 5)

    episodes = detect_desaturation(signal)

    assert len(episodes) == 1
    assert episodes[0].duration_seconds == 15
    assert episodes[0].qualifications == ("severe_transient",)


def test_one_episode_can_have_both_desaturation_qualifications() -> None:
    signal = pd.Series([89.0] * 15 + [84.0] * 15 + [89.0] * 15)

    episodes = detect_desaturation(signal)

    assert len(episodes) == 1
    assert episodes[0].duration_seconds == 45
    assert episodes[0].qualifications == ("prolonged", "severe_transient")


def test_severe_desaturation_duration_must_be_continuous() -> None:
    signal = pd.Series([84.0] * 10 + [89.0] + [84.0] * 10)

    assert detect_desaturation(signal) == []


def test_detect_tachycardia_finds_prolonged_episode() -> None:
    episodes = detect_tachycardia(pd.Series([125.0] * 30))

    assert len(episodes) == 1
    assert episodes[0].anomaly_type == "tachycardia"
    assert episodes[0].qualifications == ("prolonged",)


def test_detect_tachycardia_keeps_short_severe_episode() -> None:
    episodes = detect_tachycardia(pd.Series([155.0] * 15))

    assert len(episodes) == 1
    assert episodes[0].qualifications == ("severe_transient",)


def test_detect_bradycardia_finds_both_qualifications() -> None:
    signal = pd.Series([45.0] * 15 + [35.0] * 15 + [45.0] * 15)

    episodes = detect_bradycardia(signal)

    assert len(episodes) == 1
    assert episodes[0].extreme_value == 35.0
    assert episodes[0].qualifications == ("prolonged", "severe_transient")


def test_missing_value_interrupts_heart_rate_episode() -> None:
    signal = pd.Series([125.0] * 20 + [None] + [125.0] * 20)

    assert detect_tachycardia(signal) == []


def test_detect_low_etco2_finds_prolonged_episode() -> None:
    episodes = detect_low_etco2(pd.Series([24.0] * 30))

    assert len(episodes) == 1
    assert episodes[0].anomaly_type == "low_etco2"
    assert episodes[0].qualifications == ("prolonged",)


def test_detect_high_etco2_keeps_short_severe_episode() -> None:
    episodes = detect_high_etco2(pd.Series([65.0] * 15))

    assert len(episodes) == 1
    assert episodes[0].anomaly_type == "high_etco2"
    assert episodes[0].qualifications == ("severe_transient",)


def test_one_etco2_episode_can_have_both_qualifications() -> None:
    signal = pd.Series([24.0] * 15 + [15.0] * 15 + [24.0] * 15)

    episodes = detect_low_etco2(signal)

    assert len(episodes) == 1
    assert episodes[0].extreme_value == 15.0
    assert episodes[0].qualifications == ("prolonged", "severe_transient")


def test_missing_value_interrupts_etco2_episode() -> None:
    signal = pd.Series([55.0] * 20 + [None] + [55.0] * 20)

    assert detect_high_etco2(signal) == []
