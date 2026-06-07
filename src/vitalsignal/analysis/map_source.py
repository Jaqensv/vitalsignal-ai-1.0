"""Select the best available mean arterial pressure source."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from vitalsignal.analysis.signal_quality import SignalQuality, assess_signal_quality


MAPSource = Literal["ART_MAP", "NIBP_MAP"]
MeasurementMode = Literal["continuous", "intermittent"]


@dataclass(frozen=True)
class MAPSelection:
    """The selected pressure series and the reason it can be used."""

    source: MAPSource
    measurement_mode: MeasurementMode
    series: pd.Series
    quality: SignalQuality


def select_map_source(
    frame: pd.DataFrame,
    sample_interval_seconds: int = 1,
) -> MAPSelection | None:
    """Prefer usable invasive pressure, then usable non-invasive pressure."""
    candidates: tuple[tuple[MAPSource, MeasurementMode], ...] = (
        ("ART_MAP", "continuous"),
        ("NIBP_MAP", "intermittent"),
    )

    for source, measurement_mode in candidates:
        if source not in frame.columns:
            continue

        quality = assess_signal_quality(frame[source], sample_interval_seconds)
        if quality.status == "usable":
            return MAPSelection(
                source=source,
                measurement_mode=measurement_mode,
                series=frame[source],
                quality=quality,
            )

    return None

