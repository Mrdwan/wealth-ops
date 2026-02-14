"""Tests for EarningsCalendarManager."""

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.modules.data.earnings_manager import (
    EARNINGS_STALENESS_HOURS,
    EarningsCalendarManager,
)
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
        tiingo_api_key="test-tiingo-key",
        fred_api_key="",
        telegram_bot_token="",
        telegram_chat_id="",
        environment="test",
    )


@pytest.fixture
def sample_dates() -> list[date]:
    """Sample quarterly earnings dates (approx quarterly)."""
    return [
        date(2024, 1, 25),
        date(2024, 4, 25),
        date(2024, 7, 31),
        date(2024, 11, 1),
    ]


def _make_s3_body(ticker: str, dates: list[date]) -> MagicMock:
    """Helper to create a mock S3 response body."""
    payload = json.dumps(
        {"ticker": ticker, "dates": [d.isoformat() for d in dates]}
    )
    body = MagicMock()
    body.read.return_value = payload.encode("utf-8")
    return body


class TestIngestion:
    """Tests for earnings calendar ingestion."""

    def test_ingest_success(
        self, config: Config, sample_dates: list[date]
    ) -> None:
        """Test successful single-ticker ingestion."""
        mock_provider = MagicMock()
        mock_provider.get_statement_dates.return_value = sample_dates

        manager = EarningsCalendarManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        count = manager.ingest("AAPL")

        assert count == 4
        mock_provider.get_statement_dates.assert_called_once()

    def test_ingest_empty_returns_zero(self, config: Config) -> None:
        """Test that no earnings dates returns 0 count."""
        mock_provider = MagicMock()
        mock_provider.get_statement_dates.return_value = []

        manager = EarningsCalendarManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        count = manager.ingest("AAPL")

        assert count == 0

    def test_ingest_saves_to_correct_s3_path(
        self, config: Config, sample_dates: list[date]
    ) -> None:
        """Test that earnings data is saved to earnings/calendar_{ticker}.json."""
        mock_provider = MagicMock()
        mock_provider.get_statement_dates.return_value = sample_dates
        mock_s3 = MagicMock()

        manager = EarningsCalendarManager(
            config=config,
            provider=mock_provider,
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        manager.ingest("AAPL")

        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Key"] == "earnings/calendar_AAPL.json"
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["ContentType"] == "application/json"

        # Verify the JSON payload
        body = json.loads(call_kwargs["Body"].decode("utf-8"))
        assert body["ticker"] == "AAPL"
        assert len(body["dates"]) == 4

    def test_ingest_updates_staleness(
        self, config: Config, sample_dates: list[date]
    ) -> None:
        """Test that staleness timestamp is updated after ingestion."""
        mock_provider = MagicMock()
        mock_provider.get_statement_dates.return_value = sample_dates
        mock_dynamodb = MagicMock()

        manager = EarningsCalendarManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        manager.ingest("AAPL")

        mock_dynamodb.put_item.assert_called_once()
        put_kwargs = mock_dynamodb.put_item.call_args[1]
        assert put_kwargs["Item"]["key"]["S"] == "earnings_staleness_AAPL"
        assert "updated_at" in put_kwargs["Item"]

    def test_ingest_all_success(
        self, config: Config, sample_dates: list[date]
    ) -> None:
        """Test batch ingestion of multiple tickers."""
        mock_provider = MagicMock()
        mock_provider.get_statement_dates.return_value = sample_dates

        manager = EarningsCalendarManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        results = manager.ingest_all(["AAPL", "NVDA", "MSFT"])

        assert len(results) == 3
        assert all(count == 4 for count in results.values())

    def test_ingest_all_partial_failure(
        self, config: Config, sample_dates: list[date]
    ) -> None:
        """Test batch ingestion with one ticker failing."""
        mock_provider = MagicMock()
        mock_provider.get_statement_dates.side_effect = [
            sample_dates,
            Exception("API Error"),
            sample_dates,
        ]

        manager = EarningsCalendarManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        results = manager.ingest_all(["AAPL", "BAD", "MSFT"])

        assert results["AAPL"] == 4
        assert results["BAD"] == -1
        assert results["MSFT"] == 4


class TestNextEarningsDate:
    """Tests for next earnings date projection."""

    def test_next_date_projected_from_average_interval(
        self, config: Config, sample_dates: list[date]
    ) -> None:
        """Test next earnings date projection from historical data."""
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": _make_s3_body("AAPL", sample_dates).read.return_value
                    and _make_s3_body("AAPL", sample_dates)
        }
        # Re-do: create properly
        body_mock = _make_s3_body("AAPL", sample_dates)
        mock_s3.get_object.return_value = {"Body": body_mock}

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager.get_next_earnings_date("AAPL")

        # With dates [Jan25, Apr25, Jul31, Nov1], intervals are [91, 97, 93]
        # Average = 93 days. Last date = Nov 1, 2024. Projected = Feb 2, 2025.
        # Since that's past (today is 2026-02-14), it should step forward.
        assert result is not None
        assert result >= date.today()

    def test_next_date_none_when_no_data(self, config: Config) -> None:
        """Test that None is returned when no calendar data exists."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        assert manager.get_next_earnings_date("MISSING") is None

    def test_next_date_returns_future_date_from_data(
        self, config: Config,
    ) -> None:
        """Test that a future date in the data is returned as-is."""
        future = date.today() + timedelta(days=10)
        dates = [date(2024, 7, 31), date(2024, 11, 1), future]

        body_mock = _make_s3_body("AAPL", dates)
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": body_mock}

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager.get_next_earnings_date("AAPL")
        assert result == future

    def test_single_date_uses_default_interval(self, config: Config) -> None:
        """Test that a single historical date uses 90-day default interval."""
        past_date = date.today() - timedelta(days=30)
        dates = [past_date]

        body_mock = _make_s3_body("AAPL", dates)
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": body_mock}

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager.get_next_earnings_date("AAPL")
        assert result is not None
        expected = past_date + timedelta(days=90)
        assert result == expected


class TestDaysUntilEarnings:
    """Tests for days_until_earnings convenience method."""

    def test_positive_days(self, config: Config) -> None:
        """Test days_until_earnings returns positive count for future earnings."""
        future = date.today() + timedelta(days=15)
        dates = [date(2024, 7, 31), date(2024, 11, 1), future]

        body_mock = _make_s3_body("AAPL", dates)
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": body_mock}

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager.days_until_earnings("AAPL")
        assert result == 15

    def test_none_when_no_data(self, config: Config) -> None:
        """Test that None is returned when no calendar data exists."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        assert manager.days_until_earnings("MISSING") is None


