"""Tests for EconomicCalendarManager."""

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from src.modules.data.economic_calendar_manager import (
    ECONOMIC_STALENESS_HOURS,
    EconomicCalendarManager,
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
        tiingo_api_key="",
        fred_api_key="",
        telegram_bot_token="",
        telegram_chat_id="",
        environment="test",
    )


@pytest.fixture
def sample_dates() -> dict[str, list[date]]:
    """Sample event dates for testing."""
    return {
        "FOMC": [date(2026, 1, 28), date(2026, 3, 18)],
        "NFP": [date(2026, 1, 2), date(2026, 2, 6)],
        "CPI": [date(2026, 1, 14), date(2026, 2, 11)],
    }


def _make_s3_body(year: int, dates: dict[str, list[date]]) -> MagicMock:
    """Helper to create a mock S3 response body."""
    payload_data: dict[str, object] = {"year": year}
    for event_type, event_dates in dates.items():
        payload_data[event_type.lower()] = [d.isoformat() for d in event_dates]
    payload = json.dumps(payload_data)
    body = MagicMock()
    body.read.return_value = payload.encode("utf-8")
    return body


def _make_provider(dates: dict[str, list[date]]) -> MagicMock:
    """Create a mock provider that returns given dates."""
    mock = MagicMock()

    def side_effect(event_type: str, year: int) -> list[date]:
        return dates.get(event_type, [])

    mock.get_event_dates.side_effect = side_effect
    return mock


