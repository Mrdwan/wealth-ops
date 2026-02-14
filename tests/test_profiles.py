"""Tests for asset profile schema and helpers."""

import pytest

from src.shared.profiles import (
    COMMODITY_CYCLICAL_PROFILE,
    COMMODITY_HAVEN_PROFILE,
    EQUITY_PROFILE,
    INDEX_PROFILE,
    AssetProfile,
)


class TestAssetProfile:
    """Tests for AssetProfile dataclass."""

    def test_equity_profile_values(self) -> None:
        """Test EQUITY profile template has correct values."""
        p = EQUITY_PROFILE
        assert p.asset_class == "EQUITY"
        assert p.regime_index == "SPY"
        assert p.regime_direction == "BULL"
        assert p.vix_guard is True
        assert p.event_guard is True
        assert p.macro_event_guard is False
        assert p.volume_features is True
        assert p.benchmark_index == "SPY"
        assert p.broker == "IBKR"
        assert p.tax_rate == 0.33
        assert p.data_source == "TIINGO"

    def test_commodity_haven_profile_values(self) -> None:
        """Test COMMODITY_HAVEN profile template has correct values."""
        p = COMMODITY_HAVEN_PROFILE
        assert p.asset_class == "COMMODITY"
        assert p.regime_index == "UUP"
        assert p.regime_direction == "BEAR"
        assert p.vix_guard is False
        assert p.event_guard is False
        assert p.macro_event_guard is True
        assert p.volume_features is False
        assert p.benchmark_index == "UUP"
        assert p.broker == "IG"
        assert p.tax_rate == 0.0
        assert p.data_source == "TIINGO_FOREX"

    def test_commodity_cyclical_profile_values(self) -> None:
        """Test COMMODITY_CYCLICAL profile template has correct values."""
        p = COMMODITY_CYCLICAL_PROFILE
        assert p.asset_class == "COMMODITY"
        assert p.regime_index == "SPY"
        assert p.regime_direction == "BULL"
        assert p.vix_guard is True
        assert p.macro_event_guard is True
        assert p.volume_features is True
        assert p.broker == "IG"
        assert p.tax_rate == 0.0

    def test_index_profile_values(self) -> None:
        """Test INDEX profile template has correct values."""
        p = INDEX_PROFILE
        assert p.asset_class == "INDEX"
        assert p.regime_direction == "ANY"
        assert p.broker == "PAPER"
        assert p.data_source == "TIINGO"

    def test_profile_is_frozen(self) -> None:
        """Test that AssetProfile is immutable."""
        with pytest.raises(AttributeError):
            EQUITY_PROFILE.broker = "IG"  # type: ignore[misc]


