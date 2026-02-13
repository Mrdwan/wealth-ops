"""Tests for individual technical indicators.

Each indicator function is tested for:
- Correct output on known data
- Edge cases (empty, doji, all-gains, all-losses)
- Validation errors (bad parameters)
- NaN warm-up period behavior
"""

import pandas as pd
import pytest

from src.modules.features.indicators.candle import lower_wick_ratio, upper_wick_ratio
from src.modules.features.indicators.momentum import macd_histogram, obv, rsi
from src.modules.features.indicators.price import distance_from_low
from src.modules.features.indicators.trend import adx, ema, ema_fan
from src.modules.features.indicators.volatility import atr
from src.modules.features.indicators.volume import volume_ratio

# ========================================================================
# RSI Tests
# ========================================================================


class TestRSI:
    """Tests for Relative Strength Index."""

    def test_rsi_output_range(self, sample_ohlcv: pd.DataFrame) -> None:
        """RSI values should be between 0 and 100."""
        result = rsi(sample_ohlcv["close"])
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_warm_up_nans(self, sample_ohlcv: pd.DataFrame) -> None:
        """First 14 values should be NaN."""
        result = rsi(sample_ohlcv["close"], period=14)
        assert result.iloc[:14].isna().all()
        assert result.iloc[14:].notna().all()

    def test_rsi_all_gains(self, all_gains_close: pd.Series) -> None:
        """RSI should be 100 when all days are up."""
        result = rsi(all_gains_close, period=14)
        valid = result.dropna()
        assert (valid == 100.0).all()

    def test_rsi_all_losses(self, all_losses_close: pd.Series) -> None:
        """RSI should be 0 when all days are down."""
        result = rsi(all_losses_close, period=14)
        valid = result.dropna()
        assert (valid == 0.0).all()

    def test_rsi_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        with pytest.raises(ValueError, match="empty"):
            rsi(pd.Series(dtype=float))

    def test_rsi_bad_period(self, sample_ohlcv: pd.DataFrame) -> None:
        """Should raise ValueError for period < 1."""
        with pytest.raises(ValueError, match="Period"):
            rsi(sample_ohlcv["close"], period=0)

    def test_rsi_custom_period(self, sample_ohlcv: pd.DataFrame) -> None:
        """Custom period should shift the warm-up window."""
        result = rsi(sample_ohlcv["close"], period=7)
        assert result.iloc[:7].isna().all()
        assert result.iloc[7:].notna().all()


# ========================================================================
# MACD Histogram Tests
# ========================================================================


class TestMACDHistogram:
    """Tests for MACD Histogram."""

    def test_macd_output_length(self, sample_ohlcv: pd.DataFrame) -> None:
        """Output should have same length as input."""
        result = macd_histogram(sample_ohlcv["close"])
        assert len(result) == len(sample_ohlcv)

    def test_macd_warm_up_nans(self, sample_ohlcv: pd.DataFrame) -> None:
        """First slow + signal - 2 values should be NaN."""
        result = macd_histogram(sample_ohlcv["close"])
        warm_up = 26 + 9 - 2  # 33
        assert result.iloc[:warm_up].isna().all()
        assert result.iloc[warm_up:].notna().all()

    def test_macd_trending_up(self, trending_up_df: pd.DataFrame) -> None:
        """MACD histogram should be positive in a strong uptrend."""
        result = macd_histogram(trending_up_df["close"])
        valid = result.dropna()
        # Most values in an uptrend should be positive
        assert (valid > 0).sum() > len(valid) * 0.5

    def test_macd_bad_periods(self) -> None:
        """Should raise ValueError for bad period params."""
        close = pd.Series([100.0] * 50, dtype=float)
        with pytest.raises(ValueError, match="Fast period"):
            macd_histogram(close, fast=26, slow=12)
        with pytest.raises(ValueError, match="All periods"):
            macd_histogram(close, fast=0, slow=26, signal=9)

    def test_macd_custom_periods(self, sample_ohlcv: pd.DataFrame) -> None:
        """Custom periods should work and shift warm-up."""
        result = macd_histogram(sample_ohlcv["close"], fast=5, slow=10, signal=3)
        warm_up = 10 + 3 - 2  # 11
        assert result.iloc[:warm_up].isna().all()
        assert result.iloc[warm_up:].notna().all()


