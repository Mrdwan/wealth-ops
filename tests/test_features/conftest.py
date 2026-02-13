"""Shared fixtures for feature engine tests.

All data is static and deterministic. No network calls, no randomness.
"""

from datetime import date

import pandas as pd
import pytest


def _make_date_index(n: int) -> pd.DatetimeIndex:
    """Create a DatetimeIndex of n business days."""
    start = date(2024, 1, 2)  # A Tuesday
    dates = pd.bdate_range(start=start, periods=n)
    return dates


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """60 days of realistic OHLCV data for testing.

    Simulates a gradual uptrend with typical daily ranges.
    This is deterministic — same data every run.
    """
    n = 60
    dates = _make_date_index(n)

    # Start at 100, gradual uptrend ~0.3%/day with noise
    base_prices = [100.0]
    for i in range(1, n):
        # Alternating pattern: up, up, down, up, flat, up, down...
        move = [0.5, 0.8, -0.3, 1.0, 0.0, 0.6, -0.7, 0.4, 1.2, -0.5]
        base_prices.append(base_prices[-1] + move[i % len(move)])

    close = pd.Series(base_prices, dtype=float)
    open_ = close - 0.2  # Open slightly below close (bullish bias)
    high = close + 0.5  # High above close
    low = open_ - 0.3  # Low below open
    volume = pd.Series([1_000_000 + (i * 10_000) for i in range(n)], dtype=float)

    return pd.DataFrame(
        {
            "open": open_.values,
            "high": high.values,
            "low": low.values,
            "close": close.values,
            "volume": volume.values,
        },
        index=dates,
    )


@pytest.fixture
def doji_candle_df() -> pd.DataFrame:
    """DataFrame where High == Low (doji candles) for wick ratio edge case."""
    n = 5
    dates = _make_date_index(n)
    price = 100.0

    return pd.DataFrame(
        {
            "open": [price] * n,
            "high": [price] * n,
            "low": [price] * n,
            "close": [price] * n,
            "volume": [1_000_000.0] * n,
        },
        index=dates,
    )


@pytest.fixture
def trending_up_df() -> pd.DataFrame:
    """60 days of a strong uptrend for testing trend indicators."""
    n = 60
    dates = _make_date_index(n)

    # Monotonically increasing prices
    close = pd.Series([100.0 + i * 1.0 for i in range(n)], dtype=float)
    open_ = close - 0.3
    high = close + 0.5
    low = open_ - 0.2
    volume = pd.Series([2_000_000.0 + i * 50_000 for i in range(n)], dtype=float)

    return pd.DataFrame(
        {
            "open": open_.values,
            "high": high.values,
            "low": low.values,
            "close": close.values,
            "volume": volume.values,
        },
        index=dates,
    )


@pytest.fixture
def all_gains_close() -> pd.Series:
    """Close series where every day is an up day (for RSI = 100)."""
    return pd.Series([100.0 + i for i in range(20)], dtype=float)


@pytest.fixture
def all_losses_close() -> pd.Series:
    """Close series where every day is a down day (for RSI = 0)."""
    return pd.Series([120.0 - i for i in range(20)], dtype=float)
