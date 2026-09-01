import numpy as np

from project_factory.data.adapters.synthetic_microstructure import SyntheticMicrostructureAdapter
from project_factory.features.microstructure import SNAPSHOT_SCHEMA, MicrostructureFeatureBuilder, build_target


def test_generated_frame_matches_required_schema(tmp_path):
    adapter = SyntheticMicrostructureAdapter(n_rows=200, seed=0, cache_dir=tmp_path)
    df = adapter.load()
    for col in SNAPSHOT_SCHEMA:
        assert col in df.columns, f"missing column {col}"
    assert len(df) == 200


def test_fetch_is_cached_and_deterministic(tmp_path):
    adapter = SyntheticMicrostructureAdapter(n_rows=100, seed=42, cache_dir=tmp_path)
    df1 = adapter.load()
    df2 = adapter.load()
    assert df1.equals(df2)


def test_different_seeds_produce_different_data(tmp_path):
    a = SyntheticMicrostructureAdapter(n_rows=100, seed=1, cache_dir=tmp_path).load()
    b = SyntheticMicrostructureAdapter(n_rows=100, seed=2, cache_dir=tmp_path).load()
    assert not a["bid_price_1"].equals(b["bid_price_1"])


def test_validate_reports_no_gaps_for_regular_second_cadence(tmp_path):
    adapter = SyntheticMicrostructureAdapter(n_rows=200, seed=0, cache_dir=tmp_path)
    df = adapter.load()
    report = adapter.validate(df)
    assert not report.gaps_detected
    assert not report.has_duplicate_timestamps


def test_injected_signal_is_genuinely_learnable(tmp_path):
    """Sanity check on the synthetic data itself: top_level_imbalance
    should be weakly but measurably correlated with the next-step
    return, since that's the whole point of injecting a latent signal —
    otherwise every downstream model test would be validating against
    pure noise."""
    adapter = SyntheticMicrostructureAdapter(n_rows=3000, seed=0, signal_strength=1.5, cache_dir=tmp_path)
    df = adapter.load()
    features = MicrostructureFeatureBuilder().transform(df)
    target = build_target(features, horizon=1, threshold=0.0)

    valid = target.notna()
    imbalance = features.loc[valid, "top_level_imbalance"]
    y = target.loc[valid]

    corr = np.corrcoef(imbalance, y)[0, 1]
    assert corr > 0.03, f"expected a measurable positive correlation, got {corr}"
