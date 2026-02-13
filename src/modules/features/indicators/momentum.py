"""Momentum indicators: RSI, MACD Histogram, OBV.

Pure functions operating on pandas Series. No state or side effects.
"""

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (Wilder's smoothing).

    Args:
        close: Closing price series.
        period: Lookback period (default 14).

    Returns:
        RSI values between 0 and 100. First `period` values are NaN.

    Raises:
        ValueError: If period < 1 or series is empty.
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if close.empty:
        raise ValueError("Close series is empty")

    delta = close.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = (-delta).where(delta < 0, 0.0)

    # Wilder's smoothing (exponential with alpha = 1/period)
    avg_gain = gains.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    result = 100.0 - (100.0 / (1.0 + rs))

    # Where avg_loss is 0, RSI = 100 (all gains)
    result = result.where(avg_loss > 0, 100.0)
    # Where avg_gain is 0, RSI = 0 (all losses)
    result = result.where(avg_gain > 0, 0.0)
    # Ensure warm-up period is NaN
    result.iloc[:period] = float("nan")

    return result


def macd_histogram(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.Series:
    """Calculate MACD Histogram.

    Formula: EMA(fast) - EMA(slow) - Signal_Line(EMA of MACD, signal period).

    Args:
        close: Closing price series.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal: Signal line EMA period (default 9).

    Returns:
        MACD histogram values. Early values are NaN during warm-up.

    Raises:
        ValueError: If fast >= slow or any period < 1.
    """
    if fast < 1 or slow < 1 or signal < 1:
        raise ValueError(f"All periods must be >= 1, got fast={fast}, slow={slow}, signal={signal}")
    if fast >= slow:
        raise ValueError(f"Fast period must be < slow period, got fast={fast}, slow={slow}")

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    # NaN for warm-up period (need at least slow + signal - 1 bars)
    warm_up = slow + signal - 2
    histogram.iloc[:warm_up] = float("nan")

    return histogram


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume.

    Cumulative volume: add on up days, subtract on down days, zero on flat.

    Args:
        close: Closing price series.
        volume: Volume series (must be same length as close).

    Returns:
        OBV series. First value is the first volume value.

    Raises:
        ValueError: If series lengths don't match or are empty.
    """
    if close.empty or volume.empty:
        raise ValueError("Close and volume series must not be empty")
    if len(close) != len(volume):
        raise ValueError(
            f"Series length mismatch: close={len(close)}, volume={len(volume)}"
        )

    direction = close.diff().apply(
        lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
    )
    # First bar has no direction — use its volume as starting point
    direction.iloc[0] = 1

    return (direction * volume).cumsum()
