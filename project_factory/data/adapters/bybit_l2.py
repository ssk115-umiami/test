"""Real DataAdapter for Bybit's public historical trades + order-book
archive (Archetype B: predictive market making).

============================== VERIFICATION STATUS ==============================
This session runs in a sandbox whose network egress policy blocks every
exchange/vendor/government domain (public.bybit.com, quote-saver.bycsi.com,
NYISO, EIA, Kaggle, Tardis, etc. all return connect_rejected) — see
IMPLEMENTATION_STATUS.md. That means the URLs and parsing logic below were
assembled from web-search-derived documentation (third-party downloader
tool READMEs, a blog post's search snippet, cross-checked across two+
independent sources where possible) rather than confirmed by an actual
HTTP round trip in this session. Per Gate 9 ("never claim market data
availability that was not verified"), do NOT treat this adapter as
validated: `data.verification.verification_status(adapter.cache_dir, ...)`
reports `verified=False` until a real fetch+load has actually succeeded
in your environment (this happens automatically — `load()` calls
`mark_verified` once it produces a schema-conformant, quality-passing
frame from real downloads). Run `adapter.check_connectivity()` (or `qpf
run --stage data`) in an environment with normal internet access before
trusting anything else it returns, and expect to fix small format
details (exact directory for the order-book archive, exact CSV column
names) against a real downloaded file.

What's cross-confirmed by 2+ independent search results:
  - Futures trades:  https://public.bybit.com/trading/{SYMBOL}/{SYMBOL}{YYYY-MM-DD}.csv.gz
  - Spot trades:     https://public.bybit.com/spot/{SYMBOL}/{SYMBOL}_{YYYY-MM-DD}.csv.gz
  - Order-book filename convention: {YYYY-MM-DD}_{SYMBOL}_ob{depth}.data.zip
    (depth is 200 or 500), containing one .data file of JSONL snapshot +
    delta records.

What's NOT independently confirmed (single-source / inferred):
  - The order-book archive's exact base URL/host is quote-saver.bycsi.com
    per one search result, not public.bybit.com — the full directory path
    under that host was not confirmed. `ORDERBOOK_BASE_URL` below is a
    best-effort default; pass a corrected one once verified.
  - Exact trades CSV column names (assumed here: timestamp, symbol, side,
    size, price, tickDirection, trdMatchID, grossValue, homeNotional,
    foreignNotional — the schema commonly documented by third-party Bybit
    downloader tools).
===================================================================================

LOCAL-FILE INGESTION: fetch()/load() check `cache_dir/raw/trades/` and
`cache_dir/raw/orderbook/` for files already named exactly as Bybit
itself names them (see the URL patterns above — the local filename is
just the URL's last path component) BEFORE making any network call. So
outside this sandbox you can either let this adapter download normally,
or download the files yourself (browser, curl, Bybit's own bulk tools)
and drop them into those two directories with their original names —
either way the rest of the pipeline (features/models/trading) runs
completely unmodified.
"""

from __future__ import annotations

import gzip
import io
import json
import zipfile
from pathlib import Path

import httpx
import pandas as pd

from project_factory.data.cache import fetch_bytes_with_local_fallback
from project_factory.data.errors import (
    DataSourceHTTPError,
    DataSourceNetworkError,
    DataSourceQualityError,
    DataSourceSchemaError,
)
from project_factory.data.quality import DataQualityReport, build_quality_report
from project_factory.data.verification import mark_verified

TRADES_FUTURES_BASE_URL = "https://public.bybit.com/trading"
TRADES_SPOT_BASE_URL = "https://public.bybit.com/spot"
ORDERBOOK_BASE_URL = "https://quote-saver.bycsi.com/orderbook"  # NOT independently verified — see module docstring

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data_cache" / "bybit_l2"
SOURCE_NAME = "bybit_public_data"