class TestIngestion:
    """Tests for economic calendar ingestion."""

    def test_ingest_success(
        self, config: Config, sample_dates: dict[str, list[date]]
    ) -> None:
        """Test successful ingestion of all event types."""
        provider = _make_provider(sample_dates)
        manager = EconomicCalendarManager(
            config=config,
            provider=provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        results = manager.ingest(2026)

        assert results["FOMC"] == 2
        assert results["NFP"] == 2
        assert results["CPI"] == 2
        assert provider.get_event_dates.call_count == 3

    def test_ingest_saves_to_correct_s3_path(
        self, config: Config, sample_dates: dict[str, list[date]]
    ) -> None:
        """Test that calendar is saved to economic_calendar/calendar_{year}.json."""
        provider = _make_provider(sample_dates)
        mock_s3 = MagicMock()

        manager = EconomicCalendarManager(
            config=config,
            provider=provider,
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        manager.ingest(2026)

        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Key"] == "economic_calendar/calendar_2026.json"
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["ContentType"] == "application/json"

        body = json.loads(call_kwargs["Body"].decode("utf-8"))
        assert body["year"] == 2026
        assert len(body["fomc"]) == 2
        assert len(body["nfp"]) == 2
        assert len(body["cpi"]) == 2

    def test_ingest_updates_staleness(
        self, config: Config, sample_dates: dict[str, list[date]]
    ) -> None:
        """Test that staleness timestamp is updated after ingestion."""
        provider = _make_provider(sample_dates)
        mock_dynamodb = MagicMock()

        manager = EconomicCalendarManager(
            config=config,
            provider=provider,
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        manager.ingest(2026)

        mock_dynamodb.put_item.assert_called_once()
        put_kwargs = mock_dynamodb.put_item.call_args[1]
        assert put_kwargs["Item"]["key"]["S"] == "economic_calendar_staleness"
        assert "updated_at" in put_kwargs["Item"]

    def test_ingest_partial_failure(self, config: Config) -> None:
        """Test ingestion with one event type failing."""
        mock_provider = MagicMock()
        mock_provider.get_event_dates.side_effect = [
            [date(2026, 1, 28)],  # FOMC ok
            Exception("NFP compute error"),  # NFP fails
            [date(2026, 1, 14)],  # CPI ok
        ]

        manager = EconomicCalendarManager(
            config=config,
            provider=mock_provider,
            s3_client=MagicMock(),
            dynamodb_client=MagicMock(),
        )

        results = manager.ingest(2026)

        assert results["FOMC"] == 1
        assert results["NFP"] == -1
        assert results["CPI"] == 1


class TestNextMacroEventDate:
    """Tests for next macro event date querying."""

    def test_returns_nearest_future_date(
        self, config: Config,
    ) -> None:
        """Test that the nearest future event date is returned."""
        tomorrow = date.today() + timedelta(days=1)
        next_week = date.today() + timedelta(days=7)
        dates = {"FOMC": [tomorrow], "NFP": [next_week], "CPI": []}

        body_mock = _make_s3_body(date.today().year, dates)
        mock_s3 = MagicMock()
        # Return data for current year, empty for next year
        next_year_body = _make_s3_body(
            date.today().year + 1,
            {"FOMC": [], "NFP": [], "CPI": []},
        )
        mock_s3.get_object.side_effect = [
            {"Body": body_mock},
            {"Body": next_year_body},
        ]

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager.get_next_macro_event_date()
        assert result == tomorrow

    def test_returns_none_when_no_data(self, config: Config) -> None:
        """Test that None is returned when no calendar data exists."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        assert manager.get_next_macro_event_date() is None

    def test_returns_none_when_all_dates_in_past(
        self, config: Config,
    ) -> None:
        """Test None when all stored dates are in the past."""
        past_dates = {
            "FOMC": [date(2020, 1, 1)],
            "NFP": [date(2020, 2, 1)],
            "CPI": [],
        }
        body_mock = _make_s3_body(date.today().year, past_dates)
        next_year_body = _make_s3_body(
            date.today().year + 1,
            {"FOMC": [], "NFP": [], "CPI": []},
        )
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = [
            {"Body": body_mock},
            {"Body": next_year_body},
        ]

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        assert manager.get_next_macro_event_date() is None

    def test_loads_next_year_when_near_year_end(
        self, config: Config,
    ) -> None:
        """Test that next year's dates are included in search."""
        # Put only a future date in the next year's calendar
        next_year = date.today().year + 1
        future_date = date(next_year, 3, 18)

        current_year_body = _make_s3_body(
            date.today().year,
            {"FOMC": [], "NFP": [], "CPI": []},
        )
        next_year_body = _make_s3_body(
            next_year,
            {"FOMC": [future_date], "NFP": [], "CPI": []},
        )
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = [
            {"Body": current_year_body},
            {"Body": next_year_body},
        ]

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager.get_next_macro_event_date()
        assert result == future_date


class TestDaysUntilMacroEvent:
    """Tests for days_until_macro_event convenience method."""

    def test_positive_days(self, config: Config) -> None:
        """Test days_until_macro_event returns correct positive count."""
        future = date.today() + timedelta(days=5)
        dates = {"FOMC": [future], "NFP": [], "CPI": []}

        body_mock = _make_s3_body(date.today().year, dates)
        next_year_body = _make_s3_body(
            date.today().year + 1,
            {"FOMC": [], "NFP": [], "CPI": []},
        )
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = [
            {"Body": body_mock},
            {"Body": next_year_body},
        ]

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager.days_until_macro_event()
        assert result == 5

    def test_none_when_no_data(self, config: Config) -> None:
        """Test that None is returned when no calendar data exists."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        assert manager.days_until_macro_event() is None


class TestStalenessCheck:
    """Tests for economic calendar staleness checking."""

    def test_stale_when_no_record(self, config: Config) -> None:
        """Test that missing staleness record means stale."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness() is True

    def test_stale_when_no_updated_at_field(self, config: Config) -> None:
        """Test stale when item exists but has no updated_at."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {"key": {"S": "economic_calendar_staleness"}}
        }

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness() is True

    def test_not_stale_when_recent(self, config: Config) -> None:
        """Test that recently updated data is not stale."""
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "economic_calendar_staleness"},
                "updated_at": {"S": recent_time.isoformat()},
            }
        }

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness() is False

    def test_stale_when_old(self, config: Config) -> None:
        """Test that old data (>24h) is stale."""
        old_time = datetime.now(timezone.utc) - timedelta(
            hours=ECONOMIC_STALENESS_HOURS + 1
        )
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "economic_calendar_staleness"},
                "updated_at": {"S": old_time.isoformat()},
            }
        }

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness() is True

    def test_stale_on_dynamodb_error(self, config: Config) -> None:
        """Test that DynamoDB errors default to stale (safe-side)."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "fail"}},
            "GetItem",
        )

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        assert manager.check_staleness() is True


class TestErrorBranches:
    """Tests for error handling branches."""

    def test_save_to_s3_client_error_raises(self, config: Config) -> None:
        """Test that S3 ClientError in _save_to_s3 is re-raised."""
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "fail"}},
            "PutObject",
        )

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        with pytest.raises(ClientError):
            manager._save_to_s3(2026, {"fomc": [], "nfp": [], "cpi": []})

    def test_update_staleness_client_error_raises(
        self, config: Config
    ) -> None:
        """Test that DynamoDB ClientError in _update_staleness is re-raised."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "fail"}},
            "PutItem",
        )

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=MagicMock(),
            dynamodb_client=mock_dynamodb,
        )

        with pytest.raises(ClientError):
            manager._update_staleness()

    def test_load_from_s3_non_nosuchkey_error_raises(
        self, config: Config
    ) -> None:
        """Test that non-NoSuchKey S3 errors are re-raised."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "forbidden"}},
            "GetObject",
        )

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        with pytest.raises(ClientError):
            manager._load_from_s3(2026)

    def test_load_from_s3_nosuchkey_returns_empty(
        self, config: Config
    ) -> None:
        """Test that NoSuchKey returns empty list (not an error)."""
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        manager = EconomicCalendarManager(
            config=config,
            provider=MagicMock(),
            s3_client=mock_s3,
            dynamodb_client=MagicMock(),
        )

        result = manager._load_from_s3(2026)
        assert result == []


class TestConstants:
    """Tests for module constants."""

    def test_staleness_threshold_hours(self) -> None:
        """Test that staleness threshold is 24 hours."""
        assert ECONOMIC_STALENESS_HOURS == 24
