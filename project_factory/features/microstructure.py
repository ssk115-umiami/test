"""Microstructure feature builder for Archetype B (predictive market
making, section 6). Consumes L2 snapshot + trade-aggregate rows with the
column schema documented in `SNAPSHOT_SCHEMA` below — both the real
Bybit adapter and the synthetic test adapter (data/adapters/) produce
frames in this shape, so this builder is adapter-agnostic.

Every feature here is computed from information at or before its own
row's timestamp (rolling/trailing windows only), so `available_at` for
every feature equals the row's own timestamp — the leakage risk is
entirely in the *target* (a forward-looking label), which is built
separately by `build_target` and is never a candidate feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from project_factory.features.base import FeatureDefinition

DEPTH = 5

SNAPSHOT_SCHEMA = (
    ["timestamp"]
    + [f"bid_price_{i}" for i in range(1, DEPTH + 1)]
    + [f"ask_price_{i}" for i in range(1, DEPTH + 1)]
    + [f"bid_size_{i}" for i in range(1, DEPTH + 1)]
    + [f"ask_size_{i}" for i in range(1, DEPTH + 1)]
    + ["trade_signed_volume", "trade_count"]
)
"""Required columns on the input frame. `trade_signed_volume`/
`trade_count` aggregate trades that occurred in the interval ending at
this snapshot's timestamp (positive signed volume = buyer-initiated)."""


