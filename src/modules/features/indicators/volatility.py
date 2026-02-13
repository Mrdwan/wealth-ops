"""Volatility indicators: ATR.

Pure functions operating on pandas Series. No state or side effects.
"""

import pandas as pd


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate Average True Range.

    ATR measures volatility. Used for stop-loss sizing (2 × ATR)
    and position sizing in the Swing Sniper strategy.

    Args:
        high: High price series.
        low: Low price series.
        close: Closing price series.
        period: ATR period (default 14).

    Returns:
        ATR values. First `period` values are NaN.

    Raises:
        ValueError: If period < 1 or series are empty/mismatched.
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if high.empty or low.empty or close.empty:
        raise ValueError("Price series must not be empty")
    if not (len(high) == len(low) == len(close)):
        raise ValueError("All price series must have the same length")

    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder smoothing (alpha = 1/period)
    result = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    # NaN for warm-up
    result.iloc[: period] = float("nan")

    return result
