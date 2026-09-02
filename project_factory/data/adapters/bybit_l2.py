"""Real DataAdapter for Bybit's public historical trades + order-book
archive (Archetype B: predictive market making).

============================== VERIFICATION STATUS ==============================
This session's sandbox blocks every exchange/vendor/government domain, so
none of this has been confirmed by an HTTP round trip from inside it (see
IMPLEMENTATION_STATUS.md). A real run against this adapter (2026-09) DID
hit a live 404 on the order-book URL this docstring previously
documented — that report is what triggered the fix below. Per Gate 9,
still do NOT treat this as validated: `verification_status(...)` reports
`verified=False` until a real `load()` has actually succeeded in your
environment.

**What changed and why (root-caused from the 404, not re-guessed):**
Cloned `github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines`
(a maintained, currently-referenced Bybit downloader) directly and read
its source + README end to end — this is the strongest evidence used for
this adapter so far, since it's executable code + an explicit data-
availability table, not a search-engine snippet:
  - The order-book URL is missing a market-type path segment. Confirmed
    in two independent scripts in that repo (`download_orderbook.py`,
    `download_orderbook_stream.py`), both hardcoding:
    `https://quote-saver.bycsi.com/orderbook/spot/{SYMBOL}/{YYYY-MM-DD}_{SYMBOL}_ob200.data.zip`
    — i.e. `.../orderbook/spot/...`, not `.../orderbook/{SYMBOL}/...`.
    That missing `spot` segment is why the URL 404'd.
  - **Bybit's order-book archive only exists from May 2025 onward**
    (that repo's README: "Order Book | Available From: May 2025"; Trades
    goes back to 2020). This adapter's old default date range
    (2024-06-01..03) predates the archive entirely — it would have
    404'd on the date alone even with the URL fixed. Defaults below are
    now set inside the confirmed window.
  - `linear` (Bybit's own category name for USDT perpetual futures,
    used elsewhere in that same repo's klines downloader) is used here
    for `market="futures"` by analogy — NOT independently confirmed for
    the order-book endpoint specifically, since that repo's order-book
    downloader only implements `spot`. If futures 404s, that segment is
    the first thing to check.
  - The JSONL record schema (`ts`, `cts`, `type` in {`snapshot`,`delta`},
    nested `data.u`, `data.seq`, `data.b`, `data.a`) is confirmed by that
    repo's `convert_to_parquet.py` parser and matches this file's
    `_parse_orderbook_records` exactly — **no parsing-logic change was
    needed**, only the URL and default dates. Confirmed depth/frequency:
    200 levels per side, snapshots roughly every 200ms (per that repo's
    README); this adapter still only keeps the top 5 levels and only
    reads `snapshot` records (delta reconstruction remains a documented,
    not-yet-built extension — see the `_parse_orderbook_records`
    docstring).
  - Trades URLs were NOT part of the reported failure and are unchanged:
    `https://public.bybit.com/trading/{SYMBOL}/{SYMBOL}{YYYY-MM-DD}.csv.gz`
    (futures) / `https://public.bybit.com/spot/{SYMBOL}/{SYMBOL}_{YYYY-MM-DD}.csv.gz`
    (spot) — also independently confirmed by the same repo's README
    (`Trades | public.bybit.com/spot`).

`check_connectivity()` now checks BOTH the trades and order-book URLs
independently — it previously only checked trades, which is exactly how
a broken order-book URL passed connectivity but failed on load().
===================================================================================

LOCAL-FILE INGESTION: fetch()/load() check `cache_dir/raw/trades/` and
`cache_dir/raw/orderbook/` for files already named exactly as Bybit
itself names them (the local filename is just the URL's last path
component, unaffected by the market-segment fix above) BEFORE making any
network call. So outside this sandbox you can either let this adapter
download normally, or download the files yourself (browser, curl,
Bybit's own bulk tools) and drop them into those two directories with
their original names — either way the rest of the pipeline
(features/models/trading) runs completely unmodified.
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
ORDERBOOK_BASE_URL = "https://quote-saver.bycsi.com/orderbook"
"""Confirmed host+path shape via github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines
source (see module docstring) — the market-segment ("spot"/"linear") is
appended by _orderbook_market_segment()."""

ORDERBOOK_AVAILABLE_FROM = "2025-05-01"
"""Per that same repo's README ("Order Book | Available From: May 2025").
Requesting dates before this will 404 regardless of URL correctness."""

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data_cache" / "bybit_l2"
SOURCE_NAME = "bybit_public_data"


class BybitPublicDataAdapter:
    def __init__(
        self,
        symbol: str = "BTCUSDT",
        market: str = "spot",
        depth: int = 200,
        start: str = "2025-06-01",
        end: str = "2025-06-02",
        cache_dir: Path | None = None,
        timeout_seconds: float = 30.0,
    ):
        """start/end (YYYY-MM-DD, inclusive) live on the adapter instance
        rather than being passed to fetch()/load() — this matches the
        DataAdapter protocol's `fetch(self, spec)`/`load(self, spec)`
        signature (ProjectSpec's DataSpec has no date-range field), and
        mirrors how SyntheticMicrostructureAdapter takes its config
        (n_rows/seed) at construction time. Override the defaults by
        registering a differently-configured instance.

        Defaults are inside the confirmed order-book availability window
        (ORDERBOOK_AVAILABLE_FROM) — trades data goes back to 2020, but
        the order-book archive does not, and requesting an out-of-range
        date is a DataSourceHTTPError (404), not a code bug."""
        if pd.Timestamp(start) < pd.Timestamp(ORDERBOOK_AVAILABLE_FROM):
            raise ValueError(
                f"start={start!r} is before the order-book archive's confirmed "
                f"availability window ({ORDERBOOK_AVAILABLE_FROM}) — this would 404, "
                f"not a code bug. Trades data goes back further if that's what you need."
            )
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
        """Fail loudly and clearly if either archive isn't reachable,
        rather than letting a downstream parse error obscure the real
        problem. Checks trades AND order-book independently — checking
        only one (as an earlier version of this adapter did) is exactly
        how a broken order-book URL passed connectivity but 404'd on
        load(): trades and order-book are served from different hosts,
        so one being up says nothing about the other."""
        recent = pd.Timestamp.now("UTC").normalize() - pd.Timedelta(days=2)
        self._check_url("trades", self._trades_url(recent))
        self._check_url("order-book", self._orderbook_url(recent))

    def _check_url(self, label: str, url: str) -> None:
        try:
            resp = httpx.head(url, timeout=self.timeout_seconds, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise DataSourceNetworkError(
                f"could not reach {label} endpoint {url}: {exc}. This adapter's URLs are "
                f"unverified in the original development sandbox — see module docstring."
            ) from exc
        if resp.status_code >= 400:
            raise DataSourceHTTPError(
                f"GET {label} endpoint {url} returned HTTP {resp.status_code}. Check "
                f"symbol/market/date and see the module docstring's verification-status notes."
            )

    def _trades_url(self, date: pd.Timestamp) -> str:
        date_str = date.strftime("%Y-%m-%d")
        if self.market == "futures":
            return f"{TRADES_FUTURES_BASE_URL}/{self.symbol}/{self.symbol}{date_str}.csv.gz"
        return f"{TRADES_SPOT_BASE_URL}/{self.symbol}/{self.symbol}_{date_str}.csv.gz"

    def _orderbook_market_segment(self) -> str:
        # "spot" confirmed directly (see module docstring); "linear" is
        # Bybit's own category name for USDT perpetual futures, used by
        # analogy from that same source repo's klines downloader — NOT
        # independently confirmed for this specific endpoint.
        return "spot" if self.market == "spot" else "linear"

    def _orderbook_url(self, date: pd.Timestamp) -> str:
        date_str = date.strftime("%Y-%m-%d")
        segment = self._orderbook_market_segment()
        return f"{ORDERBOOK_BASE_URL}/{segment}/{self.symbol}/{date_str}_{self.symbol}_ob{self.depth}.data.zip"

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
