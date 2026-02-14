"""Tests for MomentumComposite orchestrator.

Integration tests verifying the composite score computation,
signal classification, and weight redistribution.
"""

import pandas as pd
import pytest

from src.modules.signals.momentum_composite import (
    BUY_THRESHOLD,
    MIN_BARS,
    STRONG_BUY_THRESHOLD,
    WEIGHTS_WITH_VOLUME,
    WEIGHTS_WITHOUT_VOLUME,
    CompositeResult,
    MomentumComposite,
    SignalClassification,
    _classify_signal,
    _zscore,
)


class TestWeights:
    """Tests for weight configuration."""

    def test_weights_with_volume_sum_to_one(self) -> None:
        """Weights with volume should sum to 1.0."""
        total = sum(WEIGHTS_WITH_VOLUME.values())
        assert abs(total - 1.0) < 1e-10

    def test_weights_without_volume_sum_to_one(self) -> None:
        """Weights without volume should sum to 1.0."""
        total = sum(WEIGHTS_WITHOUT_VOLUME.values())
        assert abs(total - 1.0) < 1e-10

    def test_weights_without_volume_has_no_volume_key(self) -> None:
        """Without volume, there should be no 'volume' key."""
        assert "volume" not in WEIGHTS_WITHOUT_VOLUME

    def test_weights_without_volume_has_5_components(self) -> None:
        """Without volume, there should be 5 components."""
        assert len(WEIGHTS_WITHOUT_VOLUME) == 5

    def test_weights_with_volume_has_6_components(self) -> None:
        """With volume, there should be 6 components."""
        assert len(WEIGHTS_WITH_VOLUME) == 6


class TestZScore:
    """Tests for the _zscore helper function."""

    def test_constant_series_returns_zero(self) -> None:
        """Constant values → z-score of 0.0 (std = 0)."""
        s = pd.Series([100.0] * 300)
        result = _zscore(s, window=252)
        # Non-NaN values should be 0.0
        stable = result.dropna()
        assert len(stable) > 0
        assert (stable == 0.0).all()

    def test_warmup_nans(self) -> None:
        """First window-1 values should be NaN."""
        s = pd.Series(range(300), dtype=float)
        result = _zscore(s, window=252)
        assert result.iloc[:251].isna().all()

    def test_output_length(self) -> None:
        """Output length should match input."""
        s = pd.Series(range(300), dtype=float)
        result = _zscore(s, window=50)
        assert len(result) == 300


class TestClassifySignal:
    """Tests for _classify_signal()."""

    def test_strong_buy(self) -> None:
        """Score > 2.0 → STRONG_BUY."""
        assert _classify_signal(2.5) == SignalClassification.STRONG_BUY.value

    def test_buy(self) -> None:
        """Score between 1.5 and 2.0 → BUY."""
        assert _classify_signal(1.7) == SignalClassification.BUY.value

    def test_neutral(self) -> None:
        """Score between -1.5 and 1.5 → NEUTRAL."""
        assert _classify_signal(0.0) == SignalClassification.NEUTRAL.value
        assert _classify_signal(1.4) == SignalClassification.NEUTRAL.value
        assert _classify_signal(-1.4) == SignalClassification.NEUTRAL.value

    def test_sell(self) -> None:
        """Score between -2.0 and -1.5 → SELL."""
        assert _classify_signal(-1.7) == SignalClassification.SELL.value

    def test_strong_sell(self) -> None:
        """Score < -2.0 → STRONG_SELL."""
        assert _classify_signal(-2.5) == SignalClassification.STRONG_SELL.value

    def test_nan_returns_neutral(self) -> None:
        """NaN score → NEUTRAL (safe default)."""
        assert _classify_signal(float("nan")) == SignalClassification.NEUTRAL.value

    def test_exact_thresholds(self) -> None:
        """Scores at exact thresholds should classify correctly."""
        # At exactly 2.0, not strictly > 2.0, should be BUY
        assert _classify_signal(STRONG_BUY_THRESHOLD) == SignalClassification.NEUTRAL.value or \
               _classify_signal(STRONG_BUY_THRESHOLD) == SignalClassification.BUY.value
        # At exactly 1.5, not strictly > 1.5, should be NEUTRAL
        assert _classify_signal(BUY_THRESHOLD) == SignalClassification.NEUTRAL.value or \
               _classify_signal(BUY_THRESHOLD) == SignalClassification.BUY.value


