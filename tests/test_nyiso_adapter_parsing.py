"""Network-free tests for the NYISO adapter's parsing logic (the live
fetch() calls are not exercised — this sandbox blocks mis.nyiso.com, see
module docstring in nyiso.py) plus a local-ingestion end-to-end check.
"""

from pathlib import Path

import pandas as pd
import pytest

from project_factory.data.adapters.nyiso import (
    NyisoPowerDataAdapter,
    _parse_lbmp_csv,
    _parse_load_forecast_csv,
)
from project_factory.data.errors import DataSourceSchemaError


def _write_lbmp_csv(path: Path, zones: list[str], lbmp_values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for zone, lbmp in zip(zones, lbmp_values):
        rows.append(
            {
                "Time Stamp": "06/01/2024 00:00",
                "Name": zone,
                "PTID": 61761,
                "LBMP ($/MWHr)": lbmp,
                "Marginal Cost Losses ($/MWHr)": 0.5,
                "Marginal Cost Congestion ($/MWHr)": 0.1,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_load_forecast_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [
            {
                "Time Stamp": "06/01/2024 00:00",
                "File Date": "05/31/2024 04:00",
                "N.Y.C.": 5678.0,
                "Capitl": 1234.0,
                "NYISO": 18000.0,
            }
        ]
    )
    df.to_csv(path, index=False)


def test_parse_lbmp_csv_selects_requested_zone(tmp_path):
    path = tmp_path / "damlbmp_zone.csv"
    _write_lbmp_csv(path, zones=["N.Y.C.", "CAPITL"], lbmp_values=[45.5, 30.1])

    df = _parse_lbmp_csv(path, zone="N.Y.C.")
    assert len(df) == 1
    assert df["lbmp"].iloc[0] == pytest.approx(45.5)


def test_parse_lbmp_csv_zone_matching_is_case_insensitive(tmp_path):
    path = tmp_path / "damlbmp_zone.csv"
    _write_lbmp_csv(path, zones=["N.Y.C."], lbmp_values=[45.5])

    df = _parse_lbmp_csv(path, zone="n.y.c.")
    assert len(df) == 1


def test_parse_lbmp_csv_raises_with_available_zones_when_zone_missing(tmp_path):
    path = tmp_path / "damlbmp_zone.csv"
    _write_lbmp_csv(path, zones=["CAPITL", "CENTRL"], lbmp_values=[30.0, 31.0])

    with pytest.raises(DataSourceSchemaError, match="CAPITL"):
        _parse_lbmp_csv(path, zone="N.Y.C.")


def test_parse_load_forecast_csv_extracts_zone_and_publish_time(tmp_path):
    path = tmp_path / "isolf.csv"
    _write_load_forecast_csv(path)

    df = _parse_load_forecast_csv(path, zone="N.Y.C.")
    assert len(df) == 1
    assert df["load_forecast"].iloc[0] == pytest.approx(5678.0)
    assert df["load_forecast_published_at"].iloc[0] < df["timestamp"].iloc[0]


def test_parse_load_forecast_csv_raises_on_unknown_zone(tmp_path):
    path = tmp_path / "isolf.csv"
    _write_load_forecast_csv(path)
    with pytest.raises(DataSourceSchemaError):
        _parse_load_forecast_csv(path, zone="NOT_A_REAL_ZONE")


def test_nyiso_adapter_uses_manually_dropped_local_files_without_network(tmp_path, monkeypatch):
    adapter = NyisoPowerDataAdapter(zone="N.Y.C.", start="2024-06-01", end="2024-06-01", cache_dir=tmp_path)

    _write_lbmp_csv(adapter.raw_dir / "damlbmp" / "20240601damlbmp_zone.csv", ["N.Y.C."], [45.0])
    _write_lbmp_csv(adapter.raw_dir / "rtlbmp" / "20240601rtlbmp_zone.csv", ["N.Y.C."], [42.0])
    _write_load_forecast_csv(adapter.raw_dir / "isolf" / "20240601isolf.csv")

    def fail_if_network_used(*args, **kwargs):
        raise AssertionError("no network call should happen when local files are already present")

    monkeypatch.setattr("project_factory.data.adapters.nyiso.httpx.get", fail_if_network_used)
    monkeypatch.setattr("project_factory.data.adapters.nyiso.httpx.head", fail_if_network_used)

    df = adapter.load()
    assert len(df) == 1
    assert df["da_lbmp"].iloc[0] == pytest.approx(45.0)
    assert df["rt_lbmp"].iloc[0] == pytest.approx(42.0)
    assert df["da_rt_spread"].iloc[0] == pytest.approx(3.0)

    from project_factory.data.verification import verification_status

    status = verification_status(adapter.cache_dir, "nyiso_public_mis")
    assert status.verified is True
