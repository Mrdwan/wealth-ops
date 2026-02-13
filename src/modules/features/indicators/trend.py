"""Trend indicators: EMA, ADX, EMA Fan.

Pure functions operating on pandas Series. No state or side effects.
"""

import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        series: Input price series.
        period: EMA period.

    Returns:
        EMA series. First `period - 1` values are NaN.

    Raises:
        ValueError: If period < 1 or series is empty.
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if series.empty:
        raise ValueError("Input series is empty")

    result = series.ewm(span=period, min_periods=period, adjust=False).mean()
    return result


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate Average Directional Index.

    Measures trend strength regardless of direction.
    ADX > 20 indicates a trending market (used in Trend Gate guard).

    Args:
        high: High price series.
        low: Low price series.
        close: Closing price series.
        period: ADX period (default 14).

    Returns:
        ADX values (0-100). Early values are NaN during warm-up.

    Raises:
        ValueError: If period < 1 or series are empty/mismatched.
    """
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    if high.empty or low.empty or close.empty:
        raise ValueError("Price series must not be empty")
    if not (len(high) == len(low) == len(close)):
        raise ValueError("All price series must have the same length")

    # True Range
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # Wilder smoothing (EMA with alpha = 1/period)
    alpha = 1.0 / period
    atr_smooth = tr.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    plus_di_smooth = plus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    minus_di_smooth = minus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    # Directional Indicators
    plus_di = 100.0 * plus_di_smooth / atr_smooth
    minus_di = 100.0 * minus_di_smooth / atr_smooth

    # ADX
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    # Handle division by zero (flat market where both DI are 0)
    dx = dx.fillna(0.0)
    result = dx.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    # NaN for warm-up (need 2 * period bars for ADX to stabilize)
    warm_up = 2 * period - 1
    result.iloc[:warm_up] = float("nan")

    return result


def ema_fan(close: pd.Series) -> pd.Series:
    """Calculate EMA Fan (boolean indicator).

    True when EMA_8 > EMA_20 > EMA_50, indicating a fully aligned uptrend.

    Args:
        close: Closing price series.

    Returns:
        Boolean series (True = aligned uptrend). First 49 values are NaN.

    Raises:
        ValueError: If series is empty.
    """
    if close.empty:
        raise ValueError("Close series is empty")

    ema_8 = close.ewm(span=8, min_periods=8, adjust=False).mean()
    ema_20 = close.ewm(span=20, min_periods=20, adjust=False).mean()
    ema_50 = close.ewm(span=50, min_periods=50, adjust=False).mean()

    aligned = (ema_8 > ema_20) & (ema_20 > ema_50)

    # NaN until EMA_50 is valid
    result = aligned.astype(float)
    result.iloc[:49] = float("nan")

    return result