# ========================================================================
# OBV Tests
# ========================================================================


class TestOBV:
    """Tests for On-Balance Volume."""

    def test_obv_output_length(self, sample_ohlcv: pd.DataFrame) -> None:
        """Output should have same length as input."""
        result = obv(sample_ohlcv["close"], sample_ohlcv["volume"])
        assert len(result) == len(sample_ohlcv)

    def test_obv_no_nans(self, sample_ohlcv: pd.DataFrame) -> None:
        """OBV should have no NaN values."""
        result = obv(sample_ohlcv["close"], sample_ohlcv["volume"])
        assert result.notna().all()

    def test_obv_up_day_adds_volume(self) -> None:
        """On an up day, volume should be added."""
        close = pd.Series([100.0, 105.0], dtype=float)
        vol = pd.Series([1000.0, 2000.0], dtype=float)
        result = obv(close, vol)
        # First bar: +1000, Second bar (up): +2000 = 3000
        assert result.iloc[1] == 3000.0

    def test_obv_down_day_subtracts_volume(self) -> None:
        """On a down day, volume should be subtracted."""
        close = pd.Series([100.0, 105.0, 95.0], dtype=float)
        vol = pd.Series([1000.0, 2000.0, 1500.0], dtype=float)
        result = obv(close, vol)
        # First: +1000, Second (up): +2000 = 3000, Third (down): -1500 = 1500
        assert result.iloc[2] == 1500.0

    def test_obv_flat_day_zero(self) -> None:
        """On a flat day, volume contribution should be zero."""
        close = pd.Series([100.0, 100.0], dtype=float)
        vol = pd.Series([1000.0, 2000.0], dtype=float)
        result = obv(close, vol)
        # First: +1000, Second (flat): 0 = 1000
        assert result.iloc[1] == 1000.0

    def test_obv_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        with pytest.raises(ValueError, match="empty"):
            obv(pd.Series(dtype=float), pd.Series(dtype=float))

    def test_obv_length_mismatch(self) -> None:
        """Should raise ValueError for mismatched lengths."""
        with pytest.raises(ValueError, match="mismatch"):
            obv(pd.Series([1.0, 2.0]), pd.Series([1.0]))


# ========================================================================
# EMA Tests
# ========================================================================