class MicrostructureFeatureBuilder:
    def __init__(self, trailing_window: int = 5):
        self.trailing_window = trailing_window

    def transform(self, df: pd.DataFrame, spec=None) -> pd.DataFrame:
        missing = [c for c in SNAPSHOT_SCHEMA if c not in df.columns]
        if missing:
            raise ValueError(f"input frame missing required columns: {missing}")

        out = df.copy().sort_values("timestamp").reset_index(drop=True)

        bid1, ask1 = out["bid_price_1"], out["ask_price_1"]
        bid1_size, ask1_size = out["bid_size_1"], out["ask_size_1"]

        out["mid_price"] = (bid1 + ask1) / 2.0
        out["spread"] = ask1 - bid1
        out["microprice"] = (bid1 * ask1_size + ask1 * bid1_size) / (bid1_size + ask1_size)

        out["top_level_imbalance"] = (bid1_size - ask1_size) / (bid1_size + ask1_size)

        bid_size_cols = [f"bid_size_{i}" for i in range(1, DEPTH + 1)]
        ask_size_cols = [f"ask_size_{i}" for i in range(1, DEPTH + 1)]
        total_bid = out[bid_size_cols].sum(axis=1)
        total_ask = out[ask_size_cols].sum(axis=1)
        out["multi_level_imbalance"] = (total_bid - total_ask) / (total_bid + total_ask)

        w = self.trailing_window
        out["signed_trade_flow"] = out["trade_signed_volume"].rolling(w, min_periods=1).sum()
        out["trade_intensity"] = out["trade_count"].rolling(w, min_periods=1).sum()

        mid_returns = out["mid_price"].pct_change()
        out["short_horizon_returns"] = mid_returns.rolling(w, min_periods=1).sum()
        out["realized_volatility"] = mid_returns.rolling(w, min_periods=2).std()

        # These are trailing-window features: the first row's return is
        # undefined (no prior price) and pandas' rolling sum/std counts
        # that as "zero valid observations in the window" even with
        # min_periods=1, so both columns are NaN at row 0 regardless of
        # window size. Fill with 0 rather than dropping the row — the
        # walk-forward validator's first training rows would otherwise
        # silently shrink, and 0 is the correct "no information yet"
        # value for both a return and a volatility estimate.
        out["short_horizon_returns"] = out["short_horizon_returns"].fillna(0.0)
        out["realized_volatility"] = out["realized_volatility"].fillna(0.0)

        out["decision_time"] = out["timestamp"]
        for feat in self.feature_manifest():
            out[feat.available_at] = out["timestamp"]

        return out

    def feature_manifest(self) -> list[FeatureDefinition]:
        return [
            FeatureDefinition(
                name="top_level_imbalance",
                description="Best-bid vs best-ask size imbalance: (bid_size_1 - ask_size_1) / (bid_size_1 + ask_size_1).",
                economic_rationale=(
                    "A temporary excess of resting buy vs sell size at the touch reflects "
                    "short-term supply/demand pressure that tends to precede price movement "
                    "in that direction."
                ),
                source_columns=["bid_size_1", "ask_size_1"],
                calculation="(bid_size_1 - ask_size_1) / (bid_size_1 + ask_size_1)",
                available_at="timestamp",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="multi_level_imbalance",
                description="Imbalance computed over the top 5 price levels on each side.",
                economic_rationale=(
                    "Depth beyond the touch captures resting interest that a purely "
                    "top-of-book imbalance measure misses, at the cost of being slower to "
                    "reflect very recent order flow."
                ),
                source_columns=[f"bid_size_{i}" for i in range(1, DEPTH + 1)]
                + [f"ask_size_{i}" for i in range(1, DEPTH + 1)],
                calculation="(sum(bid_size_1..5) - sum(ask_size_1..5)) / (sum(bid_size_1..5) + sum(ask_size_1..5))",
                available_at="timestamp",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="microprice",
                description="Size-weighted mid price: leans toward the side with less size (the side more likely to move).",
                economic_rationale=(
                    "A standard, better-than-midpoint estimate of 'fair value' used "
                    "throughout the market-making literature; deviations of the traded "
                    "price from the microprice are a classic adverse-selection signal."
                ),
                source_columns=["bid_price_1", "ask_price_1", "bid_size_1", "ask_size_1"],
                calculation="(bid_price_1*ask_size_1 + ask_price_1*bid_size_1) / (bid_size_1+ask_size_1)",
                available_at="timestamp",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="spread",
                description="Best ask minus best bid.",
                economic_rationale="Wider spreads reflect higher uncertainty/inventory risk and lower liquidity.",
                source_columns=["ask_price_1", "bid_price_1"],
                calculation="ask_price_1 - bid_price_1",
                available_at="timestamp",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="signed_trade_flow",
                description="Trailing sum of signed trade volume (buyer-initiated positive) over the trailing window.",
                economic_rationale=(
                    "Persistent one-sided aggressive flow is informed-trader behavior in classic "
                    "market microstructure theory (Kyle/Glosten-Milgrom intuition)."
                ),
                source_columns=["trade_signed_volume"],
                calculation=f"rolling_sum(trade_signed_volume, window={self.trailing_window})",
                available_at="timestamp",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="trade_intensity",
                description="Trailing count of trades over the trailing window.",
                economic_rationale=(
                    "Elevated trading activity often precedes/accompanies volatility regime "
                    "shifts and informed trading bursts."
                ),
                source_columns=["trade_count"],
                calculation=f"rolling_sum(trade_count, window={self.trailing_window})",
                available_at="timestamp",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="short_horizon_returns",
                description=(
                    "Trailing sum of mid-price percentage returns over the trailing window "
                    "(past momentum/reversal signal)."
                ),
                economic_rationale=(
                    "Very short-horizon return autocorrelation (momentum or reversal) is a "
                    "well-documented microstructure effect."
                ),
                source_columns=["mid_price"],
                calculation=f"rolling_sum(mid_price.pct_change(), window={self.trailing_window})",
                available_at="timestamp",
                ex_ante=True,
            ),
            FeatureDefinition(
                name="realized_volatility",
                description="Trailing standard deviation of mid-price returns over the trailing window.",
                economic_rationale=(
                    "Recent realized volatility is the standard conditioning variable for "
                    "spread-setting and risk sizing."
                ),
                source_columns=["mid_price"],
                calculation=f"rolling_std(mid_price.pct_change(), window={self.trailing_window})",
                available_at="timestamp",
                ex_ante=True,
            ),
        ]


def build_target(
    df: pd.DataFrame,
    horizon: int,
    threshold: float = 0.0,
    price_column: str = "mid_price",
) -> pd.Series:
    """Binary label: 1 if `price_column` rises by more than `threshold`
    (as a fraction) over the next `horizon` rows, else 0. NaN for the
    trailing `horizon` rows where the forward window doesn't exist yet —
    callers must drop those before fitting/evaluating a model.

    This is deliberately NOT a FeatureDefinition/feature-manifest entry:
    it is the target, built from strictly future information, and must
    never be treated as a candidate model input.
    """
    future_price = df[price_column].shift(-horizon)
    forward_return = (future_price - df[price_column]) / df[price_column]
    label = (forward_return > threshold).astype(float)
    label[future_price.isna()] = np.nan
    return label
