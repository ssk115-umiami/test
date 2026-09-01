"""Power feature builder for Archetype A (regime-aware DA-RT spread
forecasting, section 6). Consumes the tidy hourly schema both
NyisoPowerDataAdapter and SyntheticPowerDataAdapter produce: timestamp,
da_lbmp, rt_lbmp, da_rt_spread, load_forecast,
load_forecast_published_at.

Ex-ante discipline (section 3.7): the day-ahead price and the load
forecast are both legitimately knowable well before the real-time
interval they describe settles — `load_forecast_published_at` is the
real, source-reported timestamp for exactly when (NYISO's own "File
Date" column; see data/adapters/nyiso.py). `rt_lbmp` itself is never a
feature; it only ever appears in the target.
"""

from __future__ import annotations

import pandas as pd

from project_factory.features.base import FeatureDefinition

REQUIRED_COLUMNS = {
    "timestamp",
    "da_lbmp",
    "rt_lbmp",
    "da_rt_spread",
    "load_forecast",
    "load_forecast_published_at",
}


class PowerFeatureBuilder:
    def __init__(self, spread_lag_hours: int = 1, rolling_window_hours: int = 24, decision_lead_hours: int = 1):
        self.spread_lag_hours = spread_lag_hours
        self.rolling_window_hours = rolling_window_hours
        self.decision_lead_hours = decision_lead_hours
        """decision_lead_hours: how long before an hour's RT settlement
        the decision must be made — a conservative buffer, not a claim
        about the real DA-market-close timing."""

    def transform(self, df: pd.DataFrame, spec=None) -> pd.DataFrame:
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"input frame missing required columns: {missing}")

        out = df.copy().sort_values("timestamp").reset_index(drop=True)
        out["timestamp"] = pd.to_datetime(out["timestamp"])
        out["load_forecast_published_at"] = pd.to_datetime(out["load_forecast_published_at"])

        out["decision_time"] = out["timestamp"] - pd.Timedelta(hours=self.decision_lead_hours)

        out["hour_of_day"] = out["timestamp"].dt.hour
        out["day_of_week"] = out["timestamp"].dt.dayofweek
        out["month"] = out["timestamp"].dt.month

        out["lagged_da_rt_spread"] = out["da_rt_spread"].shift(self.spread_lag_hours)
        past_spread = out["da_rt_spread"].shift(1)
        out["rolling_spread_mean"] = past_spread.rolling(self.rolling_window_hours, min_periods=1).mean()
        out["rolling_spread_std"] = past_spread.rolling(self.rolling_window_hours, min_periods=2).std()
        out["lagged_da_rt_spread"] = out["lagged_da_rt_spread"].fillna(0.0)
        out["rolling_spread_mean"] = out["rolling_spread_mean"].fillna(0.0)
        out["rolling_spread_std"] = out["rolling_spread_std"].fillna(0.0)

        out["da_lbmp_feature"] = out["da_lbmp"]
        out["load_forecast_feature"] = out["load_forecast"]

        out["hour_of_day_available_at"] = out["decision_time"]
        out["day_of_week_available_at"] = out["decision_time"]
        out["month_available_at"] = out["decision_time"]
        out["lagged_da_rt_spread_available_at"] = out["timestamp"] - pd.Timedelta(hours=self.spread_lag_hours)
        out["rolling_spread_mean_available_at"] = out["timestamp"] - pd.Timedelta(hours=1)
        out["rolling_spread_std_available_at"] = out["timestamp"] - pd.Timedelta(hours=1)
        out["da_lbmp_feature_available_at"] = out["load_forecast_published_at"]
        out["load_forecast_feature_available_at"] = out["load_forecast_published_at"]

        return out

    def feature_manifest(self) -> list[FeatureDefinition]:
        return [
            FeatureDefinition(
                name="hour_of_day",
                description="Hour of the interval being forecast (0-23).",
                economic_rationale="Load and price have strong, well-known diurnal patterns.",
                source_columns=["timestamp"],
                calculation="timestamp.hour",
                available_at="hour_of_day_available_at",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="day_of_week",
                description="Day of week of the interval being forecast.",
                economic_rationale="Weekday/weekend load and price patterns differ materially.",
                source_columns=["timestamp"],
                calculation="timestamp.dayofweek",
                available_at="day_of_week_available_at",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="month",
                description="Calendar month of the interval being forecast.",
                economic_rationale="Seasonal demand (heating/cooling) drives price-level regime shifts.",
                source_columns=["timestamp"],
                calculation="timestamp.month",
                available_at="month_available_at",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="lagged_da_rt_spread",
                description=f"DA-RT spread from {self.spread_lag_hours} hour(s) before the forecasted interval.",
                economic_rationale=(
                    "Recent dislocations are informative about currently-elevated "
                    "congestion/uncertainty that tends to persist over short horizons."
                ),
                source_columns=["da_rt_spread"],
                calculation=f"da_rt_spread.shift({self.spread_lag_hours})",
                available_at="lagged_da_rt_spread_available_at",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="rolling_spread_mean",
                description="Trailing mean DA-RT spread over the rolling window, excluding the current hour.",
                economic_rationale="A slow-moving baseline for 'how dislocated has this zone been lately'.",
                source_columns=["da_rt_spread"],
                calculation=f"da_rt_spread.shift(1).rolling({self.rolling_window_hours}).mean()",
                available_at="rolling_spread_mean_available_at",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="rolling_spread_std",
                description="Trailing std of DA-RT spread over the rolling window, excluding the current hour.",
                economic_rationale=(
                    "Recent spread volatility is the natural conditioning variable for a "
                    "no-trade / sizing rule under uncertainty (section 6)."
                ),
                source_columns=["da_rt_spread"],
                calculation=f"da_rt_spread.shift(1).rolling({self.rolling_window_hours}).std()",
                available_at="rolling_spread_std_available_at",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="da_lbmp_feature",
                description="Day-ahead LBMP for the interval being forecast.",
                economic_rationale=(
                    "The day-ahead price is cleared and published well before the real-time "
                    "interval it describes settles, so it is legitimately known at decision time."
                ),
                source_columns=["da_lbmp"],
                calculation="da_lbmp",
                available_at="da_lbmp_feature_available_at",
                ex_ante=True,
                leakage_risk_notes=(
                    "available_at is approximated using the load forecast's publish "
                    "timestamp as a proxy for 'DA market close', since the raw NYISO DA "
                    "LBMP file does not itself carry a separate publish timestamp — "
                    "verify this timing assumption once real data is flowing."
                ),
            ),
            FeatureDefinition(
                name="load_forecast_feature",
                description="ISO load forecast for the interval being forecast.",
                economic_rationale="Forecast load level is the primary driver of expected scarcity/congestion.",
                source_columns=["load_forecast"],
                calculation="load_forecast",
                available_at="load_forecast_feature_available_at",
                ex_ante=True,
            ),
        ]


def build_target(df: pd.DataFrame) -> pd.Series:
    """The DA-RT spread for the interval itself. Unlike the market-making
    archetype's target (a forward-looking label built from a future row,
    since the whole point there is short-horizon prediction), the power
    target needs no shift: `da_rt_spread` for hour t is realized when RT
    settles at hour t, which is strictly after `decision_time` (t minus
    `decision_lead_hours`) — so it's a legitimate same-row regression
    target, not a leak. It is intentionally not part of the feature
    manifest above; it must never be used as a model input."""
    return df["da_rt_spread"].astype(float)
