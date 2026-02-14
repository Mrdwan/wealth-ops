"""Momentum Composite Score — orchestrator.

Computes the 6-component z-score-weighted Momentum Composite Score,
the academic-backed baseline signal for the Wealth-Ops system.

Architecture ref: ARCHITECTURE.md Section 7.
Roadmap ref: Step 2A.3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from src.modules.signals.components import (
    MIN_BARS_MOMENTUM,
    TREND_SMA_PERIOD,
    momentum_score,
    rsi_score,
    support_resistance_score,
    trend_score,
    volatility_score,
    volume_score,
)
from src.shared.logger import get_logger

logger = get_logger(__name__)

# Minimum bars required for the composite (driven by momentum component)
MIN_BARS = max(MIN_BARS_MOMENTUM, TREND_SMA_PERIOD)

# Z-score normalization window (matches momentum lookback for consistency)
Z_SCORE_WINDOW = 252

# Signal thresholds (in standard deviations)
STRONG_BUY_THRESHOLD = 2.0
BUY_THRESHOLD = 1.5
SELL_THRESHOLD = -1.5
STRONG_SELL_THRESHOLD = -2.0

# Component weights (with volume features)
WEIGHTS_WITH_VOLUME: dict[str, float] = {
    "momentum": 0.40,
    "trend": 0.20,
    "rsi": 0.15,
    "volume": 0.10,
    "volatility": 0.10,
    "sr": 0.05,
}

# Component weights (without volume features) — redistributed proportionally
_non_volume_total = sum(
    v for k, v in WEIGHTS_WITH_VOLUME.items() if k != "volume"
)
WEIGHTS_WITHOUT_VOLUME: dict[str, float] = {
    k: v / _non_volume_total
    for k, v in WEIGHTS_WITH_VOLUME.items()
    if k != "volume"
}


class SignalClassification(StrEnum):
    """Signal classification from composite score thresholds."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass(frozen=True)
class CompositeResult:
    """Result of the Momentum Composite Score computation.

    Attributes:
        composite_score: Final weighted z-score for each bar.
        signal: Signal classification (STRONG_BUY, BUY, NEUTRAL, etc.).
        components: Dict of individual z-scored component values.
        weights_used: Dict of weights applied to each component.
    """

    composite_score: pd.Series
    signal: pd.Series
    components: dict[str, pd.Series]
    weights_used: dict[str, float]


def _zscore(series: pd.Series, window: int = Z_SCORE_WINDOW) -> pd.Series:
    """Compute rolling z-score normalization.

    Args:
        series: Input values.
        window: Rolling window size.

    Returns:
        Z-scored series. NaN where std is 0 or during warmup.
    """
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std()

    z = (series - rolling_mean) / rolling_std
    # Where std is 0 (constant values), z-score is 0.
    # Preserve NaN during warmup: NaN > 0 is False, so bare .where() kills NaNs.
    is_warmup = rolling_std.isna()
    z = z.where(is_warmup | (rolling_std > 0), 0.0)
    return z


def _classify_signal(score: float) -> str:
    """Classify a single composite score into a signal.

    Args:
        score: Composite z-score value.

    Returns:
        Signal classification string.
    """
    if pd.isna(score):
        return SignalClassification.NEUTRAL.value
    if score > STRONG_BUY_THRESHOLD:
        return SignalClassification.STRONG_BUY.value
    if score > BUY_THRESHOLD:
        return SignalClassification.BUY.value
    if score < STRONG_SELL_THRESHOLD:
        return SignalClassification.STRONG_SELL.value
    if score < SELL_THRESHOLD:
        return SignalClassification.SELL.value
    return SignalClassification.NEUTRAL.value


class MomentumComposite:
    """Computes the 6-component Momentum Composite Score.

    Consumes a DataFrame that has already been through FeatureEngine.compute().
    Produces a CompositeResult with composite scores, signal classifications,
    and individual component z-scores.

    Usage:
        engine = FeatureEngine()
        features_df = engine.compute(ohlcv_df, volume_features=True)
        composite = MomentumComposite()
        result = composite.score(features_df, volume_features=True)
    """

    def score(
        self,
        features_df: pd.DataFrame,
        volume_features: bool = True,
    ) -> CompositeResult:
        """Compute the Momentum Composite Score.

        Args:
            features_df: DataFrame from FeatureEngine.compute() with
                OHLCV + feature columns (rsi_14, atr_14, volume_ratio, etc.).
            volume_features: If True, include volume component (EQUITY).
                If False, skip it and redistribute weights (COMMODITY/FOREX).

        Returns:
            CompositeResult with composite_score, signal, components, and
            weights_used.

        Raises:
            ValueError: If required columns are missing or data is too short.
        """
        self._validate_input(features_df, volume_features)

        # Select weights
        weights = (
            WEIGHTS_WITH_VOLUME.copy()
            if volume_features
            else WEIGHTS_WITHOUT_VOLUME.copy()
        )

        # 1. Compute raw component scores
        raw: dict[str, pd.Series] = {}
        raw["momentum"] = momentum_score(features_df["close"])
        raw["trend"] = trend_score(features_df["close"])
        raw["rsi"] = rsi_score(features_df["rsi_14"])
        raw["volatility"] = volatility_score(features_df["atr_14"], features_df["close"])
        raw["sr"] = support_resistance_score(
            features_df["close"], features_df["high"], features_df["low"]
        )

        if volume_features:
            raw["volume"] = volume_score(features_df["volume_ratio"])

        # 2. Z-score normalize each component
        z_scored: dict[str, pd.Series] = {}
        for name, series in raw.items():
            z_scored[name] = _zscore(series)

        # 3. Compute weighted sum
        composite = pd.Series(0.0, index=features_df.index)
        for name, weight in weights.items():
            composite = composite + weight * z_scored[name].fillna(0.0)

        # 4. Classify signals
        signal = composite.apply(_classify_signal)

        component_count = len(weights)
        logger.info(
            f"Computed Momentum Composite: {component_count} components, "
            f"{len(features_df)} bars, volume={'on' if volume_features else 'off'}"
        )

        return CompositeResult(
            composite_score=composite,
            signal=signal,
            components=z_scored,
            weights_used=weights,
        )

    def _validate_input(
        self,
        df: pd.DataFrame,
        volume_features: bool,
    ) -> None:
        """Validate input DataFrame has required columns and length.

        Args:
            df: Input DataFrame.
            volume_features: Whether volume features are expected.

        Raises:
            ValueError: If validation fails.
        """
        required_cols = {"close", "high", "low", "rsi_14", "atr_14"}
        if volume_features:
            required_cols.add("volume_ratio")

        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if len(df) < MIN_BARS:
            raise ValueError(
                f"Need at least {MIN_BARS} rows for Momentum Composite, "
                f"got {len(df)}. Requires ~13 months of daily data for "
                f"the 12-month momentum lookback with 1-month skip."
            )
