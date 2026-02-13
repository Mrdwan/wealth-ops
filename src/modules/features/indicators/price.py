"""Price-based indicators: Distance from 20-day Low.

Pure functions operating on pandas Series. No state or side effects.
"""

import pandas as pd


def distance_from_low(
    close: pd.Series,
    low: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Calculate Distance from N-day Low (Donchian proximity).

    Formula: (Close - Min(Low, N days)) / Close.
    Measures how far price is from the recent low — a pullback indicator.

    Args:
        close: Closing price series.
        low: Low price series.
        period: Lookback period (default 20).

    Returns:
        Distance ratio (0.0 = at the low, positive = above). First `period - 1` values NaN.

    Raises:
        ValueError: If period < 1 or series are empty/mismatched.
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if close.empty or low.empty:
        raise ValueError("Price series must not be empty")
    if len(close) != len(low):
        raise ValueError(
            f"Series length mismatch: close={len(close)}, low={len(low)}"
        )

    rolling_low = low.rolling(window=period, min_periods=period).min()
    result = (close - rolling_low) / close
    # Handle zero close price (shouldn't happen, but be safe)
    result = result.where(close > 0, float("nan"))

    return result