class TestFromDynamoDBItem:
    """Tests for AssetProfile.from_dynamodb_item()."""

    def test_parses_full_item(self) -> None:
        """Test parsing a fully populated DynamoDB item."""
        item = {
            "ticker": {"S": "AAPL"},
            "enabled": {"BOOL": True},
            "asset_class": {"S": "EQUITY"},
            "regime_index": {"S": "SPY"},
            "regime_direction": {"S": "BULL"},
            "vix_guard": {"BOOL": True},
            "event_guard": {"BOOL": True},
            "macro_event_guard": {"BOOL": False},
            "volume_features": {"BOOL": True},
            "benchmark_index": {"S": "SPY"},
            "concentration_group": {"S": "TECH"},
            "broker": {"S": "IBKR"},
            "tax_rate": {"N": "0.33"},
            "data_source": {"S": "TIINGO"},
        }

        profile = AssetProfile.from_dynamodb_item(item)

        assert profile.asset_class == "EQUITY"
        assert profile.regime_index == "SPY"
        assert profile.regime_direction == "BULL"
        assert profile.vix_guard is True
        assert profile.event_guard is True
        assert profile.macro_event_guard is False
        assert profile.volume_features is True
        assert profile.benchmark_index == "SPY"
        assert profile.concentration_group == "TECH"
        assert profile.broker == "IBKR"
        assert profile.tax_rate == 0.33
        assert profile.data_source == "TIINGO"

    def test_missing_fields_use_safe_defaults(self) -> None:
        """Test that missing fields fall back to safe EQUITY defaults."""
        item = {"ticker": {"S": "UNKNOWN"}}

        profile = AssetProfile.from_dynamodb_item(item)

        assert profile.asset_class == "EQUITY"
        assert profile.regime_index == "SPY"
        assert profile.regime_direction == "BULL"
        assert profile.vix_guard is True
        assert profile.event_guard is True
        assert profile.macro_event_guard is False
        assert profile.volume_features is True
        assert profile.benchmark_index == "SPY"
        assert profile.concentration_group == ""
        assert profile.broker == "PAPER"
        assert profile.tax_rate == 0.33
        assert profile.data_source == "TIINGO"

    def test_empty_item_uses_defaults(self) -> None:
        """Test that an empty item returns all defaults."""
        profile = AssetProfile.from_dynamodb_item({})

        assert profile.asset_class == "EQUITY"
        assert profile.broker == "PAPER"

    def test_commodity_haven_item(self) -> None:
        """Test parsing a COMMODITY_HAVEN DynamoDB item."""
        item = {
            "ticker": {"S": "XAUUSD"},
            "asset_class": {"S": "COMMODITY"},
            "regime_index": {"S": "UUP"},
            "regime_direction": {"S": "BEAR"},
            "vix_guard": {"BOOL": False},
            "event_guard": {"BOOL": False},
            "macro_event_guard": {"BOOL": True},
            "volume_features": {"BOOL": False},
            "benchmark_index": {"S": "UUP"},
            "concentration_group": {"S": "PRECIOUS_METALS"},
            "broker": {"S": "IG"},
            "tax_rate": {"N": "0.0"},
            "data_source": {"S": "TIINGO_FOREX"},
        }

        profile = AssetProfile.from_dynamodb_item(item)

        assert profile.asset_class == "COMMODITY"
        assert profile.broker == "IG"
        assert profile.tax_rate == 0.0
        assert profile.data_source == "TIINGO_FOREX"
        assert profile.macro_event_guard is True
        assert profile.volume_features is False


class TestToDynamoDBItem:
    """Tests for AssetProfile.to_dynamodb_item()."""

    def test_equity_to_item(self) -> None:
        """Test converting EQUITY profile to DynamoDB item."""
        item = EQUITY_PROFILE.to_dynamodb_item("AAPL", enabled=True)

        assert item["ticker"] == {"S": "AAPL"}
        assert item["enabled"] == {"BOOL": True}
        assert item["asset_class"] == {"S": "EQUITY"}
        assert item["broker"] == {"S": "IBKR"}
        assert item["tax_rate"] == {"N": "0.33"}
        assert item["data_source"] == {"S": "TIINGO"}

    def test_disabled_ticker(self) -> None:
        """Test that enabled=False is written correctly."""
        item = EQUITY_PROFILE.to_dynamodb_item("AAPL", enabled=False)
        assert item["enabled"] == {"BOOL": False}

    def test_roundtrip(self) -> None:
        """Test that to_dynamodb_item -> from_dynamodb_item preserves values."""
        original = COMMODITY_HAVEN_PROFILE
        item = original.to_dynamodb_item("XAUUSD")
        restored = AssetProfile.from_dynamodb_item(item)

        assert restored == original


class TestS3Prefix:
    """Tests for AssetProfile.s3_prefix()."""

    def test_equity_prefix(self) -> None:
        """Test EQUITY maps to ohlcv/stocks."""
        assert EQUITY_PROFILE.s3_prefix() == "ohlcv/stocks"

    def test_commodity_prefix(self) -> None:
        """Test COMMODITY maps to ohlcv/forex."""
        assert COMMODITY_HAVEN_PROFILE.s3_prefix() == "ohlcv/forex"

    def test_index_prefix(self) -> None:
        """Test INDEX maps to ohlcv/indices."""
        assert INDEX_PROFILE.s3_prefix() == "ohlcv/indices"

    def test_unknown_asset_class_defaults_to_stocks(self) -> None:
        """Test unknown asset class falls back to ohlcv/stocks."""
        profile = AssetProfile(
            asset_class="CRYPTO",
            regime_index="",
            regime_direction="ANY",
            vix_guard=False,
            event_guard=False,
            macro_event_guard=False,
            volume_features=False,
            benchmark_index="",
            concentration_group="",
            broker="PAPER",
            tax_rate=0.0,
            data_source="TIINGO",
        )
        assert profile.s3_prefix() == "ohlcv/stocks"
