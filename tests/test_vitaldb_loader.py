import numpy as np
import pandas as pd
import pytest

from vitalsignal.io.vitaldb_loader import TRACKS, VitalDBCaseAccessError, load_case


def test_load_case_returns_named_dataframe() -> None:
    raw_data = np.array(
        [
            [70.0, np.nan, 80.0, 98.0, 35.0],
            [68.0, np.nan, 82.0, 97.0, 34.0],
        ]
    )

    def fake_loader(case_id: int, tracks: list[str], interval: int) -> np.ndarray:
        assert case_id == 42
        assert tracks == list(TRACKS.values())
        assert interval == 2
        return raw_data

    result = load_case(case_id=42, interval=2, loader=fake_loader, cache_dir=None)

    assert isinstance(result, pd.DataFrame)
    assert result.columns.tolist() == list(TRACKS.keys())
    assert result.index.tolist() == [0, 2]
    assert result.index.name == "time_seconds"
    assert result["NIBP_MAP"].isna().all()


@pytest.mark.parametrize(("case_id", "interval"), [(0, 1), (1, 0)])
def test_load_case_rejects_non_positive_inputs(case_id: int, interval: int) -> None:
    with pytest.raises(ValueError):
        load_case(case_id=case_id, interval=interval, cache_dir=None)


def test_load_case_translates_vitaldb_403_to_user_friendly_error() -> None:
    def fake_loader(case_id: int, tracks: list[str], interval: int) -> np.ndarray:
        raise RuntimeError("HTTP Error 403: Forbidden")

    with pytest.raises(VitalDBCaseAccessError, match="introuvable ou non accessible"):
        load_case(case_id=999999, interval=2, loader=fake_loader, cache_dir=None)


def test_load_case_writes_and_reuses_local_cache(tmp_path) -> None:
    raw_data = np.array([[70.0, np.nan, 80.0, 98.0, 35.0]])
    calls = {"count": 0}

    def fake_loader(case_id: int, tracks: list[str], interval: int) -> np.ndarray:
        calls["count"] += 1
        return raw_data

    first = load_case(case_id=42, interval=2, loader=fake_loader, cache_dir=tmp_path)
    second = load_case(case_id=42, interval=2, loader=fake_loader, cache_dir=tmp_path)

    assert calls["count"] == 1
    assert first.equals(second)
    assert (tmp_path / "intervention_42_interval_2.csv").exists()


def test_load_case_can_disable_local_cache(tmp_path) -> None:
    raw_data = np.array([[70.0, np.nan, 80.0, 98.0, 35.0]])
    calls = {"count": 0}

    def fake_loader(case_id: int, tracks: list[str], interval: int) -> np.ndarray:
        calls["count"] += 1
        return raw_data

    load_case(case_id=42, interval=2, loader=fake_loader, cache_dir=None)
    load_case(case_id=42, interval=2, loader=fake_loader, cache_dir=None)

    assert calls["count"] == 2
    assert not list(tmp_path.iterdir())
