"""Candle structure indicators: Upper Wick Ratio, Lower Wick Ratio.

Pure functions operating on pandas Series. No state or side effects.
"""

import pandas as pd


def upper_wick_ratio(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """Calculate Upper Wick Ratio (Shooting Star detection).

    Formula: (High - max(Open, Close)) / (High - Low).
    Edge case: if High == Low (doji), ratio = 0.0.

    Args:
        open_: Opening price series.
        high: High price series.
        low: Low price series.
        close: Closing price series.

    Returns:
        Upper wick ratio (0.0 to 1.0).

    Raises:
        ValueError: If series are empty or mismatched.
    """
    if open_.empty or high.empty or low.empty or close.empty:
        raise ValueError("Price series must not be empty")
    if not (len(open_) == len(high) == len(low) == len(close)):
        raise ValueError("All price series must have the same length")

    body_top = pd.concat([open_, close], axis=1).max(axis=1)
    candle_range = high - low

    result = (high - body_top) / candle_range
    # Handle doji (High == Low → range is 0)
    result = result.where(candle_range > 0, 0.0)
    # Clamp any floating point artifacts
    return result.clip(0.0, 1.0)


def lower_wick_ratio(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """Calculate Lower Wick Ratio (Hammer detection).

    Formula: (min(Open, Close) - Low) / (High - Low).
    Edge case: if High == Low (doji), ratio = 0.0.

    Args:
        open_: Opening price series.
        high: High price series.
        low: Low price series.
        close: Closing price series.

    Returns:
        Lower wick ratio (0.0 to 1.0).

    Raises:
        ValueError: If series are empty or mismatched.
    """
    if open_.empty or high.empty or low.empty or close.empty:
        raise ValueError("Price series must not be empty")
    if not (len(open_) == len(high) == len(low) == len(close)):
        raise ValueError("All price series must have the same length")

    body_bottom = pd.concat([open_, close], axis=1).min(axis=1)
    candle_range = high - low

    result = (body_bottom - low) / candle_range
    # Handle doji (High == Low → range is 0)
    result = result.where(candle_range > 0, 0.0)
    # Clamp any floating point artifacts
    return result.clip(0.0, 1.0)
