"""Network-free tests for the Bybit adapter's parsing logic. The live
fetch() calls are not exercised here (this sandbox blocks the relevant
domains — see module docstring in bybit_l2.py); these only check that
the format-parsing functions do the right thing given data in the
documented shape.
"""

import pandas as pd
import pytest

from project_factory.data.adapters.bybit_l2 import _aggregate_trades_to_seconds, _parse_orderbook_records


def test_parse_orderbook_records_extracts_snapshot_only():
    records = [
        {
            "type": "snapshot",
            "ts": 1700000000000,
            "data": {
                "b": [["100.0", "5"], ["99.9", "3"]],
                "a": [["100.1", "4"], ["100.2", "6"]],
            },
        },
        {"type": "delta", "ts": 1700000001000, "data": {"b": [["100.05", "1"]], "a": []}},
        {
            "type": "snapshot",
            "ts": 1700000002000,
            "data": {
                "b": [["101.0", "2"]],
                "a": [["101.1", "3"]],
            },
        },
    ]
    df = _parse_orderbook_records(records, depth=200)

    assert len(df) == 2  # delta record dropped
    assert df["bid_price_1"].tolist() == [100.0, 101.0]
    assert df["bid_size_1"].tolist() == [5.0, 2.0]
    assert df["ask_price_1"].tolist() == [100.1, 101.1]
    # levels beyond available depth are None
    assert pd.isna(df["bid_price_3"].iloc[1])


def test_parse_orderbook_records_sorts_by_timestamp():
    records = [
        {"type": "snapshot", "ts": 2000, "data": {"b": [["1", "1"]], "a": [["2", "1"]]}},
        {"type": "snapshot", "ts": 1000, "data": {"b": [["1", "1"]], "a": [["2", "1"]]}},
    ]
    df = _parse_orderbook_records(records, depth=200)
    assert df["timestamp"].is_monotonic_increasing


def test_aggregate_trades_to_seconds_sums_signed_volume():
    trades = pd.DataFrame(
        {
            "timestamp": [1700000000.1, 1700000000.4, 1700000000.9, 1700000001.2],
            "side": ["Buy", "Sell", "Buy", "Buy"],
            "size": [1.0, 2.0, 3.0, 4.0],
        }
    )
    agg = _aggregate_trades_to_seconds(trades)

    assert len(agg) == 2  # two distinct 1-second buckets
    first_bucket = agg.iloc[0]
    assert first_bucket["trade_count"] == 3
    assert first_bucket["trade_signed_volume"] == pytest.approx(1.0 - 2.0 + 3.0)

    second_bucket = agg.iloc[1]
    assert second_bucket["trade_count"] == 1
    assert second_bucket["trade_signed_volume"] == pytest.approx(4.0)


def test_aggregate_trades_to_seconds_raises_on_unrecognized_schema():
    trades = pd.DataFrame({"timestamp": [1, 2], "unexpected_col": ["a", "b"]})
    with pytest.raises(ValueError):
        _aggregate_trades_to_seconds(trades)


def test_aggregate_trades_to_seconds_handles_empty_input():
    empty = pd.DataFrame(columns=["timestamp", "side", "size"])
    agg = _aggregate_trades_to_seconds(empty)
    assert agg.empty
