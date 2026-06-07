import math

import pandas as pd

from vitalsignal.analysis.preprocessing import clean_impossible_values


def test_clean_impossible_values_replaces_only_invalid_values() -> None:
    raw = pd.DataFrame(
        {
            "ART_MAP": [-1.0, 65.0, 251.0],
            "HR": [0.0, 80.0, 301.0],
            "SpO2": [-1.0, 98.0, 101.0],
            "EtCO2": [-1.0, 0.0, 151.0],
        }
    )

    cleaned = clean_impossible_values(raw)

    assert cleaned.loc[1, "ART_MAP"] == 65.0
    assert cleaned.loc[1, "HR"] == 80.0
    assert cleaned.loc[1, "SpO2"] == 98.0
    assert cleaned.loc[1, "EtCO2"] == 0.0
    assert cleaned.loc[[0, 2]].isna().all().all()


def test_clean_impossible_values_preserves_input_and_unknown_columns() -> None:
    raw = pd.DataFrame({"HR": [350.0], "note": ["raw"]})

    cleaned = clean_impossible_values(raw)

    assert raw.loc[0, "HR"] == 350.0
    assert math.isnan(cleaned.loc[0, "HR"])
    assert cleaned.loc[0, "note"] == "raw"

