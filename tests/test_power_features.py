import numpy as np
import pandas as pd

from project_factory.data.adapters.synthetic_power import SyntheticPowerDataAdapter
from project_factory.features.power import PowerFeatureBuilder, build_target
from project_factory.validation.leakage import audit_leakage


def _tiny_power_df() -> pd.DataFrame:
    n = 10
    timestamps = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "da_lbmp": np.linspace(30, 39, n),
            "rt_lbmp": np.linspace(31, 41, n),
            "da_rt_spread": np.linspace(30, 39, n) - np.linspace(31, 41, n),
            "load_forecast": np.linspace(1000, 1090, n),
            "load_forecast_published_at": timestamps - pd.Timedelta(hours=20),
        }
    )


def test_transform_raises_on_missing_columns():
    df = _tiny_power_df().drop(columns=["load_forecast"])
    try:
        PowerFeatureBuilder().transform(df)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_lagged_spread_matches_shifted_column():
    df = _tiny_power_df()
    out = PowerFeatureBuilder(spread_lag_hours=1).transform(df)
    expected = df["da_rt_spread"].shift(1).fillna(0.0)
    assert np.allclose(out["lagged_da_rt_spread"], expected)


def test_calendar_features_are_correct():
    df = _tiny_power_df()
    out = PowerFeatureBuilder().transform(df)
    assert out["hour_of_day"].tolist() == list(range(10))
    assert (out["month"] == 1).all()


def test_feature_manifest_is_all_ex_ante():
    manifest = PowerFeatureBuilder().feature_manifest()
    assert all(f.ex_ante for f in manifest)


def test_leakage_audit_passes_on_the_builders_own_output():
    df = _tiny_power_df()
    builder = PowerFeatureBuilder()
    out = builder.transform(df)
    audit = audit_leakage(out, builder.feature_manifest(), decision_time_column="decision_time")
    assert audit.passed, audit.violations
    assert audit.n_ex_ante_checked == len(builder.feature_manifest())


def test_build_target_is_same_row_da_rt_spread():
    df = _tiny_power_df()
    target = build_target(df)
    assert np.allclose(target, df["da_rt_spread"])
    assert target.isna().sum() == 0


def test_leakage_audit_passes_on_synthetic_data_end_to_end(tmp_path):
    adapter = SyntheticPowerDataAdapter(n_hours=500, seed=0, cache_dir=tmp_path)
    raw = adapter.load()
    builder = PowerFeatureBuilder()
    features = builder.transform(raw)
    audit = audit_leakage(features, builder.feature_manifest(), decision_time_column="decision_time")
    assert audit.passed, audit.violations
