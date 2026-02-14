"""Tests for FeatureEngine orchestrator.

Integration tests verifying the engine correctly assembles all indicators.
"""

import pandas as pd
import pytest

from src.modules.features.engine import FeatureEngine

# Feature columns expected in output
BASE_FEATURES = [
    "rsi_14", "ema_8", "ema_20", "ema_50", "macd_hist",
    "adx_14", "atr_14", "upper_wick", "lower_wick", "ema_fan", "dist_from_low",
]
VOLUME_FEATURES = ["obv", "volume_ratio"]


class TestFeatureEngine:
    """Integration tests for FeatureEngine.compute()."""

    def test_compute_with_volume_features(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Should produce 13 feature columns with volume_features=True."""
        engine = FeatureEngine()
        result = engine.compute(sample_ohlcv, volume_features=True)

        for col in BASE_FEATURES + VOLUME_FEATURES:
            assert col in result.columns, f"Missing column: {col}"

        # Original columns should also be present
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns

    def test_compute_without_volume_features(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Should produce 11 feature columns with volume_features=False."""
        engine = FeatureEngine()
        result = engine.compute(sample_ohlcv, volume_features=False)

        for col in BASE_FEATURES:
            assert col in result.columns, f"Missing column: {col}"

        for col in VOLUME_FEATURES:
            assert col not in result.columns, f"Unexpected column: {col}"

    def test_compute_output_length(self, sample_ohlcv: pd.DataFrame) -> None:
        """Output should have same number of rows as input."""
        engine = FeatureEngine()
        result = engine.compute(sample_ohlcv)
        assert len(result) == len(sample_ohlcv)

    def test_compute_stable_region_no_nans(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """After the warm-up period (~50 bars), no base features should be NaN."""
        engine = FeatureEngine()
        result = engine.compute(sample_ohlcv, volume_features=True)

        # After bar 49 (0-indexed), all features should have values
        stable = result.iloc[49:]
        for col in BASE_FEATURES:
            nan_count = stable[col].isna().sum()
            assert nan_count == 0, (
                f"Column {col} has {nan_count} NaN values in stable region"
            )

    def test_compute_preserves_index(self, sample_ohlcv: pd.DataFrame) -> None:
        """Output should preserve the original DatetimeIndex."""
        engine = FeatureEngine()
        result = engine.compute(sample_ohlcv)
        assert result.index.equals(sample_ohlcv.index)

    def test_compute_does_not_modify_input(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Input DataFrame should not be modified."""
        engine = FeatureEngine()
        original_cols = list(sample_ohlcv.columns)
        original_values = sample_ohlcv.copy()
        engine.compute(sample_ohlcv)

        assert list(sample_ohlcv.columns) == original_cols
        pd.testing.assert_frame_equal(sample_ohlcv, original_values)

    def test_compute_missing_columns(self) -> None:
        """Should raise ValueError when required columns are missing."""
        engine = FeatureEngine()
        df = pd.DataFrame({"close": [100.0] * 60, "volume": [1000.0] * 60})
        with pytest.raises(ValueError, match="Missing required columns"):
            engine.compute(df)

    def test_compute_insufficient_rows(self) -> None:
        """Should raise ValueError when data is too short."""
        engine = FeatureEngine()
        df = pd.DataFrame({
            "open": [100.0] * 30,
            "high": [101.0] * 30,
            "low": [99.0] * 30,
            "close": [100.5] * 30,
            "volume": [1000.0] * 30,
        })
        with pytest.raises(ValueError, match="at least 50 rows"):
            engine.compute(df)

    def test_compute_with_benchmark_adds_rs(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Should produce rs_zscore when benchmark_df is provided."""
        engine = FeatureEngine()
        # Use same data as benchmark (RS ratio = 1.0 everywhere)
        benchmark = sample_ohlcv[["open", "high", "low", "close", "volume"]].copy()
        result = engine.compute(
            sample_ohlcv, volume_features=True, benchmark_df=benchmark
        )

        assert "rs_zscore" in result.columns
        assert len(result) == len(sample_ohlcv)

    def test_compute_without_benchmark_no_rs(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Should NOT produce rs_zscore when benchmark_df is None."""
        engine = FeatureEngine()
        result = engine.compute(sample_ohlcv, volume_features=True)

        assert "rs_zscore" not in result.columns

    def test_compute_14_features_equity_with_benchmark(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """EQUITY with benchmark: 11 base + 2 volume + 1 RS = 14 features."""
        engine = FeatureEngine()
        benchmark = sample_ohlcv[["close"]].copy()
        result = engine.compute(
            sample_ohlcv, volume_features=True, benchmark_df=benchmark
        )

        expected_features = BASE_FEATURES + VOLUME_FEATURES + ["rs_zscore"]
        for col in expected_features:
            assert col in result.columns, f"Missing column: {col}"

    def test_compute_12_features_commodity_with_benchmark(
        self, sample_ohlcv: pd.DataFrame
    ) -> None:
        """COMMODITY with benchmark: 11 base + 0 volume + 1 RS = 12 features."""
        engine = FeatureEngine()
        benchmark = sample_ohlcv[["close"]].copy()
        result = engine.compute(
            sample_ohlcv, volume_features=False, benchmark_df=benchmark
        )

        assert "rs_zscore" in result.columns
        assert "obv" not in result.columns
        assert "volume_ratio" not in result.columns