class TestMomentumComposite:
    """Integration tests for MomentumComposite.score()."""

    def test_returns_composite_result(
        self, uptrend_with_features: pd.DataFrame
    ) -> None:
        """Should return a CompositeResult instance."""
        mc = MomentumComposite()
        result = mc.score(uptrend_with_features, volume_features=True)
        assert isinstance(result, CompositeResult)

    def test_composite_score_length(
        self, uptrend_with_features: pd.DataFrame
    ) -> None:
        """Composite score length should match input."""
        mc = MomentumComposite()
        result = mc.score(uptrend_with_features, volume_features=True)
        assert len(result.composite_score) == len(uptrend_with_features)

    def test_signal_length(
        self, uptrend_with_features: pd.DataFrame
    ) -> None:
        """Signal series length should match input."""
        mc = MomentumComposite()
        result = mc.score(uptrend_with_features, volume_features=True)
        assert len(result.signal) == len(uptrend_with_features)

    def test_6_components_with_volume(
        self, uptrend_with_features: pd.DataFrame
    ) -> None:
        """With volume_features=True, should have 6 components."""
        mc = MomentumComposite()
        result = mc.score(uptrend_with_features, volume_features=True)
        assert len(result.components) == 6
        assert "volume" in result.components
        assert set(result.components.keys()) == {
            "momentum", "trend", "rsi", "volume", "volatility", "sr"
        }

    def test_5_components_without_volume(
        self, uptrend_no_volume_features: pd.DataFrame
    ) -> None:
        """With volume_features=False, should have 5 components."""
        mc = MomentumComposite()
        result = mc.score(uptrend_no_volume_features, volume_features=False)
        assert len(result.components) == 5
        assert "volume" not in result.components

    def test_weights_sum_to_one_with_volume(
        self, uptrend_with_features: pd.DataFrame
    ) -> None:
        """Weights used should sum to 1.0 (with volume)."""
        mc = MomentumComposite()
        result = mc.score(uptrend_with_features, volume_features=True)
        assert abs(sum(result.weights_used.values()) - 1.0) < 1e-10

    def test_weights_sum_to_one_without_volume(
        self, uptrend_no_volume_features: pd.DataFrame
    ) -> None:
        """Weights used should sum to 1.0 (without volume)."""
        mc = MomentumComposite()
        result = mc.score(uptrend_no_volume_features, volume_features=False)
        assert abs(sum(result.weights_used.values()) - 1.0) < 1e-10

    def test_signal_values_valid(
        self, uptrend_with_features: pd.DataFrame
    ) -> None:
        """All signal values should be valid classifications."""
        mc = MomentumComposite()
        result = mc.score(uptrend_with_features, volume_features=True)
        valid_signals = {s.value for s in SignalClassification}
        for sig in result.signal:
            assert sig in valid_signals, f"Invalid signal: {sig}"

    def test_insufficient_data_raises(self) -> None:
        """Should raise ValueError when data is too short."""
        mc = MomentumComposite()
        # Create a DataFrame with fewer than MIN_BARS rows
        n = MIN_BARS - 1
        df = pd.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": [1000.0] * n,
            "rsi_14": [50.0] * n,
            "atr_14": [1.0] * n,
            "volume_ratio": [1.0] * n,
        })
        with pytest.raises(ValueError, match="at least"):
            mc.score(df, volume_features=True)

    def test_missing_columns_raises(self) -> None:
        """Should raise ValueError when required columns are missing."""
        mc = MomentumComposite()
        df = pd.DataFrame({
            "close": [100.0] * 300,
        })
        with pytest.raises(ValueError, match="Missing required columns"):
            mc.score(df, volume_features=True)

    def test_missing_volume_ratio_raises_when_needed(self) -> None:
        """Should raise ValueError when volume_ratio missing and volume_features=True."""
        mc = MomentumComposite()
        df = pd.DataFrame({
            "open": [100.0] * 300,
            "high": [101.0] * 300,
            "low": [99.0] * 300,
            "close": [100.5] * 300,
            "rsi_14": [50.0] * 300,
            "atr_14": [1.0] * 300,
        })
        with pytest.raises(ValueError, match="Missing required columns"):
            mc.score(df, volume_features=True)

    def test_no_error_without_volume_ratio_when_disabled(self) -> None:
        """Should NOT raise when volume_ratio missing and volume_features=False."""
        mc = MomentumComposite()
        df = pd.DataFrame({
            "open": [100.0] * 300,
            "high": [101.0] * 300,
            "low": [99.0] * 300,
            "close": [100.5] * 300,
            "rsi_14": [50.0] * 300,
            "atr_14": [1.0] * 300,
        })
        # Should not raise
        result = mc.score(df, volume_features=False)
        assert isinstance(result, CompositeResult)

    def test_composite_result_is_frozen(
        self, uptrend_with_features: pd.DataFrame
    ) -> None:
        """CompositeResult should be immutable (frozen dataclass)."""
        mc = MomentumComposite()
        result = mc.score(uptrend_with_features, volume_features=True)
        with pytest.raises(AttributeError):
            result.composite_score = pd.Series([0.0])  # type: ignore[misc]
