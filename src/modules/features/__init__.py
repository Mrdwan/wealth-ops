"""Feature Engine — orchestrates technical indicator computation.

Computes all base features for a given OHLCV DataFrame.
Profile-aware: respects the volume_features flag for asset class differences.
"""

from src.modules.features.engine import FeatureEngine

__all__ = ["FeatureEngine"]
