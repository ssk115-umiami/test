from project_factory.data.adapters.synthetic_power import SyntheticPowerDataAdapter

REQUIRED_COLUMNS = {
    "timestamp",
    "da_lbmp",
    "rt_lbmp",
    "da_rt_spread",
    "load_forecast",
    "load_forecast_published_at",
}


def test_generated_frame_has_required_schema(tmp_path):
    adapter = SyntheticPowerDataAdapter(n_hours=200, seed=0, cache_dir=tmp_path)
    df = adapter.load()
    assert REQUIRED_COLUMNS.issubset(df.columns)
    assert len(df) == 200


def test_fetch_is_cached_and_deterministic(tmp_path):
    adapter = SyntheticPowerDataAdapter(n_hours=100, seed=7, cache_dir=tmp_path)
    df1 = adapter.load()
    df2 = adapter.load()
    assert df1.equals(df2)


def test_load_forecast_published_well_before_the_interval(tmp_path):
    adapter = SyntheticPowerDataAdapter(n_hours=50, seed=0, cache_dir=tmp_path)
    df = adapter.load()
    assert (df["load_forecast_published_at"] < df["timestamp"]).all()


def test_da_rt_spread_is_consistent_with_da_and_rt_prices(tmp_path):
    adapter = SyntheticPowerDataAdapter(n_hours=50, seed=0, cache_dir=tmp_path)
    df = adapter.load()
    assert ((df["da_lbmp"] - df["rt_lbmp"] - df["da_rt_spread"]).abs() < 1e-9).all()


def test_scarcity_regime_rows_have_larger_spread_magnitude_on_average(tmp_path):
    """Sanity check on the injected regime signal: if scarcity blocks
    didn't actually behave differently, regime_breakdown tests downstream
    would be validating against nothing."""
    adapter = SyntheticPowerDataAdapter(n_hours=24 * 200, seed=1, scarcity_block_frac=0.05, cache_dir=tmp_path)
    df = adapter.load()
    assert df["is_scarcity_regime"].any()

    normal_abs_spread = df.loc[~df["is_scarcity_regime"], "da_rt_spread"].abs().mean()
    scarcity_abs_spread = df.loc[df["is_scarcity_regime"], "da_rt_spread"].abs().mean()
    assert scarcity_abs_spread > normal_abs_spread * 2


def test_validate_marks_source_kind_synthetic(tmp_path):
    adapter = SyntheticPowerDataAdapter(n_hours=50, seed=0, cache_dir=tmp_path)
    df = adapter.load()
    report = adapter.validate(df)
    assert report.source_kind == "synthetic"
    assert report.verified is False
