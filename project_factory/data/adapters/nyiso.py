"""Real DataAdapter for NYISO's public MIS CSV archive (Archetype A:
power regime / DA-RT research).

============================== VERIFICATION STATUS ==============================
Built in the same sandbox as bybit_l2.py, which blocks every exchange/
vendor/government domain including mis.nyiso.com — see
IMPLEMENTATION_STATUS.md. NOT network-verified in this session. Unlike
the Bybit order-book path, this one is unusually well cross-confirmed
for something that couldn't be hit directly:

  1. A web search independently reported the URL pattern
     `http://mis.nyiso.com/public/csv/damlbmp/{YYYYMMDD}damlbmp_zone.csv`
     and the monthly-zip pattern `{YYYYMM01}damlbmp_zone_csv.zip`.
  2. `gridstatus` (github.com/kmax12/gridstatus), a maintained open-source
     library that other people actually run against live NYISO data, was
     fetched directly via raw.githubusercontent.com (reachable in this
     sandbox) and its `nyiso.py` source read line by line. It independently
     confirms: dataset names (`damlbmp`, `rtlbmp`, `isolf`), the exact URL
     construction (`_download_nyiso_archive`, line ~1456/1464), the daily-
     vs-monthly-zip retention split (~7 days), the raw CSV column names
     ("Time Stamp", "Name", "LBMP ($/MWHr)", "Marginal Cost Losses
     ($/MWHr)", "Marginal Cost Congestion ($/MWHr)" for LBMP; "Time
     Stamp", "File Date", zone columns including "N.Y.C." for isolf), and
     that "File Date" is literally the forecast's publish timestamp
     (distinct from the interval it describes) — exactly the ex-ante/
     available_at split this project needs.

Still NOT independently confirmed: the exact zone-name string formatting
(",Name" values may be "N.Y.C." or a variant), whether the direct-CSV
retention window is still ~7 days, and whether any of this has changed
since gridstatus's version was written. Per Gate 9, do not treat this as
validated until `verification_status(...).verified` is True in your
environment (set automatically by a real `load()` that succeeds).

LOCAL-FILE INGESTION: exactly like bybit_l2.py — fetch()/load() check
`cache_dir/raw/{damlbmp,rtlbmp,isolf}/{YYYYMMDD}{dataset}[_zone].csv`
for a file already there (NYISO's own per-day filename, whether you
downloaded it directly or unzipped it from one of NYISO's monthly
bundles) before making any network call.
===================================================================================
"""

from __future__ import annotations

import io
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
from project_factory.data.verification import mark_verified, verification_status

BASE_URL = "http://mis.nyiso.com/public/csv"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data_cache" / "nyiso"
SOURCE_NAME = "nyiso_public_mis"

DAM_DATASET = "damlbmp"
DAM_FILENAME = "damlbmp_zone"
RT_DATASET = "rtlbmp"
RT_FILENAME = "rtlbmp_zone"
LOAD_FORECAST_DATASET = "isolf"
LOAD_FORECAST_FILENAME = "isolf"


