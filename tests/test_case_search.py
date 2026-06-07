import pandas as pd

from vitalsignal.analysis.case_search import search_interventions


def test_search_interventions_filters_and_sorts_matches() -> None:
    frames = {
        1: pd.DataFrame(
            {
                    "ART_MAP": [60.0, 61.0] * 30,
                "HR": [80.0, 81.0] * 30,
            }
        ),
        2: pd.DataFrame(
            {
                "ART_MAP": [70.0, 71.0] * 30,
                "HR": [125.0] * 30 + [80.0, 81.0] * 15,
            }
        ),
        3: pd.DataFrame(
            {
                "ART_MAP": [70.0, 71.0] * 30,
                "HR": [80.0, 81.0] * 30,
            }
        ),
    }

    def fake_loader(case_id: int, interval: int) -> pd.DataFrame:
        return frames[case_id]

    results = search_interventions(
        [1, 2, 3],
        anomaly_filter="any",
        loader=fake_loader,
    )

    assert [result.case_id for result in results] == [1, 2]
    assert results[0].score.value >= results[1].score.value


def test_search_interventions_applies_requested_anomaly_filter() -> None:
    frames = {
        1: pd.DataFrame({"ART_MAP": [60.0, 61.0] * 30}),
        2: pd.DataFrame({"HR": [125.0] * 30 + [80.0, 81.0] * 15}),
    }

    def fake_loader(case_id: int, interval: int) -> pd.DataFrame:
        return frames[case_id]

    results = search_interventions(
        [1, 2],
        anomaly_filter="tachycardia",
        loader=fake_loader,
    )

    assert len(results) == 1
    assert results[0].case_id == 2
    assert results[0].matched_anomalies == ("tachycardia",)


def test_search_interventions_ignores_map_point_observations() -> None:
    frames = {
        1: pd.DataFrame(
            {
                "ART_MAP": [None] * 7,
                "NIBP_MAP": [45.0, None, None, 75.0, None, None, 130.0],
            }
        ),
        2: pd.DataFrame({"ART_MAP": [60.0, 61.0] * 30}),
    }

    def fake_loader(case_id: int, interval: int) -> pd.DataFrame:
        return frames[case_id]

    results = search_interventions(
        [1, 2],
        anomaly_filter="any",
        loader=fake_loader,
    )

    assert [result.case_id for result in results] == [2]


def test_search_interventions_reports_progress() -> None:
    frame = pd.DataFrame({"ART_MAP": [70.0, 71.0] * 30})
    progress_calls: list[tuple[int, int, int]] = []

    def fake_loader(case_id: int, interval: int) -> pd.DataFrame:
        return frame

    search_interventions(
        [10, 11],
        anomaly_filter="any",
        loader=fake_loader,
        progress_callback=lambda scanned, total, case_id: progress_calls.append(
            (scanned, total, case_id)
        ),
    )

    assert progress_calls == [(1, 2, 10), (2, 2, 11)]
