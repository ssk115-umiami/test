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
    _LiveOrderBook,
    _orderbook_output_sanity,
    _reconstruct_and_sample_orderbook,
)
from project_factory.data.errors import DataSourceSchemaError


def test_live_order_book_snapshot_then_delta_update_insert_delete():
    """Core reconstruction semantics per bybit-exchange/docs
    v5/websocket/public/orderbook.mdx and pybit's reference
    _process_delta_orderbook: snapshot fully replaces the book; a delta's
    size==0 deletes a level, a new price inserts, an existing price
    updates."""
    book = _LiveOrderBook()
    book.reset(bids=[["100.0", "5"], ["99.9", "3"]], asks=[["100.1", "4"], ["100.2", "6"]])
    assert book.top_n(n=2) == {
        "bid_price_1": 100.0, "bid_size_1": 5.0, "ask_price_1": 100.1, "ask_size_1": 4.0,
        "bid_price_2": 99.9, "bid_size_2": 3.0, "ask_price_2": 100.2, "ask_size_2": 6.0,
    }

    # update an existing level, insert a new one, delete one (size == 0)
    book.apply_delta(bids=[["100.0", "7"], ["99.8", "1"], ["99.9", "0"]], asks=[])
    assert book.bids == {100.0: 7.0, 99.8: 1.0}
    assert book.asks == {100.1: 4.0, 100.2: 6.0}


def test_live_order_book_second_snapshot_fully_resets():
    book = _LiveOrderBook()
    book.reset(bids=[["100.0", "5"]], asks=[["100.1", "4"]])
    book.apply_delta(bids=[["99.0", "1"]], asks=[])
    assert 99.0 in book.bids

    book.reset(bids=[["50.0", "1"]], asks=[["50.1", "1"]])
    assert book.bids == {50.0: 1.0}
    assert 99.0 not in book.bids


def test_reconstruct_and_sample_orderbook_applies_deltas_before_snapshot_grid_point():
    """Regression test for the Round 3 bug: a snapshot-only extraction
    would produce 1 row here; full reconstruction with deltas applied
    must reflect the post-delta state at the sample grid point."""
    records = [
        {"ts": 0, "type": "snapshot", "data": {"b": [["100.0", "5"]], "a": [["100.1", "4"]]}},
        {"ts": 400, "type": "delta", "data": {"b": [["100.0", "9"]], "a": []}},
        {"ts": 1500, "type": "delta", "data": {"b": [["100.0", "2"]], "a": []}},
    ]
    df, diag = _reconstruct_and_sample_orderbook(records, sampling_interval_ms=1000)

    assert len(df) == 2  # grid points at 1000ms and a final row at 1500ms
    assert df["bid_size_1"].iloc[0] == pytest.approx(9.0)  # delta at 400ms applied before 1000ms sample
    assert df["bid_size_1"].iloc[1] == pytest.approx(2.0)
    assert diag["n_snapshots"] == 1
    assert diag["n_deltas"] == 2


def test_reconstruct_and_sample_orderbook_does_not_look_ahead():
    """A delta strictly AFTER a grid point must not affect that grid
    point's sample — only records with timestamp <= grid point apply."""
    records = [
        {"ts": 0, "type": "snapshot", "data": {"b": [["100.0", "5"]], "a": [["100.1", "4"]]}},
        {"ts": 1200, "type": "delta", "data": {"b": [["100.0", "999"]], "a": []}},
    ]
    df, _ = _reconstruct_and_sample_orderbook(records, sampling_interval_ms=1000)

    first_sample = df[df["timestamp"] == pd.Timestamp("1970-01-01 00:00:01.000")]
    assert len(first_sample) == 1
    assert first_sample["bid_size_1"].iloc[0] == pytest.approx(5.0)  # not yet 999


def test_reconstruct_and_sample_orderbook_counts_deltas_before_snapshot_and_sequence_anomalies():
    records = [
        {"ts": 0, "type": "delta", "data": {"b": [["1", "1"]], "a": []}},  # before any snapshot
        {"ts": 100, "type": "snapshot", "data": {"b": [["100.0", "5"]], "a": [["100.1", "4"]], "seq": 10}},
        {"ts": 200, "type": "delta", "data": {"b": [["100.0", "6"]], "a": [], "seq": 5}},  # non-increasing seq
    ]
    _, diag = _reconstruct_and_sample_orderbook(records, sampling_interval_ms=1000)

    assert diag["n_deltas_before_snapshot"] == 1
    assert diag["n_sequence_anomalies"] == 1


def test_reconstruct_and_sample_orderbook_second_snapshot_counted_as_reset():
    records = [
        {"ts": 0, "type": "snapshot", "data": {"b": [["100.0", "5"]], "a": [["100.1", "4"]]}},
        {"ts": 500, "type": "snapshot", "data": {"b": [["50.0", "1"]], "a": [["50.1", "1"]]}},
    ]
    _, diag = _reconstruct_and_sample_orderbook(records, sampling_interval_ms=1000)
    assert diag["n_resets"] == 1


def test_reconstruct_and_sample_orderbook_empty_input_returns_empty_frame_not_error():
    df, diag = _reconstruct_and_sample_orderbook([], sampling_interval_ms=1000)
    assert df.empty
    assert diag["n_records"] == 0


def test_orderbook_output_sanity_flags_the_round_3_two_row_failure():
    """Regression test for the exact real-world failure reported: 2 rows
    for a full trading day must NOT pass sanity (row_count_ok)."""
    df = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2025-06-01"), pd.Timestamp("2025-06-02")],
            "bid_price_1": [100.0, 100.0],
            "bid_size_1": [1.0, 1.0],
            "ask_price_1": [100.1, 100.1],
            "ask_size_1": [1.0, 1.0],
        }
    )
    sanity = _orderbook_output_sanity(df, sampling_interval_ms=1000, expected_span_ms=24 * 60 * 60 * 1000)
    assert sanity["sane"] is False
    assert sanity["row_count_ok"] is False


def test_orderbook_output_sanity_flags_crossed_book_and_nonpositive_size():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-06-01", periods=10, freq="1s"),
            "bid_price_1": [100.0] * 9 + [100.2],  # last row crosses (bid >= ask)
            "bid_size_1": [1.0] * 9 + [0.0],  # last row also nonpositive
            "ask_price_1": [100.1] * 10,
            "ask_size_1": [1.0] * 10,
        }
    )
    sanity = _orderbook_output_sanity(df, sampling_interval_ms=1000, expected_span_ms=10 * 1000)
    assert sanity["crossed_book_ok"] is False
    assert sanity["nonpositive_size_ok"] is False
    assert sanity["sane"] is False


def test_orderbook_output_sanity_passes_for_a_well_formed_dense_day():
    n = 86400
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-06-01", periods=n, freq="1s"),
            "bid_price_1": [100.0] * n,
            "bid_size_1": [1.0] * n,
            "ask_price_1": [100.1] * n,
            "ask_size_1": [1.0] * n,
        }
    )
    sanity = _orderbook_output_sanity(df, sampling_interval_ms=1000, expected_span_ms=24 * 60 * 60 * 1000)
    assert sanity["sane"] is True


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
