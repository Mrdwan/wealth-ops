"""Tests for DataManager orchestrator."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from botocore.exceptions import ClientError

from src.modules.data.manager import DataManager, FetchMode
from src.modules.data.protocols import ProviderError
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
def sample_df() -> pd.DataFrame:
    """Sample DataFrame for testing."""
    data = {
        "open": [150.0, 154.0],
        "high": [155.0, 158.0],
        "low": [149.0, 153.0],
        "close": [154.0, 157.0],
        "volume": [1000000, 1100000],
        "adjusted_close": [154.0, 157.0],
    }
    index = [date(2024, 1, 2), date(2024, 1, 3)]
    df = pd.DataFrame(data, index=index)
    df.index.name = "date"
    return df


class TestFetchModeLogic:
    """Tests for fetch mode determination."""

    def test_bootstrap_mode_when_no_last_updated(self, config: Config) -> None:
        """Test bootstrap mode when ticker has no history."""
        mock_primary = MagicMock()
        mock_fallback = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=mock_fallback,
            dynamodb_client=mock_dynamodb,
            s3_client=MagicMock(),
        )

        mode, start, end = manager._determine_fetch_params(
            last_updated=None,
            today=date(2024, 1, 5),
            max_history_years=50,
        )

        assert mode == FetchMode.BOOTSTRAP
        # Start should be ~50 years ago
        assert start < date(1980, 1, 1)

    def test_daily_drip_mode_when_current(self, config: Config) -> None:
        """Test daily drip when data is current."""
        mock_primary = MagicMock()
        mock_fallback = MagicMock()

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=mock_fallback,
            dynamodb_client=MagicMock(),
            s3_client=MagicMock(),
        )

        yesterday = date.today() - timedelta(days=1)
        mode, _, _ = manager._determine_fetch_params(
            last_updated=yesterday,
            today=date.today(),
            max_history_years=50,
        )

        assert mode == FetchMode.DAILY_DRIP

    def test_gap_fill_mode_when_missing_days(self, config: Config) -> None:
        """Test gap fill when multiple days missing."""
        mock_primary = MagicMock()
        mock_fallback = MagicMock()

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=mock_fallback,
            dynamodb_client=MagicMock(),
            s3_client=MagicMock(),
        )

        five_days_ago = date.today() - timedelta(days=5)
        mode, start, end = manager._determine_fetch_params(
            last_updated=five_days_ago,
            today=date.today(),
            max_history_years=50,
        )

        assert mode == FetchMode.GAP_FILL
        assert start == five_days_ago + timedelta(days=1)


class TestProviderFailover:
    """Tests for provider failover logic."""

    def test_uses_primary_when_successful(
        self,
        config: Config,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test primary provider is used when it succeeds."""
        mock_primary = MagicMock()
        mock_primary.get_daily_candles.return_value = sample_df

        mock_fallback = MagicMock()

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=mock_fallback,
            dynamodb_client=MagicMock(),
            s3_client=MagicMock(),
        )

        result = manager._fetch_with_failover("AAPL", date(2024, 1, 2), date(2024, 1, 3))

        mock_primary.get_daily_candles.assert_called_once()
        mock_fallback.get_daily_candles.assert_not_called()
        assert len(result) == 2

    def test_falls_back_when_primary_fails(
        self,
        config: Config,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test fallback is used when primary fails."""
        mock_primary = MagicMock()
        mock_primary.get_daily_candles.side_effect = ProviderError("Tiingo", "AAPL", "API Error")

        mock_fallback = MagicMock()
        mock_fallback.get_daily_candles.return_value = sample_df

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=mock_fallback,
            dynamodb_client=MagicMock(),
            s3_client=MagicMock(),
        )

        result = manager._fetch_with_failover("AAPL", date(2024, 1, 2), date(2024, 1, 3))

        mock_primary.get_daily_candles.assert_called_once()
        mock_fallback.get_daily_candles.assert_called_once()
        assert len(result) == 2

    def test_raises_when_both_fail(self, config: Config) -> None:
        """Test raises when both providers fail."""
        mock_primary = MagicMock()
        mock_primary.get_daily_candles.side_effect = ProviderError("Tiingo", "AAPL", "API Error")

        mock_fallback = MagicMock()
        mock_fallback.get_daily_candles.side_effect = ProviderError("Yahoo", "AAPL", "Rate limited")

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=mock_fallback,
            dynamodb_client=MagicMock(),
            s3_client=MagicMock(),
        )

        with pytest.raises(ProviderError):
            manager._fetch_with_failover("AAPL", date(2024, 1, 2), date(2024, 1, 3))


class TestIngestOrchestration:
    """Tests for the ingest() orchestration flow."""

    @patch("src.modules.data.manager.date")
    def test_ingest_full_flow(
        self,
        mock_date: MagicMock,
        config: Config,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test full ingest flow: bootstrap mode, fetch, save, update."""
        mock_date.today.return_value = date(2024, 1, 5)
        mock_date.fromisoformat = date.fromisoformat
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        mock_primary = MagicMock()
        mock_primary.get_daily_candles.return_value = sample_df

        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}  # No last_updated → BOOTSTRAP

        mock_s3 = MagicMock()

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
            s3_client=mock_s3,
        )

        result = manager.ingest("AAPL")

        assert result == 2
        mock_primary.get_daily_candles.assert_called_once()
        mock_s3.put_object.assert_called_once()
        mock_dynamodb.update_item.assert_called_once()

    @patch("src.modules.data.manager.date")
    def test_ingest_already_up_to_date(
        self,
        mock_date: MagicMock,
        config: Config,
    ) -> None:
        """Test ingest returns 0 when data is already up to date."""
        today = date(2024, 1, 5)
        yesterday = date(2024, 1, 4)
        mock_date.today.return_value = today
        mock_date.fromisoformat = date.fromisoformat
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {"ticker": {"S": "AAPL"}, "last_updated_date": {"S": yesterday.isoformat()}}
        }

        mock_primary = MagicMock()

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
            s3_client=MagicMock(),
        )

        result = manager.ingest("AAPL")

        assert result == 0
        mock_primary.get_daily_candles.assert_not_called()

    @patch("src.modules.data.manager.date")
    def test_ingest_empty_dataframe(
        self,
        mock_date: MagicMock,
        config: Config,
    ) -> None:
        """Test ingest returns 0 when provider returns empty DataFrame."""
        mock_date.today.return_value = date(2024, 1, 5)
        mock_date.fromisoformat = date.fromisoformat
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        mock_primary = MagicMock()
        mock_primary.get_daily_candles.return_value = pd.DataFrame()

        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}

        mock_s3 = MagicMock()

        manager = DataManager(
            config=config,
            primary_provider=mock_primary,
            fallback_provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
            s3_client=mock_s3,
        )

        result = manager.ingest("AAPL")

        assert result == 0
        mock_s3.put_object.assert_not_called()


