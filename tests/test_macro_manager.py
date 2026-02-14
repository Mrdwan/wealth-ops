"""Tests for MacroDataManager."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from botocore.exceptions import ClientError

from src.modules.data.macro_manager import MACRO_SERIES, MacroDataManager
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
        tiingo_api_key="",
        fred_api_key="test-fred-key",
        telegram_bot_token="",
        telegram_chat_id="",
        environment="test",
    )


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create sample macro DataFrame."""
    return pd.DataFrame(
        {"value": [16.5, 17.2, 15.8]},
        index=pd.Index(
            [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
            name="date",
        ),
    )


class TestMacroDataManager:
    """Tests for MacroDataManager."""

    def test_ingest_all_success(self, config: Config, sample_df: pd.DataFrame) -> None:
        """Test successful ingestion of all macro series."""
        mock_provider = MagicMock()
        mock_provider.get_observations.return_value = sample_df

        manager = MacroDataManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        results = manager.ingest_all(lookback_years=5)

        assert len(results) == len(MACRO_SERIES)
        for series_id, _ in MACRO_SERIES:
            assert results[series_id] == 3

    def test_ingest_all_partial_failure(
        self, config: Config, sample_df: pd.DataFrame
    ) -> None:
        """Test ingestion with one series failing."""
        mock_provider = MagicMock()
        mock_provider.get_observations.side_effect = [
            sample_df,
            Exception("API Error"),
            sample_df,
            sample_df,
        ]

        manager = MacroDataManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        results = manager.ingest_all()

        failed = [sid for sid, count in results.items() if count == -1]
        succeeded = [sid for sid, count in results.items() if count > 0]
        assert len(failed) == 1
        assert len(succeeded) == 3

    def test_ingest_saves_to_correct_s3_path(
        self, config: Config, sample_df: pd.DataFrame
    ) -> None:
        """Test that macro data is saved to ohlcv/macro/{series}.parquet."""
        mock_provider = MagicMock()
        mock_provider.get_observations.return_value = sample_df
        mock_s3 = MagicMock()

        manager = MacroDataManager(
            config=config,
            provider=mock_provider,
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        manager._ingest_series("VIXCLS", date(2024, 1, 1), date(2024, 1, 4))

        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Key"] == "ohlcv/macro/VIXCLS.parquet"
        assert call_kwargs["Bucket"] == "test-bucket"

    def test_ingest_updates_staleness(
        self, config: Config, sample_df: pd.DataFrame
    ) -> None:
        """Test that staleness timestamp is updated after ingestion."""
        mock_provider = MagicMock()
        mock_provider.get_observations.return_value = sample_df
        mock_dynamodb = MagicMock()

        manager = MacroDataManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        manager._ingest_series("VIXCLS", date(2024, 1, 1), date(2024, 1, 4))

        mock_dynamodb.put_item.assert_called_once()
        put_kwargs = mock_dynamodb.put_item.call_args[1]
        assert put_kwargs["Item"]["key"]["S"] == "macro_staleness_VIXCLS"
        assert "updated_at" in put_kwargs["Item"]

    def test_ingest_empty_df_returns_zero(self, config: Config) -> None:
        """Test that empty observation DataFrame returns 0 count."""
        mock_provider = MagicMock()
        mock_provider.get_observations.return_value = pd.DataFrame(columns=["value"])

        manager = MacroDataManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        count = manager._ingest_series("VIXCLS", date(2024, 1, 1), date(2024, 1, 4))

        assert count == 0

    def test_get_threshold_unknown_series_returns_default(self, config: Config) -> None:
        """Test that unknown series ID returns default 24h threshold."""
        manager = MacroDataManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        assert manager._get_threshold("UNKNOWN_SERIES") == 24

    def test_save_to_s3_client_error_raises(
        self, config: Config, sample_df: pd.DataFrame
    ) -> None:
        """Test that S3 ClientError in _save_to_s3 is re-raised."""
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "fail"}},
            "PutObject",
        )

        manager = MacroDataManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        with pytest.raises(ClientError):
            manager._save_to_s3("VIXCLS", sample_df)

    def test_update_staleness_client_error_raises(self, config: Config) -> None:
        """Test that DynamoDB ClientError in _update_staleness is re-raised."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "fail"}},
            "PutItem",
        )

        manager = MacroDataManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        with pytest.raises(ClientError):
            manager._update_staleness("VIXCLS")


class TestStalenessCheck:
    """Tests for staleness checking."""

    def test_stale_when_no_record(self, config: Config) -> None:
        """Test that missing staleness record means stale."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}

        manager = MacroDataManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("VIXCLS") is True

    def test_not_stale_when_recent(self, config: Config) -> None:
        """Test that recently updated series is not stale."""
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "macro_staleness_VIXCLS"},
                "updated_at": {"S": recent_time.isoformat()},
            }
        }

        manager = MacroDataManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("VIXCLS") is False

    def test_stale_when_old(self, config: Config) -> None:
        """Test that old VIX data (>24h) is stale."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "macro_staleness_VIXCLS"},
                "updated_at": {"S": old_time.isoformat()},
            }
        }

        manager = MacroDataManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("VIXCLS") is True

    def test_monthly_series_not_stale_after_one_day(self, config: Config) -> None:
        """Test that monthly series (FEDFUNDS) isn't stale after 1 day."""
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=25)
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "macro_staleness_FEDFUNDS"},
                "updated_at": {"S": one_day_ago.isoformat()},
            }
        }

        manager = MacroDataManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        # FEDFUNDS has 840h threshold — 25h should NOT be stale
        assert manager.check_staleness("FEDFUNDS") is False

    def test_stale_on_dynamodb_error(self, config: Config) -> None:
        """Test that DynamoDB errors default to stale (safe)."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "fail"}},
            "GetItem",
        )

        manager = MacroDataManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("VIXCLS") is True


class TestMacroSeriesConfig:
    """Tests for macro series configuration."""

    def test_all_required_series_configured(self) -> None:
        """Test that all required macro series are in MACRO_SERIES."""
        series_ids = [sid for sid, _ in MACRO_SERIES]
        assert "VIXCLS" in series_ids
        assert "T10Y2Y" in series_ids
        assert "FEDFUNDS" in series_ids
        assert "CPIAUCSL" in series_ids

    def test_daily_series_have_24h_threshold(self) -> None:
        """Test that daily series have 24-hour staleness threshold."""
        thresholds = {sid: hours for sid, hours in MACRO_SERIES}
        assert thresholds["VIXCLS"] == 24
        assert thresholds["T10Y2Y"] == 24

    def test_monthly_series_have_extended_threshold(self) -> None:
        """Test that monthly series have ~35 day staleness threshold."""
        thresholds = {sid: hours for sid, hours in MACRO_SERIES}
        assert thresholds["FEDFUNDS"] == 840
        assert thresholds["CPIAUCSL"] == 840