class NyisoPowerDataAdapter:
    def __init__(
        self,
        zone: str = "N.Y.C.",
        start: str = "2024-06-01",
        end: str = "2024-06-03",
        cache_dir: Path | None = None,
        timeout_seconds: float = 30.0,
    ):
        """zone: the NYISO load-zone name as it appears in the raw
        "Name" column of the LBMP CSVs (and, unmodified, as a load-
        forecast column header — see module docstring). start/end
        (YYYY-MM-DD, inclusive) live on the instance for the same reason
        as BybitPublicDataAdapter's (DataAdapter protocol has no
        date-range parameter). Comparison-zone / multi-zone spread
        features are a documented v2 extension, not built here (section
        22 scope discipline, matching bybit_l2.py's own scope cuts)."""
        self.zone = zone
        self.start = start
        self.end = end
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.timeout_seconds = timeout_seconds

    @property
    def raw_dir(self) -> Path:
        return self.cache_dir / "raw"

    def _dates(self) -> pd.DatetimeIndex:
        return pd.date_range(self.start, self.end, freq="D")

    def _daily_csv_url(self, dataset_name: str, filename: str, date: pd.Timestamp) -> str:
        return f"{BASE_URL}/{dataset_name}/{date:%Y%m%d}{filename}.csv"

    def _monthly_zip_url(self, dataset_name: str, filename: str, date: pd.Timestamp) -> str:
        return f"{BASE_URL}/{dataset_name}/{date:%Y%m}01{filename}_csv.zip"

    def _local_filename(self, filename: str, date: pd.Timestamp) -> str:
        return f"{date:%Y%m%d}{filename}.csv"

    def check_connectivity(self) -> None:
        """Fail loudly and clearly if the archive isn't reachable."""
        recent = pd.Timestamp.now("UTC").normalize() - pd.Timedelta(days=2)
        url = self._daily_csv_url(DAM_DATASET, DAM_FILENAME, recent)
        try:
            resp = httpx.head(url, timeout=self.timeout_seconds, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise DataSourceNetworkError(
                f"could not reach {url}: {exc}. This adapter's URLs are unverified "
                f"in the original development sandbox — see module docstring."
            ) from exc
        if resp.status_code >= 400:
            raise DataSourceHTTPError(
                f"GET {url} returned HTTP {resp.status_code}. See the module "
                f"docstring's verification-status notes."
            )

    def _get_bytes(self, url: str) -> bytes:
        try:
            resp = httpx.get(url, timeout=self.timeout_seconds, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise DataSourceNetworkError(f"could not reach {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise DataSourceHTTPError(f"GET {url} returned HTTP {resp.status_code}")
        return resp.content

    def _fetch_dataset_day(self, dataset_name: str, filename: str, date: pd.Timestamp) -> Path:
        local_name = self._local_filename(filename, date)

        def fetch_fn() -> bytes:
            try:
                return self._get_bytes(self._daily_csv_url(dataset_name, filename, date))
            except DataSourceHTTPError:
                # Likely older than the direct-CSV retention window (~7
                # days per gridstatus) — fall back to the monthly zip
                # archive and extract this day's own file from it.
                zip_bytes = self._get_bytes(self._monthly_zip_url(dataset_name, filename, date))
                return _extract_member_from_zip(zip_bytes, local_name)

        return fetch_bytes_with_local_fallback(self.raw_dir / dataset_name, local_name, fetch_fn)

    def fetch(self, spec=None) -> Path:
        for date in self._dates():
            self._fetch_dataset_day(DAM_DATASET, DAM_FILENAME, date)
            self._fetch_dataset_day(RT_DATASET, RT_FILENAME, date)
            self._fetch_dataset_day(LOAD_FORECAST_DATASET, LOAD_FORECAST_FILENAME, date)
        return self.cache_dir

    def load(self, spec=None) -> pd.DataFrame:
        """Load cached/local raw files and combine into a tidy hourly
        frame: timestamp, da_lbmp, rt_lbmp, da_rt_spread, load_forecast,
        load_forecast_published_at (the ex-ante `available_at` for the
        forecast feature — see PowerFeatureBuilder)."""
        dam_frames, rt_frames, lf_frames = [], [], []
        for date in self._dates():
            dam_path = self._fetch_dataset_day(DAM_DATASET, DAM_FILENAME, date)
            rt_path = self._fetch_dataset_day(RT_DATASET, RT_FILENAME, date)
            lf_path = self._fetch_dataset_day(LOAD_FORECAST_DATASET, LOAD_FORECAST_FILENAME, date)
            dam_frames.append(_parse_lbmp_csv(dam_path, self.zone))
            rt_frames.append(_parse_lbmp_csv(rt_path, self.zone))
            lf_frames.append(_parse_load_forecast_csv(lf_path, self.zone))

        dam = pd.concat(dam_frames, ignore_index=True).rename(columns={"lbmp": "da_lbmp"})
        rt = pd.concat(rt_frames, ignore_index=True).rename(columns={"lbmp": "rt_lbmp"})
        lf = pd.concat(lf_frames, ignore_index=True)

        merged = dam.merge(rt, on="timestamp", how="inner")
        merged = merged.merge(lf, on="timestamp", how="left")
        merged["da_rt_spread"] = merged["da_lbmp"] - merged["rt_lbmp"]
        merged = merged.sort_values("timestamp").reset_index(drop=True)

        if merged.empty:
            raise DataSourceQualityError(
                f"no overlapping DA/RT rows for zone={self.zone!r} in "
                f"{self.start}..{self.end} — check the downloaded files in {self.raw_dir}"
            )

        mark_verified(self.cache_dir, source_name=SOURCE_NAME, notes=f"zone={self.zone} range={self.start}..{self.end}")
        return merged

    def validate(self, df: pd.DataFrame, spec=None) -> DataQualityReport:
        status = verification_status(self.cache_dir, SOURCE_NAME)
        return build_quality_report(
            df,
            timestamp_column="timestamp",
            expected_frequency=pd.Timedelta(hours=1),
            source_kind="real",
            verified=status.verified,
        )


def _extract_member_from_zip(zip_bytes: bytes, member_name: str) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            match = next((n for n in names if n.lower() == member_name.lower()), None)
            if match is None:
                raise DataSourceSchemaError(
                    f"{member_name!r} not found inside monthly zip archive; contents: {names}"
                )
            return zf.read(match)
    except zipfile.BadZipFile as exc:
        raise DataSourceSchemaError(f"downloaded monthly archive is not a valid zip file: {exc}") from exc


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DataSourceSchemaError(f"could not parse {path} as CSV: {exc}") from exc


def _find_column(columns, candidates: set[str]) -> str | None:
    return next((c for c in columns if c.strip().lower() in candidates), None)


def _parse_lbmp_csv(path: Path, zone: str) -> pd.DataFrame:
    df = _read_csv(path)
    ts_col = _find_column(df.columns, {"time stamp", "timestamp"})
    name_col = _find_column(df.columns, {"name"})
    lbmp_col = next((c for c in df.columns if "lbmp" in c.lower()), None)
    if ts_col is None or name_col is None or lbmp_col is None:
        raise DataSourceSchemaError(
            f"unexpected LBMP CSV columns in {path}: {list(df.columns)} — "
            f"expected 'Time Stamp', 'Name', and an 'LBMP' column (see module docstring)"
        )

    available_zones = sorted(df[name_col].astype(str).str.strip().unique())
    matched = df[df[name_col].astype(str).str.strip().str.lower() == zone.strip().lower()]
    if matched.empty:
        raise DataSourceSchemaError(
            f"zone {zone!r} not found in {path}; available zones: {available_zones}"
        )

    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(matched[ts_col], errors="coerce"),
            "lbmp": pd.to_numeric(matched[lbmp_col], errors="coerce"),
        }
    )
    return out.dropna(subset=["timestamp"]).reset_index(drop=True)


def _parse_load_forecast_csv(path: Path, zone: str) -> pd.DataFrame:
    df = _read_csv(path)
    ts_col = _find_column(df.columns, {"time stamp", "timestamp"})
    file_date_col = _find_column(df.columns, {"file date"})
    zone_col = next((c for c in df.columns if c.strip().lower() == zone.strip().lower()), None)
    if ts_col is None or file_date_col is None or zone_col is None:
        raise DataSourceSchemaError(
            f"unexpected load-forecast CSV columns in {path}: {list(df.columns)} — "
            f"expected 'Time Stamp', 'File Date', and a column matching zone={zone!r} "
            f"(see module docstring)"
        )

    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df[ts_col], errors="coerce"),
            "load_forecast": pd.to_numeric(df[zone_col], errors="coerce"),
            "load_forecast_published_at": pd.to_datetime(df[file_date_col], errors="coerce"),
        }
    )
    return out.dropna(subset=["timestamp"]).reset_index(drop=True)