class TestDetermineParams:
    """Tests for fetch parameter edge cases."""

    def test_daily_drip_two_days_ago(self, config: Config) -> None:
        """Test DAILY_DRIP when last_updated is exactly 2 days ago."""
        manager = DataManager(
            config=config,
            primary_provider=MagicMock(),
            fallback_provider=MagicMock(),
            dynamodb_client=MagicMock(),
            s3_client=MagicMock(),
        )

        today = date(2024, 1, 5)
        two_days_ago = today - timedelta(days=2)
        yesterday = today - timedelta(days=1)

        mode, start, end = manager._determine_fetch_params(
            last_updated=two_days_ago,
            today=today,
            max_history_years=50,
        )

        assert mode == FetchMode.DAILY_DRIP
        assert start == yesterday
        assert end == yesterday


class TestDynamoDBOperations:
    """Tests for DynamoDB read/write operations."""

    def test_get_last_updated_returns_date(self, config: Config) -> None:
        """Test _get_last_updated returns date when item exists."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {"ticker": {"S": "AAPL"}, "last_updated_date": {"S": "2024-01-05"}}
        }

        manager = DataManager(
            config=config,
            primary_provider=MagicMock(),
            fallback_provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
            s3_client=MagicMock(),
        )

        result = manager._get_last_updated("AAPL")

        assert result == date(2024, 1, 5)

    def test_get_last_updated_no_item(self, config: Config) -> None:
        """Test _get_last_updated returns None when no item exists."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}

        manager = DataManager(
            config=config,
            primary_provider=MagicMock(),
            fallback_provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
            s3_client=MagicMock(),
        )

        result = manager._get_last_updated("AAPL")

        assert result is None

    def test_get_last_updated_client_error(self, config: Config) -> None:
        """Test _get_last_updated returns None on ClientError."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
            "GetItem",
        )

        manager = DataManager(
            config=config,
            primary_provider=MagicMock(),
            fallback_provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
            s3_client=MagicMock(),
        )

        result = manager._get_last_updated("AAPL")

        assert result is None

    def test_update_last_updated_success(self, config: Config) -> None:
        """Test _update_last_updated calls DynamoDB with correct args."""
        mock_dynamodb = MagicMock()

        manager = DataManager(
            config=config,
            primary_provider=MagicMock(),
            fallback_provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
            s3_client=MagicMock(),
        )

        manager._update_last_updated("AAPL", date(2024, 1, 5))

        mock_dynamodb.update_item.assert_called_once()
        call_kwargs = mock_dynamodb.update_item.call_args[1]
        assert call_kwargs["TableName"] == "test-config"
        assert call_kwargs["Key"] == {"ticker": {"S": "AAPL"}}
        assert ":d" in call_kwargs["ExpressionAttributeValues"]

    def test_update_last_updated_client_error(self, config: Config) -> None:
        """Test _update_last_updated re-raises ClientError."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Condition failed"}},
            "UpdateItem",
        )

        manager = DataManager(
            config=config,
            primary_provider=MagicMock(),
            fallback_provider=MagicMock(),
            dynamodb_client=mock_dynamodb,
            s3_client=MagicMock(),
        )

        with pytest.raises(ClientError):
            manager._update_last_updated("AAPL", date(2024, 1, 5))


class TestS3Operations:
    """Tests for S3 save operations."""

    def test_save_to_s3_success(self, config: Config, sample_df: pd.DataFrame) -> None:
        """Test _save_to_s3 converts to Parquet and uploads."""
        mock_s3 = MagicMock()

        manager = DataManager(
            config=config,
            primary_provider=MagicMock(),
            fallback_provider=MagicMock(),
            dynamodb_client=MagicMock(),
            s3_client=mock_s3,
        )

        manager._save_to_s3("AAPL", sample_df)

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "raw/AAPL/2024-01-02_2024-01-03.parquet"
        assert len(call_kwargs["Body"]) > 0

    def test_save_to_s3_client_error(self, config: Config, sample_df: pd.DataFrame) -> None:
        """Test _save_to_s3 re-raises ClientError."""
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "PutObject",
        )

        manager = DataManager(
            config=config,
            primary_provider=MagicMock(),
            fallback_provider=MagicMock(),
            dynamodb_client=MagicMock(),
            s3_client=mock_s3,
        )

        with pytest.raises(ClientError):
            manager._save_to_s3("AAPL", sample_df)
