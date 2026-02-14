"""Tests for TiingoEarningsProvider."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.modules.data.protocols import ProviderError
from src.modules.data.providers.tiingo_earnings import TiingoEarningsProvider


@pytest.fixture
def provider() -> TiingoEarningsProvider:
    """Create a TiingoEarningsProvider instance for testing."""
    return TiingoEarningsProvider(api_key="test-api-key")


@pytest.fixture
def sample_statements_response() -> list[dict[str, object]]:
    """Sample Tiingo Fundamentals statements response."""
    return [
        {
            "date": "2024-01-25T00:00:00.000Z",
            "quarter": 1,
            "year": 2024,
            "statementType": "quarterly",
        },
        {
            "date": "2024-04-25T00:00:00.000Z",
            "quarter": 2,
            "year": 2024,
            "statementType": "quarterly",
        },
        {
            "date": "2024-07-31T00:00:00.000Z",
            "quarter": 3,
            "year": 2024,
            "statementType": "quarterly",
        },
        {
            "date": "2024-11-01T00:00:00.000Z",
            "quarter": 4,
            "year": 2024,
            "statementType": "quarterly",
        },
    ]


class TestTiingoEarningsProvider:
    """Tests for TiingoEarningsProvider."""

    def test_name_property(self, provider: TiingoEarningsProvider) -> None:
        """Test provider name."""
        assert provider.name == "TiingoEarnings"

    @patch("src.modules.data.providers.tiingo_earnings.httpx.Client")
    def test_get_statement_dates_success(
        self,
        mock_client_class: MagicMock,
        provider: TiingoEarningsProvider,
        sample_statements_response: list[dict[str, object]],
    ) -> None:
        """Test successful fetch of quarterly statement dates."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_statements_response
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        dates = provider.get_statement_dates(
            ticker="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert len(dates) == 4
        assert dates[0] == date(2024, 1, 25)
        assert dates[-1] == date(2024, 11, 1)
        assert dates == sorted(dates)

    @patch("src.modules.data.providers.tiingo_earnings.httpx.Client")
    def test_filters_out_annual_reports(
        self,
        mock_client_class: MagicMock,
        provider: TiingoEarningsProvider,
    ) -> None:
        """Test that annual reports (quarter=0) are excluded."""
        data = [
            {"date": "2024-01-25T00:00:00.000Z", "quarter": 1},
            {"date": "2024-03-10T00:00:00.000Z", "quarter": 0},  # annual
            {"date": "2024-04-25T00:00:00.000Z", "quarter": 2},
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = data
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        dates = provider.get_statement_dates(
            ticker="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert len(dates) == 2
        assert date(2024, 3, 10) not in dates

    @patch("src.modules.data.providers.tiingo_earnings.httpx.Client")
    def test_skips_entries_with_missing_quarter(
        self,
        mock_client_class: MagicMock,
        provider: TiingoEarningsProvider,
    ) -> None:
        """Test that entries with no quarter field are skipped."""
        data = [
            {"date": "2024-01-25T00:00:00.000Z", "quarter": 1},
            {"date": "2024-04-25T00:00:00.000Z"},  # no quarter
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = data
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        dates = provider.get_statement_dates(
            ticker="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert len(dates) == 1

    @patch("src.modules.data.providers.tiingo_earnings.httpx.Client")
    def test_skips_entries_with_non_string_date(
        self,
        mock_client_class: MagicMock,
        provider: TiingoEarningsProvider,
    ) -> None:
        """Test that entries with non-string date are skipped."""
        data = [
            {"date": "2024-01-25T00:00:00.000Z", "quarter": 1},
            {"date": 12345, "quarter": 2},  # numeric date
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = data
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        dates = provider.get_statement_dates(
            ticker="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert len(dates) == 1

    @patch("src.modules.data.providers.tiingo_earnings.httpx.Client")
    def test_skips_unparseable_date_string(
        self,
        mock_client_class: MagicMock,
        provider: TiingoEarningsProvider,
    ) -> None:
        """Test that unparseable date strings are skipped with a warning."""
        data = [
            {"date": "not-a-date", "quarter": 1},
            {"date": "2024-04-25T00:00:00.000Z", "quarter": 2},
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = data
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        dates = provider.get_statement_dates(
            ticker="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert len(dates) == 1
        assert dates[0] == date(2024, 4, 25)

    @patch("src.modules.data.providers.tiingo_earnings.httpx.Client")
    def test_empty_response_raises_provider_error(
        self,
        mock_client_class: MagicMock,
        provider: TiingoEarningsProvider,
    ) -> None:
        """Test that empty API response raises ProviderError."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError) as exc_info:
            provider.get_statement_dates(
                ticker="INVALID",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )

        assert "No data returned" in str(exc_info.value)

    @patch("src.modules.data.providers.tiingo_earnings.httpx.Client")
    def test_http_error_raises_provider_error(
        self,
        mock_client_class: MagicMock,
        provider: TiingoEarningsProvider,
    ) -> None:
        """Test that HTTP errors raise ProviderError."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError) as exc_info:
            provider.get_statement_dates(
                ticker="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )

        assert "TiingoEarnings" in str(exc_info.value)

    @patch("src.modules.data.providers.tiingo_earnings.httpx.Client")
    def test_request_error_raises_provider_error(
        self,
        mock_client_class: MagicMock,
        provider: TiingoEarningsProvider,
    ) -> None:
        """Test that network/connection errors raise ProviderError."""
        import httpx

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError(
            "Connection timeout",
            request=MagicMock(),
        )
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError) as exc_info:
            provider.get_statement_dates(
                ticker="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )

        assert "TiingoEarnings" in str(exc_info.value)