class TestStalenessCheck:
    """Tests for earnings calendar staleness checking."""

    def test_stale_when_no_record(self, config: Config) -> None:
        """Test that missing staleness record means stale."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("AAPL") is True

    def test_stale_when_no_updated_at_field(self, config: Config) -> None:
        """Test stale when item exists but has no updated_at."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {"key": {"S": "earnings_staleness_AAPL"}}
        }

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("AAPL") is True

    def test_not_stale_when_recent(self, config: Config) -> None:
        """Test that recently updated earnings data is not stale."""
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "earnings_staleness_AAPL"},
                "updated_at": {"S": recent_time.isoformat()},
            }
        }

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("AAPL") is False

    def test_stale_when_old(self, config: Config) -> None:
        """Test that old earnings data (>24h) is stale."""
        old_time = datetime.now(timezone.utc) - timedelta(
            hours=EARNINGS_STALENESS_HOURS + 1
        )
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "earnings_staleness_AAPL"},
                "updated_at": {"S": old_time.isoformat()},
            }
        }

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("AAPL") is True

    def test_stale_on_dynamodb_error(self, config: Config) -> None:
        """Test that DynamoDB errors default to stale (safe-side)."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "fail"}},
            "GetItem",
        )

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness("AAPL") is True


class TestErrorBranches:
    """Tests for error handling branches."""

    def test_save_to_s3_client_error_raises(
        self, config: Config, sample_dates: list[date]
    ) -> None:
        """Test that S3 ClientError in _save_to_s3 is re-raised."""
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "fail"}},
            "PutObject",
        )

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        with pytest.raises(ClientError):
            manager._save_to_s3("AAPL", sample_dates)

    def test_update_staleness_client_error_raises(
        self, config: Config,
    ) -> None:
        """Test that DynamoDB ClientError in _update_staleness is re-raised."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "fail"}},
            "PutItem",
        )

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        with pytest.raises(ClientError):
            manager._update_staleness("AAPL")

    def test_load_from_s3_non_nosuchkey_error_raises(
        self, config: Config,
    ) -> None:
        """Test that non-NoSuchKey S3 errors are re-raised."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "forbidden"}},
            "GetObject",
        )

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        with pytest.raises(ClientError):
            manager._load_from_s3("AAPL")

    def test_load_from_s3_nosuchkey_returns_empty(
        self, config: Config,
    ) -> None:
        """Test that NoSuchKey returns empty list (not an error)."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        manager = EarningsCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager._load_from_s3("AAPL")
        assert result == []


class TestConstants:
    """Tests for module constants."""

    def test_staleness_threshold_hours(self) -> None:
        """Test that staleness threshold is 24 hours."""
        assert EARNINGS_STALENESS_HOURS == 24