class TestEMA:
    """Tests for Exponential Moving Average."""

    def test_ema_output_length(self, sample_ohlcv: pd.DataFrame) -> None:
        """Output should have same length as input."""
        result = ema(sample_ohlcv["close"], period=8)
        assert len(result) == len(sample_ohlcv)

    def test_ema_warm_up_nans(self, sample_ohlcv: pd.DataFrame) -> None:
        """First period - 1 values should be NaN."""
        result = ema(sample_ohlcv["close"], period=20)
        assert result.iloc[:19].isna().all()
        assert result.iloc[19:].notna().all()

    def test_ema_smooths_data(self, sample_ohlcv: pd.DataFrame) -> None:
        """EMA should be smoother (lower std) than raw close."""
        result = ema(sample_ohlcv["close"], period=20)
        valid = result.dropna()
        raw = sample_ohlcv["close"].iloc[-len(valid):]
        # EMA standard deviation should be less than raw
        assert valid.std() < raw.std()

    def test_ema_shorter_period_more_responsive(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Shorter EMA should track price more closely."""
        ema_8 = ema(sample_ohlcv["close"], period=8)
        ema_50 = ema(sample_ohlcv["close"], period=50)
        valid_idx = ema_50.dropna().index
        # Mean absolute deviation from close should be smaller for EMA_8
        close = sample_ohlcv["close"].loc[valid_idx]
        dev_8 = (ema_8.loc[valid_idx] - close).abs().mean()
        dev_50 = (ema_50.loc[valid_idx] - close).abs().mean()
        assert dev_8 < dev_50

    def test_ema_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        with pytest.raises(ValueError, match="empty"):
            ema(pd.Series(dtype=float), period=8)

    def test_ema_bad_period(self, sample_ohlcv: pd.DataFrame) -> None:
        """Should raise ValueError for period < 1."""
        with pytest.raises(ValueError, match="Period"):
            ema(sample_ohlcv["close"], period=0)


# ========================================================================
# ADX Tests
# ========================================================================


class TestADX:
    """Tests for Average Directional Index."""

    def test_adx_output_range(self, sample_ohlcv: pd.DataFrame) -> None:
        """ADX should be between 0 and 100."""
        result = adx(
            sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"]
        )
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_adx_warm_up_nans(self, sample_ohlcv: pd.DataFrame) -> None:
        """First 2*period - 1 values should be NaN."""
        result = adx(
            sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"],
            period=14,
        )
        warm_up = 2 * 14 - 1  # 27
        assert result.iloc[:warm_up].isna().all()
        assert result.iloc[warm_up:].notna().all()

    def test_adx_trending_higher(self, trending_up_df: pd.DataFrame) -> None:
        """ADX should be elevated in a strong trend."""
        result = adx(
            trending_up_df["high"], trending_up_df["low"], trending_up_df["close"]
        )
        valid = result.dropna()
        # In a monotonic trend, ADX should be > 20 (Trend Gate threshold)
        assert valid.iloc[-1] > 20

    def test_adx_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        with pytest.raises(ValueError, match="empty"):
            adx(pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float))

    def test_adx_bad_period(self, sample_ohlcv: pd.DataFrame) -> None:
        """Should raise ValueError for period < 1."""
        with pytest.raises(ValueError, match="Period"):
            adx(
                sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"],
                period=0,
            )

    def test_adx_length_mismatch(self) -> None:
        """Should raise ValueError for mismatched lengths."""
        with pytest.raises(ValueError, match="same length"):
            adx(pd.Series([1.0, 2.0]), pd.Series([1.0]), pd.Series([1.0, 2.0]))


# ========================================================================
# ATR Tests
# ========================================================================


class TestATR:
    """Tests for Average True Range."""

    def test_atr_positive(self, sample_ohlcv: pd.DataFrame) -> None:
        """ATR should always be positive (volatility is never negative)."""
        result = atr(
            sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"]
        )
        valid = result.dropna()
        assert (valid > 0).all()

    def test_atr_warm_up_nans(self, sample_ohlcv: pd.DataFrame) -> None:
        """First period values should be NaN."""
        result = atr(
            sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"],
            period=14,
        )
        assert result.iloc[:14].isna().all()
        assert result.iloc[14:].notna().all()

    def test_atr_known_value(self) -> None:
        """ATR for a simple case with known True Range."""
        # 3 bars, constant range of 2.0
        high = pd.Series([102.0, 103.0, 104.0], dtype=float)
        low = pd.Series([100.0, 101.0, 102.0], dtype=float)
        close = pd.Series([101.0, 102.0, 103.0], dtype=float)
        result = atr(high, low, close, period=2)
        # After warm-up, ATR should reflect ~2.0 range
        valid = result.dropna()
        assert len(valid) > 0
        assert abs(valid.iloc[-1] - 2.0) < 0.5

    def test_atr_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        with pytest.raises(ValueError, match="empty"):
            atr(pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float))

    def test_atr_bad_period(self, sample_ohlcv: pd.DataFrame) -> None:
        """Should raise ValueError for period < 1."""
        with pytest.raises(ValueError, match="Period"):
            atr(
                sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"],
                period=0,
            )

    def test_atr_length_mismatch(self) -> None:
        """Should raise ValueError for mismatched lengths."""
        with pytest.raises(ValueError, match="same length"):
            atr(pd.Series([1.0, 2.0]), pd.Series([1.0]), pd.Series([1.0, 2.0]))


# ========================================================================
# EMA Fan Tests
# ========================================================================


class TestEMAFan:
    """Tests for EMA Fan (boolean indicator)."""

    def test_ema_fan_output_type(self, sample_ohlcv: pd.DataFrame) -> None:
        """Output should be float (0.0 or 1.0 or NaN)."""
        result = ema_fan(sample_ohlcv["close"])
        valid = result.dropna()
        assert set(valid.unique()).issubset({0.0, 1.0})

    def test_ema_fan_warm_up_nans(self, sample_ohlcv: pd.DataFrame) -> None:
        """First 49 values should be NaN (needs EMA_50)."""
        result = ema_fan(sample_ohlcv["close"])
        assert result.iloc[:49].isna().all()
        assert result.iloc[49:].notna().all()

    def test_ema_fan_uptrend(self, trending_up_df: pd.DataFrame) -> None:
        """In a strong uptrend, EMA fan should be True (1.0)."""
        result = ema_fan(trending_up_df["close"])
        valid = result.dropna()
        # In a monotonic uptrend, the fan should align eventually
        assert valid.iloc[-1] == 1.0

    def test_ema_fan_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        with pytest.raises(ValueError, match="empty"):
            ema_fan(pd.Series(dtype=float))


# ========================================================================
# Upper Wick Ratio Tests
# ========================================================================


class TestUpperWickRatio:
    """Tests for Upper Wick Ratio."""

    def test_upper_wick_ratio_range(self, sample_ohlcv: pd.DataFrame) -> None:
        """Upper wick ratio should be between 0 and 1."""
        result = upper_wick_ratio(
            sample_ohlcv["open"], sample_ohlcv["high"],
            sample_ohlcv["low"], sample_ohlcv["close"],
        )
        assert (result >= 0).all()
        assert (result <= 1).all()

    def test_upper_wick_ratio_doji(self, doji_candle_df: pd.DataFrame) -> None:
        """Doji (H==L) should produce 0.0 upper wick ratio."""
        result = upper_wick_ratio(
            doji_candle_df["open"], doji_candle_df["high"],
            doji_candle_df["low"], doji_candle_df["close"],
        )
        assert (result == 0.0).all()

    def test_upper_wick_shooting_star(self) -> None:
        """Shooting star candle should have high upper wick ratio."""
        # Open=100, Close=101, High=110, Low=99 → upper wick = (110-101)/11 ≈ 0.82
        o = pd.Series([100.0])
        h = pd.Series([110.0])
        low_s = pd.Series([99.0])
        c = pd.Series([101.0])
        result = upper_wick_ratio(o, h, low_s, c)
        assert result.iloc[0] > 0.7

    def test_upper_wick_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        empty = pd.Series(dtype=float)
        with pytest.raises(ValueError, match="empty"):
            upper_wick_ratio(empty, empty, empty, empty)

    def test_upper_wick_length_mismatch(self) -> None:
        """Should raise ValueError for mismatched lengths."""
        with pytest.raises(ValueError, match="same length"):
            upper_wick_ratio(
                pd.Series([1.0, 2.0]), pd.Series([1.0]),
                pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]),
            )


# ========================================================================
# Lower Wick Ratio Tests
# ========================================================================


class TestLowerWickRatio:
    """Tests for Lower Wick Ratio."""

    def test_lower_wick_ratio_range(self, sample_ohlcv: pd.DataFrame) -> None:
        """Lower wick ratio should be between 0 and 1."""
        result = lower_wick_ratio(
            sample_ohlcv["open"], sample_ohlcv["high"],
            sample_ohlcv["low"], sample_ohlcv["close"],
        )
        assert (result >= 0).all()
        assert (result <= 1).all()

    def test_lower_wick_ratio_doji(self, doji_candle_df: pd.DataFrame) -> None:
        """Doji (H==L) should produce 0.0 lower wick ratio."""
        result = lower_wick_ratio(
            doji_candle_df["open"], doji_candle_df["high"],
            doji_candle_df["low"], doji_candle_df["close"],
        )
        assert (result == 0.0).all()

    def test_lower_wick_hammer(self) -> None:
        """Hammer candle should have high lower wick ratio."""
        # Open=109, Close=110, High=111, Low=100 → lower wick = (109-100)/11 ≈ 0.82
        o = pd.Series([109.0])
        h = pd.Series([111.0])
        low_s = pd.Series([100.0])
        c = pd.Series([110.0])
        result = lower_wick_ratio(o, h, low_s, c)
        assert result.iloc[0] > 0.7

    def test_lower_wick_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        empty = pd.Series(dtype=float)
        with pytest.raises(ValueError, match="empty"):
            lower_wick_ratio(empty, empty, empty, empty)

    def test_lower_wick_length_mismatch(self) -> None:
        """Should raise ValueError for mismatched lengths."""
        with pytest.raises(ValueError, match="same length"):
            lower_wick_ratio(
                pd.Series([1.0, 2.0]), pd.Series([1.0]),
                pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]),
            )


# ========================================================================
# Volume Ratio Tests
# ========================================================================


class TestVolumeRatio:
    """Tests for Volume Ratio."""

    def test_volume_ratio_output_length(self, sample_ohlcv: pd.DataFrame) -> None:
        """Output should have same length as input."""
        result = volume_ratio(sample_ohlcv["volume"])
        assert len(result) == len(sample_ohlcv)

    def test_volume_ratio_warm_up_nans(self, sample_ohlcv: pd.DataFrame) -> None:
        """First long-1 values should be NaN."""
        result = volume_ratio(sample_ohlcv["volume"], short=20, long=50)
        assert result.iloc[:49].isna().all()
        assert result.iloc[49:].notna().all()

    def test_volume_ratio_constant_volume(self) -> None:
        """Constant volume should produce ratio of 1.0."""
        vol = pd.Series([1_000_000.0] * 60, dtype=float)
        result = volume_ratio(vol, short=20, long=50)
        valid = result.dropna()
        assert all(abs(v - 1.0) < 0.001 for v in valid)

    def test_volume_ratio_bad_periods(self) -> None:
        """Should raise ValueError for bad period params."""
        vol = pd.Series([1_000_000.0] * 60, dtype=float)
        with pytest.raises(ValueError, match="Short period"):
            volume_ratio(vol, short=50, long=20)
        with pytest.raises(ValueError, match="Periods"):
            volume_ratio(vol, short=0, long=50)

    def test_volume_ratio_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        with pytest.raises(ValueError, match="empty"):
            volume_ratio(pd.Series(dtype=float))


# ========================================================================
# Distance from Low Tests
# ========================================================================


class TestDistanceFromLow:
    """Tests for Distance from 20-day Low."""

    def test_distance_from_low_non_negative(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Distance should be >= 0 (close is always >= rolling low)."""
        result = distance_from_low(sample_ohlcv["close"], sample_ohlcv["low"])
        valid = result.dropna()
        assert (valid >= 0).all()

    def test_distance_from_low_warm_up(self, sample_ohlcv: pd.DataFrame) -> None:
        """First period-1 values should be NaN."""
        result = distance_from_low(sample_ohlcv["close"], sample_ohlcv["low"], period=20)
        assert result.iloc[:19].isna().all()
        assert result.iloc[19:].notna().all()

    def test_distance_from_low_at_low(self) -> None:
        """When close equals the 20-day low, distance should be 0."""
        # All lows at 100, close also at 100
        close = pd.Series([100.0] * 25, dtype=float)
        low = pd.Series([100.0] * 25, dtype=float)
        result = distance_from_low(close, low, period=20)
        valid = result.dropna()
        assert (valid == 0.0).all()

    def test_distance_from_low_empty_series(self) -> None:
        """Should raise ValueError for empty series."""
        with pytest.raises(ValueError, match="empty"):
            distance_from_low(pd.Series(dtype=float), pd.Series(dtype=float))

    def test_distance_from_low_bad_period(self, sample_ohlcv: pd.DataFrame) -> None:
        """Should raise ValueError for period < 1."""
        with pytest.raises(ValueError, match="Period"):
            distance_from_low(sample_ohlcv["close"], sample_ohlcv["low"], period=0)

    def test_distance_from_low_length_mismatch(self) -> None:
        """Should raise ValueError for mismatched lengths."""
        with pytest.raises(ValueError, match="mismatch"):
            distance_from_low(pd.Series([1.0, 2.0]), pd.Series([1.0]))
