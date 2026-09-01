import pandas as pd

from project_factory.data.quality import build_quality_report


def test_clean_data_reports_is_clean_true():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="h"),
            "value": range(10),
        }
    )
    report = build_quality_report(df, timestamp_column="timestamp", expected_frequency=pd.Timedelta(hours=1))
    assert report.is_clean
    assert not report.has_duplicate_timestamps
    assert not report.gaps_detected


def test_detects_duplicate_timestamps():
    df = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01")] * 3 + list(pd.date_range("2024-01-02", periods=7, freq="h")),
            "value": range(10),
        }
    )
    report = build_quality_report(df, timestamp_column="timestamp")
    assert report.has_duplicate_timestamps
    assert report.n_duplicate_timestamps == 2
    assert not report.is_clean


def test_detects_gaps():
    timestamps = list(pd.date_range("2024-01-01", periods=5, freq="h")) + list(
        pd.date_range("2024-01-05", periods=5, freq="h")
    )
    df = pd.DataFrame({"timestamp": timestamps, "value": range(10)})
    report = build_quality_report(df, timestamp_column="timestamp", expected_frequency=pd.Timedelta(hours=1))
    assert report.gaps_detected


def test_detects_missing_values():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="h"),
            "value": [1, 2, None, None, None, None, 7, 8, 9, 10],
        }
    )
    report = build_quality_report(df, timestamp_column="timestamp")
    assert report.missing_fraction_by_column["value"] == 0.4
    assert not report.is_clean
