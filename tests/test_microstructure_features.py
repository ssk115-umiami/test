import numpy as np
import pandas as pd

from project_factory.features.microstructure import MicrostructureFeatureBuilder, build_target
from project_factory.validation.leakage import audit_leakage


def _tiny_snapshot_df() -> pd.DataFrame:
    n = 10
    data = {"timestamp": pd.date_range("2024-01-01", periods=n, freq="s")}
    for level in range(1, 6):
        data[f"bid_price_{level}"] = [100.0 - level * 0.01] * n
        data[f"ask_price_{level}"] = [100.2 + level * 0.01] * n
        data[f"bid_size_{level}"] = [10.0] * n
        data[f"ask_size_{level}"] = [10.0] * n
    # asymmetric size at the touch on one row so imbalance is non-trivial
    data["bid_size_1"] = [10.0] * n
    data["bid_size_1"][3] = 30.0
    data["ask_size_1"] = [10.0] * n
    data["trade_signed_volume"] = np.zeros(n)
    data["trade_count"] = np.zeros(n)
    return pd.DataFrame(data)


def test_transform_computes_correct_microprice_and_spread():
    df = _tiny_snapshot_df()
    out = MicrostructureFeatureBuilder().transform(df)

    expected_mid = (100.0 - 0.01 + 100.2 + 0.01) / 2.0
    assert np.isclose(out["mid_price"].iloc[0], expected_mid)
    assert np.isclose(out["spread"].iloc[0], (100.2 + 0.01) - (100.0 - 0.01))

    # symmetric sizes at row 0 -> microprice == mid_price
    assert np.isclose(out["microprice"].iloc[0], out["mid_price"].iloc[0])
    assert np.isclose(out["top_level_imbalance"].iloc[0], 0.0)


def test_top_level_imbalance_reflects_size_skew():
    df = _tiny_snapshot_df()
    out = MicrostructureFeatureBuilder().transform(df)
    # row 3 has bid_size_1=30 vs ask_size_1=10 -> positive imbalance
    assert out["top_level_imbalance"].iloc[3] > 0
    expected = (30.0 - 10.0) / (30.0 + 10.0)
    assert np.isclose(out["top_level_imbalance"].iloc[3], expected)


def test_transform_raises_on_missing_columns():
    df = _tiny_snapshot_df().drop(columns=["bid_price_1"])
    try:
        MicrostructureFeatureBuilder().transform(df)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_feature_manifest_is_all_ex_ante_and_available_at_timestamp():
    manifest = MicrostructureFeatureBuilder().feature_manifest()
    assert all(f.ex_ante for f in manifest)
    assert all(f.available_at == "timestamp" for f in manifest)


def test_leakage_audit_passes_on_the_builders_own_output():
    df = _tiny_snapshot_df()
    builder = MicrostructureFeatureBuilder()
    out = builder.transform(df)
    audit = audit_leakage(out, builder.feature_manifest(), decision_time_column="decision_time")
    assert audit.passed
    assert audit.n_ex_ante_checked == len(builder.feature_manifest())


def test_build_target_forward_looking_label():
    df = pd.DataFrame({"mid_price": [100.0, 101.0, 99.0, 102.0, 102.0]})
    target = build_target(df, horizon=1, threshold=0.0)
    # row0: 100->101 up => 1; row1: 101->99 down => 0; row2: 99->102 up => 1;
    # row3: 102->102 flat, not > threshold => 0; row4: no forward data => NaN
    assert target.iloc[0] == 1.0
    assert target.iloc[1] == 0.0
    assert target.iloc[2] == 1.0
    assert target.iloc[3] == 0.0
    assert np.isnan(target.iloc[4])


def test_build_target_respects_threshold():
    df = pd.DataFrame({"mid_price": [100.0, 100.5, 100.0]})
    target = build_target(df, horizon=1, threshold=0.01)  # need >1% move
    assert target.iloc[0] == 0.0  # 0.5% move doesn't clear 1% threshold
