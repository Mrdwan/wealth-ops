"""Tests for Momentum Composite component score functions.

Unit tests for each of the 6 pure component calculators.
"""

import pandas as pd
import pytest

from src.modules.signals.components import (
    MIN_BARS_MOMENTUM,
    momentum_score,
    rsi_score,
    support_resistance_score,
    trend_score,
    volatility_score,
    volume_score,
)


class TestMomentumScore:
    """Tests for momentum_score()."""

    def test_returns_series(self, long_uptrend_ohlcv: pd.DataFrame) -> None:
        """Should return a pandas Series."""
        result = momentum_score(long_uptrend_ohlcv["close"])
        assert isinstance(result, pd.Series)

    def test_output_length(self, long_uptrend_ohlcv: pd.DataFrame) -> None:
        """Output length should match input."""
        result = momentum_score(long_uptrend_ohlcv["close"])
        assert len(result) == len(long_uptrend_ohlcv)

    def test_warmup_nans(self, long_uptrend_ohlcv: pd.DataFrame) -> None:
        """Early values should be NaN during warmup period."""
        result = momentum_score(long_uptrend_ohlcv["close"])
        # First MIN_BARS_MOMENTUM values are NaN
        assert result.iloc[: MIN_BARS_MOMENTUM].isna().all()

    def test_uptrend_positive(self, long_uptrend_ohlcv: pd.DataFrame) -> None:
        """In an uptrend, stable-region momentum should be positive."""
        result = momentum_score(long_uptrend_ohlcv["close"])
        stable = result.dropna()
        assert len(stable) > 0
        assert stable.iloc[-1] > 0

    def test_empty_series_raises(self) -> None:
        """Should raise ValueError on empty series."""
        with pytest.raises(ValueError, match="empty"):
            momentum_score(pd.Series(dtype=float))


class TestTrendScore:
    """Tests for trend_score()."""

    def test_returns_series(self, long_uptrend_ohlcv: pd.DataFrame) -> None:
        """Should return a pandas Series."""
        result = trend_score(long_uptrend_ohlcv["close"])
        assert isinstance(result, pd.Series)

    def test_warmup_nans(self, long_uptrend_ohlcv: pd.DataFrame) -> None:
        """First 199 values should be NaN (200-day SMA warmup)."""
        result = trend_score(long_uptrend_ohlcv["close"])
        assert result.iloc[:199].isna().all()

    def test_uptrend_positive(self, long_uptrend_ohlcv: pd.DataFrame) -> None:
        """In an uptrend, price above 200 SMA → positive score."""
        result = trend_score(long_uptrend_ohlcv["close"])
        # Last value in a strong uptrend should be positive
        assert result.iloc[-1] > 0

    def test_empty_series_raises(self) -> None:
        """Should raise ValueError on empty series."""
        with pytest.raises(ValueError, match="empty"):
            trend_score(pd.Series(dtype=float))


class TestRsiScore:
    """Tests for rsi_score()."""

    def test_midpoint_gets_max_score(self) -> None:
        """RSI = 50 → maximum score of 50."""
        rsi = pd.Series([50.0, 50.0, 50.0])
        result = rsi_score(rsi)
        assert (result == 50.0).all()

    def test_extreme_gets_zero(self) -> None:
        """RSI = 0 or 100 → score of 0."""
        rsi = pd.Series([0.0, 100.0])
        result = rsi_score(rsi)
        assert (result == 0.0).all()

    def test_symmetric(self) -> None:
        """RSI = 30 and RSI = 70 should produce the same score."""
        rsi = pd.Series([30.0, 70.0])
        result = rsi_score(rsi)
        assert result.iloc[0] == result.iloc[1]

    def test_nan_propagation(self) -> None:
        """NaN RSI values should produce NaN scores."""
        rsi = pd.Series([float("nan"), 50.0, float("nan")])
        result = rsi_score(rsi)
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == 50.0
        assert pd.isna(result.iloc[2])

    def test_empty_series_raises(self) -> None:
        """Should raise ValueError on empty series."""
        with pytest.raises(ValueError, match="empty"):
            rsi_score(pd.Series(dtype=float))


