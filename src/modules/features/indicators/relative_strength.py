"""Relative Strength indicator.

Computes the z-scored ratio of an asset's price to its benchmark,
measuring outperformance or underperformance relative to the market.
"""

import pandas as pd


def relative_strength(
    asset_close: pd.Series,  # type: ignore[type-arg]
    benchmark_close: pd.Series,  # type: ignore[type-arg]
    z_period: int = 20,
) -> pd.Series:  # type: ignore[type-arg]
    """Calculate z-scored Relative Strength ratio.

    Formula:
        rs_ratio = asset_close / benchmark_close
        z_score = (rs_ratio - SMA(rs_ratio, z_period)) / STD(rs_ratio, z_period)

    Args:
        asset_close: Asset closing price series.
        benchmark_close: Benchmark closing price series (e.g., SPY, UUP).
            Must be aligned by date index with asset_close.
        z_period: Rolling window for z-score normalization (default 20).

    Returns:
        Z-scored relative strength series. First z_period-1 values are NaN.
    """
    rs_ratio = asset_close / benchmark_close
    rolling_mean = rs_ratio.rolling(window=z_period).mean()
    rolling_std = rs_ratio.rolling(window=z_period).std()

    # Avoid division by zero — if std is 0, z-score is 0
    z_score = (rs_ratio - rolling_mean) / rolling_std
    z_score = z_score.fillna(0.0)

    return z_score
