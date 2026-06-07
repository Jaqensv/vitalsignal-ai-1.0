"""Prepare raw vital signs for quality control and anomaly detection."""

import pandas as pd


VALID_RANGES: dict[str, tuple[float, float]] = {
    "ART_MAP": (0.0, 250.0),
    "NIBP_MAP": (0.0, 250.0),
    "HR": (0.0, 300.0),
    "SpO2": (0.0, 100.0),
    "EtCO2": (0.0, 150.0),
}


def clean_impossible_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Replace clearly impossible vital-sign values with missing values."""
    cleaned = frame.copy()

    for signal, (minimum, maximum) in VALID_RANGES.items():
        if signal not in cleaned.columns:
            continue

        values = cleaned[signal]
        invalid = (values <= minimum) | (values > maximum)
        if signal == "EtCO2":
            invalid = (values < minimum) | (values > maximum)

        cleaned.loc[invalid, signal] = pd.NA

    return cleaned

