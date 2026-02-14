"""Feature Engine — orchestrates technical indicator computation.

Computes all 11 base features (or 13 with volume, 14 with benchmark)
for a given OHLCV DataFrame.
This is the single entry point for feature computation in the signal pipeline.
"""

import pandas as pd

from src.modules.features.indicators.candle import lower_wick_ratio, upper_wick_ratio
from src.modules.features.indicators.momentum import macd_histogram, obv, rsi
from src.modules.features.indicators.price import distance_from_low
from src.modules.features.indicators.trend import adx, ema, ema_fan
from src.modules.features.indicators.volatility import atr
from src.modules.features.indicators.relative_strength import relative_strength
from src.modules.features.indicators.volume import volume_ratio
from src.shared.logger import get_logger

logger = get_logger(__name__)

# Required columns in input DataFrame
REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}

# Minimum rows needed for the longest warm-up period (EMA_50 = 50 bars)
MIN_ROWS = 50


class FeatureEngine:
    """Computes technical features for a given OHLCV DataFrame.

    Orchestrates all indicator functions and assembles the result.
    Profile-aware: `volume_features=False` skips OBV and Volume Ratio.

    Usage:
        engine = FeatureEngine()
        features_df = engine.compute(ohlcv_df, volume_features=True)
    """

    def compute(
        self,
        df: pd.DataFrame,
        volume_features: bool = True,
        benchmark_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Compute all technical features for the input OHLCV data.

        Args:
            df: DataFrame with columns: open, high, low, close, volume.
                Index should be a DatetimeIndex or date-based.
            volume_features: If True, include OBV and Volume Ratio
                (for EQUITY profiles). If False, skip them
                (for COMMODITY_HAVEN/FOREX profiles).
            benchmark_df: Optional benchmark OHLCV DataFrame for Relative
                Strength computation. Must have a 'close' column with
                date-aligned index. If None, RS is skipped.

        Returns:
            New DataFrame with all original columns plus feature columns.
            Feature columns: rsi_14, ema_8, ema_20, ema_50, macd_hist,
            adx_14, atr_14, upper_wick, lower_wick, ema_fan, dist_from_low.
            If volume_features=True: also obv, volume_ratio.
            If benchmark_df provided: also rs_zscore.

        Raises:
            ValueError: If required columns are missing or data is too short.
        """
        self._validate_input(df)

        result = df.copy()

        # Base features (all asset classes — 11 features)
        result["rsi_14"] = rsi(df["close"], period=14)
        result["ema_8"] = ema(df["close"], period=8)
        result["ema_20"] = ema(df["close"], period=20)
        result["ema_50"] = ema(df["close"], period=50)
        result["macd_hist"] = macd_histogram(df["close"])
        result["adx_14"] = adx(df["high"], df["low"], df["close"], period=14)
        result["atr_14"] = atr(df["high"], df["low"], df["close"], period=14)
        result["upper_wick"] = upper_wick_ratio(
            df["open"], df["high"], df["low"], df["close"]
        )
        result["lower_wick"] = lower_wick_ratio(
            df["open"], df["high"], df["low"], df["close"]
        )
        result["ema_fan"] = ema_fan(df["close"])
        result["dist_from_low"] = distance_from_low(df["close"], df["low"], period=20)

        feature_count = 11

        # Class-specific features (EQUITY only)
        if volume_features:
            result["obv"] = obv(df["close"], df["volume"])
            result["volume_ratio"] = volume_ratio(df["volume"])
            feature_count += 2

        # Relative Strength (when benchmark provided)
        if benchmark_df is not None and "close" in benchmark_df.columns:
            # Align benchmark to asset dates
            aligned_benchmark = benchmark_df["close"].reindex(df.index)
            result["rs_zscore"] = relative_strength(df["close"], aligned_benchmark)
            feature_count += 1

        logger.info(f"Computed {feature_count} features for {len(df)} bars")

        return result

    def _validate_input(self, df: pd.DataFrame) -> None:
        """Validate the input DataFrame has required columns and sufficient rows.

        Args:
            df: Input DataFrame to validate.

        Raises:
            ValueError: If columns are missing or data is too short.
        """
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if len(df) < MIN_ROWS:
            raise ValueError(
                f"Need at least {MIN_ROWS} rows, got {len(df)}. "
                f"Longest warm-up is EMA_50 (50 bars)."
            )