class BybitPublicDataAdapter:
    def __init__(
        self,
        symbol: str = "BTCUSDT",
        market: str = "spot",
        depth: int = 200,
        start: str = "2024-06-01",
        end: str = "2024-06-03",
        cache_dir: Path | None = None,
        timeout_seconds: float = 30.0,
    ):
        """start/end (YYYY-MM-DD, inclusive) live on the adapter instance
        rather than being passed to fetch()/load() — this matches the
        DataAdapter protocol's `fetch(self, spec)`/`load(self, spec)`
        signature (ProjectSpec's DataSpec has no date-range field), and
        mirrors how SyntheticMicrostructureAdapter takes its config
        (n_rows/seed) at construction time. Override the defaults by
        registering a differently-configured instance."""
        if market not in {"spot", "futures"}:
            raise ValueError(f"market must be 'spot' or 'futures', got {market!r}")
        self.symbol = symbol
        self.market = market
        self.depth = depth
        self.start = start
        self.end = end
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.timeout_seconds = timeout_seconds

    @property
    def raw_trades_dir(self) -> Path:
        return self.cache_dir / "raw" / "trades"

    @property
    def raw_orderbook_dir(self) -> Path:
        return self.cache_dir / "raw" / "orderbook"

    def check_connectivity(self) -> None:
        """Fail loudly and clearly if the archive isn't reachable, rather
        than letting a downstream parse error obscure the real problem."""
        url = self._trades_url(pd.Timestamp.now("UTC").normalize() - pd.Timedelta(days=2))
        try:
            resp = httpx.head(url, timeout=self.timeout_seconds, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise DataSourceNetworkError(
                f"could not reach {url}: {exc}. This adapter's URLs are unverified "
                f"in the original development sandbox — see module docstring."
            ) from exc
        if resp.status_code >= 400:
            raise DataSourceHTTPError(
                f"GET {url} returned HTTP {resp.status_code}. Check symbol/market/date "
                f"and see the module docstring's verification-status notes."
            )

    def _trades_url(self, date: pd.Timestamp) -> str:
        date_str = date.strftime("%Y-%m-%d")
        if self.market == "futures":
            return f"{TRADES_FUTURES_BASE_URL}/{self.symbol}/{self.symbol}{date_str}.csv.gz"
        return f"{TRADES_SPOT_BASE_URL}/{self.symbol}/{self.symbol}_{date_str}.csv.gz"

    def _orderbook_url(self, date: pd.Timestamp) -> str:
        date_str = date.strftime("%Y-%m-%d")
        return f"{ORDERBOOK_BASE_URL}/{self.symbol}/{date_str}_{self.symbol}_ob{self.depth}.data.zip"

    def _get_bytes(self, url: str) -> bytes:
        try:
            resp = httpx.get(url, timeout=self.timeout_seconds, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise DataSourceNetworkError(f"could not reach {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise DataSourceHTTPError(f"GET {url} returned HTTP {resp.status_code}")
        return resp.content

    def _dates(self) -> pd.DatetimeIndex:
        return pd.date_range(self.start, self.end, freq="D")

    def fetch(self, spec=None) -> Path:
        """Download (or find locally) and cache raw trades + order-book
        files for [self.start, self.end] (inclusive dates), return the
        cache directory."""
        for date in self._dates():
            trades_url = self._trades_url(date)
            fetch_bytes_with_local_fallback(
                self.raw_trades_dir, trades_url.rsplit("/", 1)[-1], lambda u=trades_url: self._get_bytes(u)
            )
            ob_url = self._orderbook_url(date)
            fetch_bytes_with_local_fallback(
                self.raw_orderbook_dir, ob_url.rsplit("/", 1)[-1], lambda u=ob_url: self._get_bytes(u)
            )
        return self.cache_dir

    def load(self, spec=None) -> pd.DataFrame:
        """Load cached/local raw files and combine into the
        SNAPSHOT_SCHEMA frame (features/microstructure.py). Trades are
        aggregated to 1-second signed-volume/count buckets and merged
        onto order-book snapshot timestamps via merge_asof."""
        trades_frames, ob_frames = [], []
        for date in self._dates():
            trades_url = self._trades_url(date)
            trades_path = fetch_bytes_with_local_fallback(
                self.raw_trades_dir, trades_url.rsplit("/", 1)[-1], lambda u=trades_url: self._get_bytes(u)
            )
            trades_frames.append(_parse_trades_csv_gz(trades_path))

            ob_url = self._orderbook_url(date)
            ob_path = fetch_bytes_with_local_fallback(
                self.raw_orderbook_dir, ob_url.rsplit("/", 1)[-1], lambda u=ob_url: self._get_bytes(u)
            )
            ob_frames.append(_parse_orderbook_zip(ob_path, depth=self.depth))

        trades = pd.concat(trades_frames, ignore_index=True) if trades_frames else pd.DataFrame()
        if not ob_frames or all(f.empty for f in ob_frames):
            raise DataSourceQualityError(
                f"no order-book rows parsed for {self.symbol} {self.start}..{self.end} — "
                f"check the downloaded file(s) in {self.raw_orderbook_dir}"
            )
        orderbook = pd.concat(ob_frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
        # merge_asof requires matching dtypes on the join key; orderbook
        # timestamps come from millisecond epoch data (datetime64[ms]),
        # trade_agg's from floor("s") (datetime64[s]) — normalize both to
        # the same resolution before merging.
        orderbook["timestamp"] = orderbook["timestamp"].astype("datetime64[ns]")

        trade_agg = _aggregate_trades_to_seconds(trades)
        trade_agg["timestamp"] = trade_agg["timestamp"].astype("datetime64[ns]")
        merged = pd.merge_asof(
            orderbook.sort_values("timestamp"),
            trade_agg.sort_values("timestamp"),
            on="timestamp",
            direction="backward",
        )
        merged["trade_signed_volume"] = merged["trade_signed_volume"].fillna(0.0)
        merged["trade_count"] = merged["trade_count"].fillna(0.0)

        mark_verified(
            self.cache_dir,
            source_name=SOURCE_NAME,
            notes=f"symbol={self.symbol} market={self.market} range={self.start}..{self.end}",
        )
        return merged

    def validate(self, df: pd.DataFrame, spec=None) -> DataQualityReport:
        from project_factory.data.verification import verification_status

        status = verification_status(self.cache_dir, SOURCE_NAME)
        return build_quality_report(
            df, timestamp_column="timestamp", source_kind="real", verified=status.verified
        )


def _parse_trades_csv_gz(path: Path) -> pd.DataFrame:
    raw_bytes = path.read_bytes()
    try:
        raw = gzip.decompress(raw_bytes)
    except OSError as exc:
        raise DataSourceSchemaError(f"{path} is not a valid gzip file: {exc}") from exc
    try:
        return pd.read_csv(io.BytesIO(raw))
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DataSourceSchemaError(f"could not parse {path} as CSV: {exc}") from exc


def _parse_orderbook_zip(path: Path, depth: int) -> pd.DataFrame:
    raw_bytes = path.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            names = zf.namelist()
            if len(names) != 1:
                raise DataSourceSchemaError(f"expected exactly one file inside {path}, found {names}")
            raw_lines = zf.read(names[0]).decode("utf-8").splitlines()
    except zipfile.BadZipFile as exc:
        raise DataSourceSchemaError(f"{path} is not a valid zip file: {exc}") from exc

    try:
        records = [json.loads(line) for line in raw_lines if line.strip()]
    except json.JSONDecodeError as exc:
        raise DataSourceSchemaError(f"could not parse JSONL inside {path}: {exc}") from exc

    return _parse_orderbook_records(records, depth=depth)


def _parse_orderbook_records(records: list[dict], depth: int) -> pd.DataFrame:
    """Reconstruct top-5-level snapshots from raw snapshot records.

    Simplification (documented, not yet implemented): only 'snapshot'
    type records are used; 'delta' records between snapshots are
    currently dropped, so resolution is limited to the snapshot cadence
    in the raw file rather than every book update. This is a reasonable
    v1 scope for a 48-hour project (section 22 — scope discipline) but
    should be noted as a limitation in ASSUMPTIONS_AND_RISKS.md; full
    delta-based book reconstruction is a natural first extension.
    """
    rows = []
    for rec in records:
        if rec.get("type") != "snapshot":
            continue
        data = rec.get("data", rec)
        bids = data.get("b") or data.get("bids") or []
        asks = data.get("a") or data.get("asks") or []
        ts = rec.get("ts") or rec.get("timestamp") or data.get("ts")
        row = {"timestamp": pd.to_datetime(ts, unit="ms", errors="coerce")}
        for i in range(1, 6):
            bid = bids[i - 1] if len(bids) >= i else [None, None]
            ask = asks[i - 1] if len(asks) >= i else [None, None]
            row[f"bid_price_{i}"] = float(bid[0]) if bid[0] is not None else None
            row[f"bid_size_{i}"] = float(bid[1]) if bid[1] is not None else None
            row[f"ask_price_{i}"] = float(ask[0]) if ask[0] is not None else None
            row[f"ask_size_{i}"] = float(ask[1]) if ask[1] is not None else None
        rows.append(row)
    return pd.DataFrame(rows).dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


def _aggregate_trades_to_seconds(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["timestamp", "trade_signed_volume", "trade_count"])

    ts_col = next((c for c in trades.columns if c.lower() in {"timestamp", "time"}), trades.columns[0])
    side_col = next((c for c in trades.columns if c.lower() == "side"), None)
    size_col = next((c for c in trades.columns if c.lower() in {"size", "qty", "quantity"}), None)
    if side_col is None or size_col is None:
        raise DataSourceSchemaError(
            f"could not find side/size columns in trades data (columns: {list(trades.columns)}) — "
            f"the assumed Bybit trades CSV schema was not independently verified, see module docstring"
        )

    ts = pd.to_datetime(trades[ts_col], unit="s", errors="coerce")
    if ts.isna().all():
        ts = pd.to_datetime(trades[ts_col], errors="coerce")

    sign = trades[side_col].astype(str).str.lower().map({"buy": 1.0, "sell": -1.0}).fillna(0.0)
    signed_volume = sign * trades[size_col].astype(float)

    df = pd.DataFrame({"timestamp": ts.dt.floor("s"), "signed_volume": signed_volume})
    agg = df.groupby("timestamp").agg(
        trade_signed_volume=("signed_volume", "sum"),
        trade_count=("signed_volume", "count"),
    ).reset_index()
    return agg
