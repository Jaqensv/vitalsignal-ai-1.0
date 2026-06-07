import pandas as pd

from vitalsignal.analysis.map_source import select_map_source


def test_select_map_source_prefers_usable_art_map() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": list(range(70, 190)),
            "NIBP_MAP": [75.0, 76.0, 74.0] + [None] * 117,
        }
    )

    selection = select_map_source(frame)

    assert selection is not None
    assert selection.source == "ART_MAP"
    assert selection.measurement_mode == "continuous"


def test_select_map_source_falls_back_to_usable_nibp_map() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [None] * 10,
            "NIBP_MAP": [75.0, None, None, 76.0, None, None, 74.0, None, None, None],
        }
    )

    selection = select_map_source(frame)

    assert selection is not None
    assert selection.source == "NIBP_MAP"
    assert selection.measurement_mode == "intermittent"


def test_select_map_source_returns_none_without_usable_source() -> None:
    frame = pd.DataFrame(
        {
            "ART_MAP": [None] * 10,
            "NIBP_MAP": [75.0] + [None] * 9,
        }
    )

    assert select_map_source(frame) is None

