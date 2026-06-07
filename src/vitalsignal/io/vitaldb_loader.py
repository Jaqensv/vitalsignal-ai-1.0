"""Load the priority vital signs from a VitalDB case."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import vitaldb


TRACKS: dict[str, str] = {
    "ART_MAP": "Solar8000/ART_MBP",
    "NIBP_MAP": "Solar8000/NIBP_MBP",
    "HR": "Solar8000/HR",
    "SpO2": "Solar8000/PLETH_SPO2",
    "EtCO2": "Solar8000/ETCO2",
}

VitalDBLoader = Callable[[int, list[str], int], np.ndarray]
DEFAULT_CACHE_DIR = Path("cases")


class VitalDBCaseAccessError(ValueError):
    """Raised when one VitalDB intervention cannot be loaded by identifier."""


def load_case(
    case_id: int,
    interval: int = 2,
    loader: VitalDBLoader = vitaldb.load_case,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
) -> pd.DataFrame:
    """Load priority tracks for one VitalDB case, using a local cache when enabled."""
    if case_id < 1:
        raise ValueError("case_id must be a positive integer")
    if interval < 1:
        raise ValueError("interval must be a positive integer")

    cache_path = _cache_path(case_id, interval, cache_dir)
    if cache_path is not None and cache_path.exists():
        return _read_cached_case(cache_path)

    try:
        data = loader(case_id, list(TRACKS.values()), interval)
    except Exception as error:
        message = str(error)
        if "403" in message:
            raise VitalDBCaseAccessError(
                "intervention VitalDB introuvable ou non accessible. "
                "Vérifie que l'identifiant existe dans VitalDB."
            ) from error
        raise

    if data.ndim != 2 or data.shape[1] != len(TRACKS):
        raise ValueError("VitalDB returned data with an unexpected shape")

    frame = pd.DataFrame(data, columns=TRACKS.keys())
    frame.index = pd.Index(frame.index * interval, name="time_seconds")
    if cache_path is not None:
        _write_cached_case(frame, cache_path)
    return frame


def _cache_path(case_id: int, interval: int, cache_dir: Path | str | None) -> Path | None:
    """Return the local cache path for one intervention, or None when disabled."""
    if cache_dir is None:
        return None
    return Path(cache_dir) / f"intervention_{case_id}_interval_{interval}.csv"


def _read_cached_case(cache_path: Path) -> pd.DataFrame:
    """Read one cached intervention from disk."""
    frame = pd.read_csv(cache_path, index_col="time_seconds")
    frame.index = pd.Index(frame.index.astype(int), name="time_seconds")
    return frame


def _write_cached_case(frame: pd.DataFrame, cache_path: Path) -> None:
    """Persist one loaded intervention in the local cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path)
