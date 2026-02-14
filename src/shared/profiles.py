"""Asset Profile Schema v3.

Defines the typed profile schema for multi-asset trading.
Each asset in DynamoDB:Config carries a profile that configures
the entire pipeline: data source, guards, features, broker, and tax.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetProfile:
    """Asset profile that configures the pipeline for a given ticker.

    Attributes:
        asset_class: Instrument category (EQUITY, COMMODITY, INDEX).
        regime_index: Ticker for Macro Gate (e.g., SPY, UUP).
        regime_direction: Buy condition relative to regime (BULL, BEAR, ANY).
        vix_guard: Whether Panic Guard applies.
        event_guard: Whether Earnings Guard applies.
        macro_event_guard: Whether FOMC/NFP blackout applies.
        volume_features: Whether OBV + Volume Ratio are computed.
        benchmark_index: Relative Strength benchmark ticker (SPY, UUP, or empty).
        concentration_group: Grouping for Concentration Limit.
        broker: Execution broker (IG, IBKR, PAPER).
        tax_rate: Applicable tax rate (0.0, 0.33, 0.41).
        data_source: Primary data provider (TIINGO, TIINGO_FOREX, FRED).
    """

    asset_class: str
    regime_index: str
    regime_direction: str
    vix_guard: bool
    event_guard: bool
    macro_event_guard: bool
    volume_features: bool
    benchmark_index: str
    concentration_group: str
    broker: str
    tax_rate: float
    data_source: str

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> AssetProfile:
        """Parse a DynamoDB item dict into an AssetProfile.

        Missing fields fall back to safe EQUITY defaults.

        Args:
            item: DynamoDB item with string/bool/number attribute values.

        Returns:
            Parsed AssetProfile.
        """
        return cls(
            asset_class=_get_str(item, "asset_class", "EQUITY"),
            regime_index=_get_str(item, "regime_index", "SPY"),
            regime_direction=_get_str(item, "regime_direction", "BULL"),
            vix_guard=_get_bool(item, "vix_guard", default=True),
            event_guard=_get_bool(item, "event_guard", default=True),
            macro_event_guard=_get_bool(item, "macro_event_guard", default=False),
            volume_features=_get_bool(item, "volume_features", default=True),
            benchmark_index=_get_str(item, "benchmark_index", "SPY"),
            concentration_group=_get_str(item, "concentration_group", ""),
            broker=_get_str(item, "broker", "PAPER"),
            tax_rate=_get_number(item, "tax_rate", default=0.33),
            data_source=_get_str(item, "data_source", "TIINGO"),
        )

    def to_dynamodb_item(self, ticker: str, enabled: bool = True) -> dict[str, Any]:
        """Convert profile to a DynamoDB item dict.

        Args:
            ticker: Ticker symbol (becomes the partition key).
            enabled: Whether the ticker is active for ingestion.

        Returns:
            DynamoDB-formatted item dict.
        """
        return {
            "ticker": {"S": ticker},
            "enabled": {"BOOL": enabled},
            "asset_class": {"S": self.asset_class},
            "regime_index": {"S": self.regime_index},
            "regime_direction": {"S": self.regime_direction},
            "vix_guard": {"BOOL": self.vix_guard},
            "event_guard": {"BOOL": self.event_guard},
            "macro_event_guard": {"BOOL": self.macro_event_guard},
            "volume_features": {"BOOL": self.volume_features},
            "benchmark_index": {"S": self.benchmark_index},
            "concentration_group": {"S": self.concentration_group},
            "broker": {"S": self.broker},
            "tax_rate": {"N": str(self.tax_rate)},
            "data_source": {"S": self.data_source},
        }

    def s3_prefix(self) -> str:
        """Return the S3 path prefix for this profile's asset class.

        Returns:
            S3 prefix string (e.g., 'ohlcv/stocks/', 'ohlcv/forex/').
        """
        prefix_map = {
            "EQUITY": "ohlcv/stocks",
            "COMMODITY": "ohlcv/forex",
            "INDEX": "ohlcv/indices",
        }
        return prefix_map.get(self.asset_class, "ohlcv/stocks")


def _get_str(item: dict[str, Any], key: str, default: str) -> str:
    """Extract a string attribute from a DynamoDB item."""
    if key in item and "S" in item[key]:
        return str(item[key]["S"])
    return default


def _get_bool(item: dict[str, Any], key: str, *, default: bool) -> bool:
    """Extract a boolean attribute from a DynamoDB item."""
    if key in item and "BOOL" in item[key]:
        return bool(item[key]["BOOL"])
    return default


def _get_number(item: dict[str, Any], key: str, *, default: float) -> float:
    """Extract a number attribute from a DynamoDB item."""
    if key in item and "N" in item[key]:
        return float(item[key]["N"])
    return default


# --- Pre-built Profile Templates ---

EQUITY_PROFILE = AssetProfile(
    asset_class="EQUITY",
    regime_index="SPY",
    regime_direction="BULL",
    vix_guard=True,
    event_guard=True,
    macro_event_guard=False,
    volume_features=True,
    benchmark_index="SPY",
    concentration_group="",
    broker="IBKR",
    tax_rate=0.33,
    data_source="TIINGO",
)

COMMODITY_HAVEN_PROFILE = AssetProfile(
    asset_class="COMMODITY",
    regime_index="UUP",
    regime_direction="BEAR",
    vix_guard=False,
    event_guard=False,
    macro_event_guard=True,
    volume_features=False,
    benchmark_index="UUP",
    concentration_group="PRECIOUS_METALS",
    broker="IG",
    tax_rate=0.0,
    data_source="TIINGO_FOREX",
)

COMMODITY_CYCLICAL_PROFILE = AssetProfile(
    asset_class="COMMODITY",
    regime_index="SPY",
    regime_direction="BULL",
    vix_guard=True,
    event_guard=False,
    macro_event_guard=True,
    volume_features=True,
    benchmark_index="UUP",
    concentration_group="CYCLICAL",
    broker="IG",
    tax_rate=0.0,
    data_source="TIINGO",
)

INDEX_PROFILE = AssetProfile(
    asset_class="INDEX",
    regime_index="",
    regime_direction="ANY",
    vix_guard=False,
    event_guard=False,
    macro_event_guard=False,
    volume_features=True,
    benchmark_index="",
    concentration_group="",
    broker="PAPER",
    tax_rate=0.0,
    data_source="TIINGO",
)
