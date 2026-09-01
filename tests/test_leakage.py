import pandas as pd
import pytest

from project_factory.data.timestamps import LookaheadError, assert_ex_ante, shift_available_at
from project_factory.features.base import FeatureDefinition
from project_factory.validation.leakage import audit_leakage, safe_feature_columns


def _df():
    decision_time = pd.date_range("2024-01-01", periods=5, freq="h")
    return pd.DataFrame(
        {
            "decision_time": decision_time,
            "legit_feature": [1, 2, 3, 4, 5],
            "legit_available_at": decision_time,  # known exactly at decision time
            "leaky_feature": [1, 2, 3, 4, 5],
            "leaky_available_at": decision_time + pd.Timedelta(hours=1),  # known too late
        }
    )


def _manifest():
    return [
        FeatureDefinition(
            name="legit_feature",
            description="d",
            economic_rationale="r",
            source_columns=["legit_feature"],
            calculation="c",
            available_at="legit_available_at",
            ex_ante=True,
        ),
        FeatureDefinition(
            name="leaky_feature",
            description="d",
            economic_rationale="r",
            source_columns=["leaky_feature"],
            calculation="c",
            available_at="leaky_available_at",
            ex_ante=True,
        ),
        FeatureDefinition(
            name="diagnostic_only",
            description="ex-post diagnostic, never a model input",
            economic_rationale="r",
            source_columns=["leaky_feature"],
            calculation="c",
            available_at="leaky_available_at",
            ex_ante=False,
        ),
    ]


def test_audit_catches_the_leaky_feature_and_passes_the_legit_one():
    df = _df()
    report = audit_leakage(df, _manifest(), decision_time_column="decision_time")

    assert report.passed is False
    assert "leaky_feature" in report.unsafe_features
    assert "legit_feature" not in report.unsafe_features
    # ex-post feature is never checked (it's not a candidate model input)
    assert report.n_ex_ante_checked == 2
    assert report.n_ex_post_excluded == 1


def test_safe_feature_columns_excludes_unsafe_and_ex_post():
    df = _df()
    manifest = _manifest()
    report = audit_leakage(df, manifest, decision_time_column="decision_time")
    safe = safe_feature_columns(manifest, report)

    assert safe == ["legit_feature"]


def test_assert_ex_ante_raises_lookahead_error():
    decision_time = pd.Series(pd.date_range("2024-01-01", periods=3, freq="h"))
    available_at = decision_time + pd.Timedelta(minutes=1)
    with pytest.raises(LookaheadError):
        assert_ex_ante(available_at, decision_time, feature_name="bad_feature")


def test_assert_ex_ante_allows_equal_timestamps():
    decision_time = pd.Series(pd.date_range("2024-01-01", periods=3, freq="h"))
    assert_ex_ante(decision_time, decision_time, feature_name="ok_feature")  # no raise


def test_shift_available_at_applies_publication_lag():
    base = pd.Series(pd.date_range("2024-01-01", periods=3, freq="h"))
    shifted = shift_available_at(base, pd.Timedelta(hours=6))
    assert (shifted - base == pd.Timedelta(hours=6)).all()
