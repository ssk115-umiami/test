"""Network-free tests for the Bybit adapter's parsing logic. The live
fetch() calls are not exercised here (this sandbox blocks the relevant
domains — see module docstring in bybit_l2.py); these only check that
the format-parsing functions do the right thing given data in the
documented shape.
"""

import pandas as pd
import pytest

from project_factory.data.adapters.bybit_l2 import (
    BybitPublicDataAdapter,
    _aggregate_trades_to_seconds,
    _parse_orderbook_records,
)
from project_factory.data.errors import DataSourceSchemaError


def test_parse_orderbook_records_handles_full_confirmed_record_shape():
    """This fixture uses every field in the schema confirmed by directly
    reading github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines's
    convert_to_parquet.py `parse_record()` (cloned and inspected, not
    guessed): top-level `ts`, `cts`, `type`; nested `data.u`, `data.seq`,
    `data.b`, `data.a`. This is the closest available substitute for a
    live-captured file in this sandbox (network access to Bybit is
    blocked here) — it is schema-accurate against that source's own
    parser, not a byte-for-byte real download. `cts`/`u`/`seq` are
    present (as real records have them) but unused by this adapter."""
    records = [
        {
            "ts": 1748736000123,
            "cts": 1748736000100,
            "type": "snapshot",
            "data": {
                "u": 123456789,
                "seq": 987654321,
                "b": [["67420.10", "0.842"], ["67419.90", "1.204"]],
                "a": [["67420.20", "0.512"], ["67420.30", "2.001"]],
            },
        },
        {
            "ts": 1748736000323,
            "cts": 1748736000300,
            "type": "delta",
            "data": {"u": 123456790, "seq": 987654322, "b": [["67419.90", "0.900"]], "a": []},
        },
    ]

    df = _parse_orderbook_records(records, depth=200)

    assert len(df) == 1  # only the snapshot
    assert df["bid_price_1"].iloc[0] == pytest.approx(67420.10)
    assert df["bid_size_1"].iloc[0] == pytest.approx(0.842)
    assert df["ask_price_1"].iloc[0] == pytest.approx(67420.20)


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
    with pytest.raises(DataSourceSchemaError):
        _aggregate_trades_to_seconds(trades)


def test_aggregate_trades_to_seconds_handles_empty_input():
    empty = pd.DataFrame(columns=["timestamp", "side", "size"])
    agg = _aggregate_trades_to_seconds(empty)
    assert agg.empty


def test_aggregate_trades_to_seconds_matches_real_observed_bybit_schema():
    """Regression test for the real schema mismatch found in verification:
    a real downloaded Bybit trades CSV has columns
    ['id', 'timestamp', 'price', 'volume', 'side', 'rpi'] — 'volume'
    (not 'size'), plus 'id' and 'rpi' which must be safely ignored.
    Timestamps here use millisecond-epoch magnitude (~1.7e12), matching
    Bybit's documented V5 API convention (see
    _parse_trade_timestamps's docstring) — three trades in the same
    millisecond-truncated-to-second bucket, one in the next."""
    trades = pd.DataFrame(
        {
            "id": ["2100000000007764263", "2100000000007764264", "2100000000007764265", "2100000000007764266"],
            "timestamp": [1748736000100, 1748736000400, 1748736000900, 1748736001200],
            "price": [67420.10, 67419.90, 67420.50, 67421.00],
            "volume": [0.00012, 0.00050, 0.00030, 0.00100],
            "side": ["Buy", "Sell", "Buy", "Buy"],
            "rpi": [True, False, True, False],
        }
    )

    agg = _aggregate_trades_to_seconds(trades)

    assert len(agg) == 2  # two distinct 1-second buckets after flooring
    first_bucket = agg.iloc[0]
    assert first_bucket["timestamp"] == pd.Timestamp("2025-06-01 00:00:00")
    assert first_bucket["trade_count"] == 3
    assert first_bucket["trade_signed_volume"] == pytest.approx(0.00012 - 0.00050 + 0.00030)

    second_bucket = agg.iloc[1]
    assert second_bucket["trade_count"] == 1
    assert second_bucket["trade_signed_volume"] == pytest.approx(0.00100)


