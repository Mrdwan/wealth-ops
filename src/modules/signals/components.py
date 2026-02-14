"""Momentum Composite — individual component score calculators.

Six pure functions, one per composite component. Each takes price/feature
data and returns a raw score Series (not yet z-scored).

Component weights (with volume):
    Momentum: 40%, Trend: 20%, RSI: 15%, Volume: 10%, Volatility: 10%, S/R: 5%

References:
    - Jegadeesh & Titman (1993) — Momentum
    - Moskowitz (2012) — Time-series momentum
    - Osler (2003, J. Finance) — Support/Resistance
"""

import pandas as pd

# --- Minimum data requirements ---

# Momentum: 12-month return with 1-month skip = 252 + 21 = 273 bars
MOMENTUM_LOOKBACK = 252
MOMENTUM_SKIP = 21
MIN_BARS_MOMENTUM = MOMENTUM_LOOKBACK + MOMENTUM_SKIP

# Trend: 200-day SMA
TREND_SMA_PERIOD = 200

# Support/Resistance: 20-day Donchian
SR_PERIOD = 20


def momentum_score(close: pd.Series) -> pd.Series:
    """Calculate momentum component (Jegadeesh & Titman, 1993).

    Formula: 12-month return, skipping the most recent 21 trading days
    to avoid short-term reversal. Uses 6-month momentum averaged with
    12-month for robustness.

    Args:
        close: Closing price series (must have >= 273 bars).

    Returns:
        Raw momentum score. Early values are NaN during warmup.

    Raises:
        ValueError: If series is empty.
    """
    if close.empty:
        raise ValueError("Close series is empty")

    # 12-month return, skip most recent 21 days
    ret_12m = close.shift(MOMENTUM_SKIP).pct_change(MOMENTUM_LOOKBACK)

    # 6-month return, skip most recent 21 days (half-period)
    ret_6m = close.shift(MOMENTUM_SKIP).pct_change(MOMENTUM_LOOKBACK // 2)

    # Average of 6m and 12m for robustness
    result = (ret_12m + ret_6m) / 2.0

    return result


def trend_score(close: pd.Series) -> pd.Series:
    """Calculate trend confirmation component.

    Formula: close / SMA(200) ratio. Values > 1.0 indicate price above
    the 200-day moving average (bullish). Values < 1.0 are bearish.

    Args:
        close: Closing price series.

    Returns:
        Trend ratio. First 199 values are NaN.

    Raises:
        ValueError: If series is empty.
    """
    if close.empty:
        raise ValueError("Close series is empty")

    sma_200 = close.rolling(window=TREND_SMA_PERIOD, min_periods=TREND_SMA_PERIOD).mean()

    # Ratio centered around 1.0; subtract 1.0 so >0 = bullish
    result = (close / sma_200) - 1.0

    # Guard against zero SMA (shouldn't happen with real prices)
    result = result.where(sma_200 > 0, float("nan"))

    return result


def rsi_score(rsi_values: pd.Series) -> pd.Series:
    """Calculate RSI filter component.

    Rewards RSI in the "sweet spot" (40-60 range, not overbought/oversold).
    Higher score when RSI is further from extremes (0 and 100).

    Formula: 50 - abs(RSI - 50)
    Range: 0 (at extremes) to 50 (at midpoint).

    Args:
        rsi_values: RSI(14) values from FeatureEngine.

    Returns:
        RSI score (0 to 50). NaN where RSI is NaN.

    Raises:
        ValueError: If series is empty.
    """
    if rsi_values.empty:
        raise ValueError("RSI series is empty")

    return 50.0 - (rsi_values - 50.0).abs()


def volume_score(volume_ratio_values: pd.Series) -> pd.Series:
    """Calculate volume confirmation component.

    Pass-through of the 20d/50d volume ratio from FeatureEngine.
    Values > 1.0 indicate above-average recent volume (institutional flow).

    Args:
        volume_ratio_values: Volume ratio from FeatureEngine.

    Returns:
        Volume score. NaN where input is NaN.

    Raises:
        ValueError: If series is empty.
    """
    if volume_ratio_values.empty:
        raise ValueError("Volume ratio series is empty")

    # Center around 0: subtract 1.0 so positive = above-average volume
    return volume_ratio_values - 1.0


def volatility_score(atr_values: pd.Series, close: pd.Series) -> pd.Series:
    """Calculate ATR volatility component.

    Moderate volatility is preferred for swing trading. Too high = risky,
    too low = no movement. We compute normalized ATR and invert it so
    lower volatility = higher score (conservative preference).

    Formula: -(atr_14 / close) — inverted so lower vol = higher score.

    Args:
        atr_values: ATR(14) values from FeatureEngine.
        close: Closing price series.

    Returns:
        Volatility score (inverted normalized ATR). NaN where inputs are NaN.

    Raises:
        ValueError: If series are empty or mismatched length.
    """
    if atr_values.empty or close.empty:
        raise ValueError("ATR and close series must not be empty")
    if len(atr_values) != len(close):
        raise ValueError(
            f"Series length mismatch: atr={len(atr_values)}, close={len(close)}"
        )

    normalized_atr = atr_values / close

    # Guard against zero close
    normalized_atr = normalized_atr.where(close > 0, float("nan"))

    # Invert: lower volatility = higher score
    return -normalized_atr


def support_resistance_score(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    period: int = SR_PERIOD,
) -> pd.Series:
    """Calculate support/resistance component (Donchian proximity).

    Measures how close the current price is to the recent low (support).
    Buying near support = higher score.

    Formula: 1 - (close - low_Nd) / (high_Nd - low_Nd)
    Range: 0 (at high) to 1 (at low/support).

    Args:
        close: Closing price series.
        high: High price series.
        low: Low price series.
        period: Donchian channel lookback (default 20).

    Returns:
        S/R score (0 to 1). First period-1 values are NaN.

    Raises:
        ValueError: If series are empty or mismatched length.
    """
    if close.empty or high.empty or low.empty:
        raise ValueError("Price series must not be empty")
    if not (len(close) == len(high) == len(low)):
        raise ValueError("All price series must have the same length")
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")

    rolling_high = high.rolling(window=period, min_periods=period).max()
    rolling_low = low.rolling(window=period, min_periods=period).min()

    channel_range = rolling_high - rolling_low

    # Position within channel: 0 = at low, 1 = at high
    channel_position = (close - rolling_low) / channel_range

    # Guard against zero range (flat market), but preserve NaN during warmup.
    # NaN > 0 is False, so a bare .where(x > 0, fallback) would kill warmup NaNs.
    is_warmup = channel_range.isna()
    channel_position = channel_position.where(is_warmup | (channel_range > 0), 0.5)

    # Invert: closer to support (low) = higher score
    return 1.0 - channel_position
