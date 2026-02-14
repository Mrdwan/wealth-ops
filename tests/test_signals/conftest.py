"""Shared fixtures for signal tests.

All data is static and deterministic. No network calls, no randomness.
Provides 300+ bar datasets sufficient for the momentum composite's
273-bar minimum requirement.
"""

from datetime import date

import pandas as pd
import pytest

from src.modules.features.engine import FeatureEngine


def _make_date_index(n: int) -> pd.DatetimeIndex:
    """Create a DatetimeIndex of n business days."""
    start = date(2023, 1, 3)  # A Tuesday
    dates = pd.bdate_range(start=start, periods=n)
    return dates


@pytest.fixture
def long_uptrend_ohlcv() -> pd.DataFrame:
    """300 days of a deterministic gradual uptrend.

    Suitable for testing momentum composite (needs 273+ bars).
    Prices start at 100 and trend upward ~0.4%/day with realistic noise.
    """
    n = 300
    dates = _make_date_index(n)

    base_prices = [100.0]
    for i in range(1, n):
        # Gradual uptrend with repeating noise pattern
        move = [0.5, 0.8, -0.2, 1.0, 0.1, 0.6, -0.4, 0.4, 1.2, -0.3]
        base_prices.append(base_prices[-1] + move[i % len(move)])

    close = pd.Series(base_prices, dtype=float)
    open_ = close - 0.2
    high = close + 0.6
    low = open_ - 0.4
    volume = pd.Series([1_500_000 + (i * 5_000) for i in range(n)], dtype=float)

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
def sideways_ohlcv() -> pd.DataFrame:
    """300 days of range-bound (sideways) data.

    Prices oscillate between 98 and 102, no clear trend.
    Should produce NEUTRAL signals.
    """
    n = 300
    dates = _make_date_index(n)

    # Oscillate around 100
    import math
    base_prices = [100.0 + 2.0 * math.sin(i * 0.15) for i in range(n)]

    close = pd.Series(base_prices, dtype=float)
    open_ = close - 0.1
    high = close + 0.4
    low = open_ - 0.3
    volume = pd.Series([1_000_000.0] * n, dtype=float)

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
def uptrend_with_features(long_uptrend_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Uptrend OHLCV data with all features computed (volume enabled)."""
    engine = FeatureEngine()
    return engine.compute(long_uptrend_ohlcv, volume_features=True)


@pytest.fixture
def uptrend_no_volume_features(long_uptrend_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Uptrend OHLCV data with features computed (volume disabled)."""
    engine = FeatureEngine()
    return engine.compute(long_uptrend_ohlcv, volume_features=False)


@pytest.fixture
def sideways_with_features(sideways_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Sideways OHLCV data with all features computed (volume enabled)."""
    engine = FeatureEngine()
    return engine.compute(sideways_ohlcv, volume_features=True)
