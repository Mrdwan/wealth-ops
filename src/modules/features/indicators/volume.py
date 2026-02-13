"""Volume indicators: Volume Ratio.

Pure functions operating on pandas Series. No state or side effects.
"""

import pandas as pd


def volume_ratio(
    volume: pd.Series,
    short: int = 20,
    long: int = 50,
) -> pd.Series:
    """Calculate Volume Ratio (short-term vs long-term average).

    Formula: SMA(volume, short) / SMA(volume, long).
    Detects volume spikes that may confirm price moves.

    Args:
        volume: Volume series.
        short: Short-term SMA period (default 20).
        long: Long-term SMA period (default 50).

    Returns:
        Volume ratio. First `long - 1` values are NaN.

    Raises:
        ValueError: If short >= long, any period < 1, or series is empty.
    """
    if short < 1 or long < 1:
        raise ValueError(f"Periods must be >= 1, got short={short}, long={long}")
    if short >= long:
        raise ValueError(f"Short period must be < long, got short={short}, long={long}")
    if volume.empty:
        raise ValueError("Volume series is empty")

    sma_short = volume.rolling(window=short, min_periods=short).mean()
    sma_long = volume.rolling(window=long, min_periods=long).mean()

    result = sma_short / sma_long
    # Handle zero long-term volume (shouldn't happen, but be safe)
    result = result.where(sma_long > 0, float("nan"))

    return result