class TestVolumeScore:
    """Tests for volume_score()."""

    def test_above_average_positive(self) -> None:
        """Volume ratio > 1.0 → positive score."""
        vr = pd.Series([1.5, 2.0, 1.1])
        result = volume_score(vr)
        assert (result > 0).all()

    def test_below_average_negative(self) -> None:
        """Volume ratio < 1.0 → negative score."""
        vr = pd.Series([0.5, 0.8, 0.9])
        result = volume_score(vr)
        assert (result < 0).all()

    def test_average_zero(self) -> None:
        """Volume ratio = 1.0 → score of 0."""
        vr = pd.Series([1.0])
        result = volume_score(vr)
        assert result.iloc[0] == 0.0

    def test_empty_series_raises(self) -> None:
        """Should raise ValueError on empty series."""
        with pytest.raises(ValueError, match="empty"):
            volume_score(pd.Series(dtype=float))


class TestVolatilityScore:
    """Tests for volatility_score()."""

    def test_inverted(self) -> None:
        """Higher normalized ATR → lower (more negative) score."""
        atr = pd.Series([2.0, 4.0, 6.0])
        close = pd.Series([100.0, 100.0, 100.0])
        result = volatility_score(atr, close)
        assert result.iloc[0] > result.iloc[1] > result.iloc[2]

    def test_negative_values(self) -> None:
        """All values should be negative (inverted)."""
        atr = pd.Series([1.0, 2.0])
        close = pd.Series([100.0, 100.0])
        result = volatility_score(atr, close)
        assert (result < 0).all()

    def test_zero_close_produces_nan(self) -> None:
        """Zero close price → NaN (guard against division by zero)."""
        atr = pd.Series([1.0])
        close = pd.Series([0.0])
        result = volatility_score(atr, close)
        assert pd.isna(result.iloc[0])

    def test_empty_series_raises(self) -> None:
        """Should raise ValueError on empty series."""
        with pytest.raises(ValueError, match="empty"):
            volatility_score(pd.Series(dtype=float), pd.Series(dtype=float))

    def test_length_mismatch_raises(self) -> None:
        """Should raise ValueError on mismatched lengths."""
        with pytest.raises(ValueError, match="mismatch"):
            volatility_score(pd.Series([1.0, 2.0]), pd.Series([100.0]))


class TestSupportResistanceScore:
    """Tests for support_resistance_score()."""

    def test_at_support_high_score(self) -> None:
        """Price at the 20-day low → score near 1.0."""
        close = pd.Series([100.0] * 20 + [90.0, 90.0, 90.0, 90.0, 90.0])
        high = close + 1.0
        low = close - 0.5
        result = support_resistance_score(close, high, low, period=20)
        # Last value should be high (near support)
        assert result.iloc[-1] > 0.5

    def test_at_resistance_low_score(self) -> None:
        """Price at the 20-day high → score near 0.0."""
        close = pd.Series([100.0] * 20 + [110.0, 110.0, 110.0, 110.0, 110.0])
        high = close + 0.5
        low = close - 1.0
        result = support_resistance_score(close, high, low, period=20)
        # Last value should be low (near resistance)
        assert result.iloc[-1] < 0.5

    def test_warmup_nans(self) -> None:
        """First period-1 values should be NaN."""
        n = 30
        close = pd.Series([100.0] * n)
        high = close + 1.0
        low = close - 1.0
        result = support_resistance_score(close, high, low, period=20)
        assert result.iloc[:19].isna().all()

    def test_zero_range_produces_half(self) -> None:
        """Flat market (high == low) → score of 0.5 (guard value)."""
        n = 25
        price = pd.Series([100.0] * n)
        result = support_resistance_score(price, price, price, period=20)
        stable = result.dropna()
        assert len(stable) > 0
        assert (stable == 0.5).all()

    def test_empty_series_raises(self) -> None:
        """Should raise ValueError on empty series."""
        with pytest.raises(ValueError, match="empty"):
            support_resistance_score(
                pd.Series(dtype=float),
                pd.Series(dtype=float),
                pd.Series(dtype=float),
            )

    def test_length_mismatch_raises(self) -> None:
        """Should raise ValueError on mismatched lengths."""
        with pytest.raises(ValueError, match="same length"):
            support_resistance_score(
                pd.Series([100.0, 101.0]),
                pd.Series([102.0]),
                pd.Series([99.0, 98.0]),
            )

    def test_invalid_period_raises(self) -> None:
        """Should raise ValueError for period < 1."""
        with pytest.raises(ValueError, match="Period"):
            support_resistance_score(
                pd.Series([100.0]),
                pd.Series([101.0]),
                pd.Series([99.0]),
                period=0,
            )