def test_aggregate_trades_to_seconds_raises_on_unrecognized_side_value():
    trades = pd.DataFrame(
        {"timestamp": [1748736000100, 1748736000200], "side": ["Buy", "Unknown"], "volume": [1.0, 2.0]}
    )
    with pytest.raises(DataSourceSchemaError, match="Unknown"):
        _aggregate_trades_to_seconds(trades)


def test_parse_trade_timestamps_infers_seconds_vs_milliseconds():
    from project_factory.data.adapters.bybit_l2 import _parse_trade_timestamps

    seconds = _parse_trade_timestamps(pd.Series([1748736000.1, 1748736001.2]))
    assert abs(seconds.iloc[0] - pd.Timestamp("2025-06-01 00:00:00.1")) < pd.Timedelta(milliseconds=1)

    millis = _parse_trade_timestamps(pd.Series([1748736000100, 1748736001200]))
    assert millis.iloc[0] == pd.Timestamp("2025-06-01 00:00:00.1")


def test_parse_trade_timestamps_raises_on_implausible_magnitude():
    from project_factory.data.adapters.bybit_l2 import _parse_trade_timestamps

    with pytest.raises(DataSourceSchemaError, match="implausible"):
        _parse_trade_timestamps(pd.Series([1, 2, 3]))


def test_orderbook_url_includes_market_segment():
    """Regression test for the real 404 hit in verification: the
    order-book URL must include the market-type segment ("spot"/
    "linear"), confirmed via github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines
    source — see module docstring."""
    adapter = BybitPublicDataAdapter(symbol="BTCUSDT", market="spot", start="2025-06-01", end="2025-06-01")
    url = adapter._orderbook_url(pd.Timestamp("2025-06-01"))
    assert url == "https://quote-saver.bycsi.com/orderbook/spot/BTCUSDT/2025-06-01_BTCUSDT_ob200.data.zip"


def test_orderbook_url_futures_uses_linear_segment():
    adapter = BybitPublicDataAdapter(symbol="BTCUSDT", market="futures", start="2025-06-01", end="2025-06-01")
    url = adapter._orderbook_url(pd.Timestamp("2025-06-01"))
    assert "/orderbook/linear/BTCUSDT/" in url


def test_trades_url_unaffected_by_orderbook_fix():
    """Trades URLs were not part of the reported failure — confirm they
    stayed exactly as before."""
    adapter = BybitPublicDataAdapter(symbol="BTCUSDT", market="spot", start="2025-06-01", end="2025-06-01")
    url = adapter._trades_url(pd.Timestamp("2025-06-01"))
    assert url == "https://public.bybit.com/spot/BTCUSDT/BTCUSDT_2025-06-01.csv.gz"


def test_start_date_before_orderbook_availability_window_raises():
    with pytest.raises(ValueError, match="2025-05-01"):
        BybitPublicDataAdapter(symbol="BTCUSDT", start="2024-06-01", end="2024-06-02")


def test_start_date_within_window_does_not_raise():
    BybitPublicDataAdapter(symbol="BTCUSDT", start="2025-05-01", end="2025-05-02")  # no raise


def test_check_connectivity_checks_both_trades_and_orderbook(monkeypatch):
    """Regression test for the actual failure mode reported: connectivity
    previously only checked the trades endpoint, so a broken order-book
    URL silently passed connectivity and only failed later at load()."""
    checked_urls = []

    class FakeResponse:
        status_code = 200

    def fake_head(url, **kwargs):
        checked_urls.append(url)
        return FakeResponse()

    monkeypatch.setattr("project_factory.data.adapters.bybit_l2.httpx.head", fake_head)

    adapter = BybitPublicDataAdapter(symbol="BTCUSDT", start="2025-06-01", end="2025-06-01")
    adapter.check_connectivity()

    assert any("public.bybit.com" in u for u in checked_urls), "trades endpoint was not checked"
    assert any("quote-saver.bycsi.com" in u for u in checked_urls), "order-book endpoint was not checked"
