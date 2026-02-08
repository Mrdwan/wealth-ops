"""Tests for Regime Filter module."""

from datetime import date
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from botocore.exceptions import ClientError

from src.modules.regime.filter import MarketStatus, RegimeFilter
from src.shared.config import Config


@pytest.fixture
def config() -> Config:
    """Create test configuration."""
    return Config(
        aws_region="us-east-1",
        s3_bucket="test-bucket",
        config_table="test-config",
        ledger_table="test-ledger",
        portfolio_table="test-portfolio",
        system_table="test-system",
        tiingo_api_key="test-key",
        telegram_bot_token="",
        telegram_chat_id="",
        environment="test",
    )


@pytest.fixture
def bull_market_df() -> pd.DataFrame:
    """DataFrame where current close > 200-day SMA (BULL)."""
    # 250 days of data with upward trend
    dates = [date(2024, 1, 1) + pd.Timedelta(days=i) for i in range(250)]
    closes = [100 + i * 0.5 for i in range(250)]  # Upward trend

    df = pd.DataFrame({"close": closes}, index=dates)
    df.index.name = "date"
    return df


@pytest.fixture
def bear_market_df() -> pd.DataFrame:
    """DataFrame where current close < 200-day SMA (BEAR)."""
    # 250 days of data with downward trend at end
    dates = [date(2024, 1, 1) + pd.Timedelta(days=i) for i in range(250)]
    closes = [200 - i * 0.3 for i in range(250)]  # Downward trend

    df = pd.DataFrame({"close": closes}, index=dates)
    df.index.name = "date"
    return df


class TestRegimeFilter:
    """Tests for RegimeFilter."""

    def test_bull_market_detected(
        self,
        config: Config,
        bull_market_df: pd.DataFrame,
    ) -> None:
        """Test BULL status when close > SMA200."""
        mock_provider = MagicMock()
        mock_provider.get_daily_candles.return_value = bull_market_df

        mock_dynamodb = MagicMock()
        mock_dynamodb.put_item.return_value = {}

        filter = RegimeFilter(
            config=config,
            provider=mock_provider,
            dynamodb_client=mock_dynamodb,
        )

        status = filter.evaluate()

        assert status == MarketStatus.BULL
        mock_dynamodb.put_item.assert_called_once()

    def test_bear_market_detected(
        self,
        config: Config,
        bear_market_df: pd.DataFrame,
    ) -> None:
        """Test BEAR status when close < SMA200."""
        mock_provider = MagicMock()
        mock_provider.get_daily_candles.return_value = bear_market_df

        mock_dynamodb = MagicMock()
        mock_dynamodb.put_item.return_value = {}

        filter = RegimeFilter(
            config=config,
            provider=mock_provider,
            dynamodb_client=mock_dynamodb,
        )

        status = filter.evaluate()

        assert status == MarketStatus.BEAR

    def test_unknown_on_insufficient_data(self, config: Config) -> None:
        """Test UNKNOWN when not enough data for 200-day MA."""
        # Only 50 days of data
        dates = [date(2024, 1, 1) + pd.Timedelta(days=i) for i in range(50)]
        closes = [100 + i for i in range(50)]
        df = pd.DataFrame({"close": closes}, index=dates)
        df.index.name = "date"

        mock_provider = MagicMock()
        mock_provider.get_daily_candles.return_value = df

        mock_dynamodb = MagicMock()

        filter = RegimeFilter(
            config=config,
            provider=mock_provider,
            dynamodb_client=mock_dynamodb,
        )

        status = filter.evaluate()

        assert status == MarketStatus.UNKNOWN

    def test_get_current_status_from_dynamodb(self, config: Config) -> None:
        """Test reading current status from DynamoDB."""
        mock_provider = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "market_status"},
                "value": {"S": "BULL"},
            }
        }

        filter = RegimeFilter(
            config=config,
            provider=mock_provider,
            dynamodb_client=mock_dynamodb,
        )

        status = filter.get_current_status()

        assert status == MarketStatus.BULL


class TestRegimeFilterErrorHandling:
    """Tests for error handling in RegimeFilter."""

    def test_evaluate_exception_returns_unknown(self, config: Config) -> None:
        """Test evaluate returns UNKNOWN when provider raises exception."""
        mock_provider = MagicMock()
        mock_provider.get_daily_candles.side_effect = Exception("Network error")

        mock_dynamodb = MagicMock()

        regime_filter = RegimeFilter(
            config=config,
            provider=mock_provider,
            dynamodb_client=mock_dynamodb,
        )

        status = regime_filter.evaluate()

        assert status == MarketStatus.UNKNOWN

    def test_get_current_status_no_value_key(self, config: Config) -> None:
        """Test get_current_status returns UNKNOWN when item has no value key."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {"key": {"S": "market_status"}}
        }

        regime_filter = RegimeFilter(
            config=config,
            provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        status = regime_filter.get_current_status()

        assert status == MarketStatus.UNKNOWN

    def test_get_current_status_client_error(self, config: Config) -> None:
        """Test get_current_status returns UNKNOWN on ClientError."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
            "GetItem",
        )

        regime_filter = RegimeFilter(
            config=config,
            provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        status = regime_filter.get_current_status()

        assert status == MarketStatus.UNKNOWN

    def test_get_current_status_invalid_value(self, config: Config) -> None:
        """Test get_current_status returns UNKNOWN for invalid enum value."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {"key": {"S": "market_status"}, "value": {"S": "INVALID"}}
        }

        regime_filter = RegimeFilter(
            config=config,
            provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        status = regime_filter.get_current_status()

        assert status == MarketStatus.UNKNOWN

    def test_calculate_regime_nan_sma_returns_unknown(self, config: Config) -> None:
        """Test UNKNOWN when SMA200 is NaN due to missing data."""
        # 200 rows but one NaN close value makes rolling(200).mean() NaN
        dates = [date(2024, 1, 1) + pd.Timedelta(days=i) for i in range(200)]
        closes = [100.0 + i for i in range(200)]
        closes[50] = np.nan  # One NaN → rolling window can't compute mean

        df = pd.DataFrame({"close": closes}, index=dates)
        df.index.name = "date"

        mock_provider = MagicMock()
        mock_provider.get_daily_candles.return_value = df

        mock_dynamodb = MagicMock()

        regime_filter = RegimeFilter(
            config=config,
            provider=mock_provider,
            dynamodb_client=mock_dynamodb,
        )

        status = regime_filter.evaluate()

        assert status == MarketStatus.UNKNOWN

    def test_update_status_client_error_reraises(self, config: Config) -> None:
        """Test _update_status re-raises ClientError."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "failed"}},
            "PutItem",
        )

        regime_filter = RegimeFilter(
            config=config,
            provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        with pytest.raises(ClientError):
            regime_filter._update_status(MarketStatus.BULL)
