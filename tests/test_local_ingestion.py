"""Tests for the local-file/fixture ingestion path: a user who downloads
real data outside this sandbox and drops it into an adapter's raw
directory (with the source's own filenames) should get the exact same
pipeline behavior as a live fetch, with zero network calls and zero
code changes.
"""

import gzip
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from project_factory.data.adapters.bybit_l2 import BybitPublicDataAdapter
from project_factory.data.cache import fetch_bytes_with_local_fallback
from project_factory.data.verification import mark_verified, verification_status


def _write_gz_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(df.to_csv(index=False).encode()))


def _write_orderbook_zip(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(json.dumps(r) for r in records)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.data", lines)
    path.write_bytes(buf.getvalue())


def test_local_fallback_never_calls_fetch_fn_when_file_exists(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "existing.bin").write_bytes(b"hello")

    def boom():
        raise AssertionError("fetch_fn must not run when the local file already exists")

    path = fetch_bytes_with_local_fallback(raw_dir, "existing.bin", boom)
    assert path.read_bytes() == b"hello"


def test_local_fallback_calls_fetch_fn_and_caches_when_missing(tmp_path):
    raw_dir = tmp_path / "raw"
    calls = []

    def fetch():
        calls.append(1)
        return b"downloaded"

    path1 = fetch_bytes_with_local_fallback(raw_dir, "new.bin", fetch)
    path2 = fetch_bytes_with_local_fallback(raw_dir, "new.bin", fetch)
    assert path1 == path2
    assert path1.read_bytes() == b"downloaded"
    assert len(calls) == 1  # second call found the cached/local file


def test_bybit_adapter_uses_manually_dropped_local_files_without_network(tmp_path, monkeypatch):
    """The core promise: drop files named exactly as Bybit names them
    into the adapter's raw directories, and load() uses them directly —
    no network call, no renaming, no research-code change.

    This fixture has only one order-book record (deliberately sparse,
    same shape as the Round 3 real-world bug), so it must NOT come out
    verified: load() no longer auto-marks verified, and validate()'s
    sanity gate must reject a dataset this thin rather than trust that
    it merely parsed without exceptions."""
    adapter = BybitPublicDataAdapter(
        symbol="BTCUSDT", market="spot", start="2025-06-01", end="2025-06-01", cache_dir=tmp_path
    )

    trades_df = pd.DataFrame({"timestamp": [1748736000, 1748736001], "side": ["Buy", "Sell"], "size": [1.0, 2.0]})
    _write_gz_csv(adapter.raw_trades_dir / "BTCUSDT_2025-06-01.csv.gz", trades_df)

    records = [{"type": "snapshot", "ts": 1748736000000, "data": {"b": [["100.0", "5"]], "a": [["100.1", "5"]]}}]
    _write_orderbook_zip(adapter.raw_orderbook_dir / "2025-06-01_BTCUSDT_ob200.data.zip", records)

    def fail_if_network_used(*args, **kwargs):
        raise AssertionError("no network call should happen when local files are already present")

    monkeypatch.setattr("project_factory.data.adapters.bybit_l2.httpx.get", fail_if_network_used)
    monkeypatch.setattr("project_factory.data.adapters.bybit_l2.httpx.head", fail_if_network_used)

    df = adapter.load()
    assert len(df) == 1
    assert df["bid_price_1"].iloc[0] == 100.0

    report = adapter.validate(df)
    assert report.verified is False  # one row for a full day must fail the sanity gate

    status = verification_status(adapter.cache_dir, "bybit_public_data")
    assert status.verified is False


def test_bybit_adapter_marks_verified_when_local_fixture_passes_sanity(tmp_path, monkeypatch):
    """A locally-dropped fixture that IS dense enough (covers the whole
    requested span at roughly the configured sampling cadence, with a
    clean non-crossed book) should pass the sanity gate and get marked
    verified — the gate should reject sparse data (previous test) without
    being so strict that a genuinely good dataset never verifies."""
    sampling_interval_ms = 3_600_000  # 1 hour, so a day only needs ~24-25 records
    adapter = BybitPublicDataAdapter(
        symbol="BTCUSDT",
        market="spot",
        start="2025-06-01",
        end="2025-06-01",
        cache_dir=tmp_path,
        sampling_interval_ms=sampling_interval_ms,
    )

    trades_df = pd.DataFrame({"timestamp": [1748736000, 1748736001], "side": ["Buy", "Sell"], "size": [1.0, 2.0]})
    _write_gz_csv(adapter.raw_trades_dir / "BTCUSDT_2025-06-01.csv.gz", trades_df)

    base_ts = 1748736000000
    records = [
        {
            "type": "snapshot" if i == 0 else "delta",
            "ts": base_ts + i * sampling_interval_ms,
            "data": {"b": [["100.0", "5"]], "a": [["100.1", "5"]]} if i == 0 else {"b": [], "a": []},
        }
        for i in range(25)
    ]
    _write_orderbook_zip(adapter.raw_orderbook_dir / "2025-06-01_BTCUSDT_ob200.data.zip", records)

    def fail_if_network_used(*args, **kwargs):
        raise AssertionError("no network call should happen when local files are already present")

    monkeypatch.setattr("project_factory.data.adapters.bybit_l2.httpx.get", fail_if_network_used)
    monkeypatch.setattr("project_factory.data.adapters.bybit_l2.httpx.head", fail_if_network_used)

    df = adapter.load()
    report = adapter.validate(df)
    assert report.verified is True

    status = verification_status(adapter.cache_dir, "bybit_public_data")
    assert status.verified is True


def test_verification_status_defaults_to_unverified(tmp_path):
    status = verification_status(tmp_path, "some_source")
    assert status.verified is False


def test_mark_verified_persists_across_calls(tmp_path):
    mark_verified(tmp_path, "some_source", notes="test run")
    status = verification_status(tmp_path, "some_source")
    assert status.verified is True
    assert status.notes == "test run"
    assert status.verified_at is not None
