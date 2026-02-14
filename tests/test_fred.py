"""Tests for FRED data provider."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.modules.data.protocols import ProviderError
from src.modules.data.providers.fred import FredProvider


@pytest.fixture
def provider() -> FredProvider:
    """Create a FredProvider instance."""
    return FredProvider(api_key="test-key")


SAMPLE_FRED_RESPONSE = {
    "observations": [
        {"date": "2024-01-02", "value": "16.50"},
        {"date": "2024-01-03", "value": "17.20"},
        {"date": "2024-01-04", "value": "15.80"},
    ]
}


class TestFredProvider:
    """Tests for FredProvider."""

    def test_name_property(self, provider: FredProvider) -> None:
        """Test provider name is FRED."""
        assert provider.name == "FRED"

    @patch("src.modules.data.providers.fred.httpx.Client")
    def test_get_observations_success(
        self, mock_client_class: MagicMock, provider: FredProvider
    ) -> None:
        """Test successful observation fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_FRED_RESPONSE
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        df = provider.get_observations("VIXCLS", date(2024, 1, 2), date(2024, 1, 4))

        assert len(df) == 3
        assert list(df.columns) == ["value"]
        assert df.iloc[0]["value"] == 16.50
        assert df.iloc[2]["value"] == 15.80

    @patch("src.modules.data.providers.fred.httpx.Client")
    def test_missing_values_are_skipped(
        self, mock_client_class: MagicMock, provider: FredProvider
    ) -> None:
        """Test that FRED's '.' missing values are dropped."""
        response_with_missing = {
            "observations": [
                {"date": "2024-01-02", "value": "16.50"},
                {"date": "2024-01-03", "value": "."},
                {"date": "2024-01-04", "value": "15.80"},
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_with_missing
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        df = provider.get_observations("VIXCLS", date(2024, 1, 2), date(2024, 1, 4))

        assert len(df) == 2
        assert date(2024, 1, 3) not in df.index

    @patch("src.modules.data.providers.fred.httpx.Client")
    def test_all_missing_values_returns_empty_df(
        self, mock_client_class: MagicMock, provider: FredProvider
    ) -> None:
        """Test that all-missing observations returns empty DataFrame."""
        response_all_missing = {
            "observations": [
                {"date": "2024-01-02", "value": "."},
                {"date": "2024-01-03", "value": "."},
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_all_missing
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        df = provider.get_observations("VIXCLS", date(2024, 1, 2), date(2024, 1, 3))

        assert df.empty

    @patch("src.modules.data.providers.fred.httpx.Client")
    def test_empty_observations_raises_provider_error(
        self, mock_client_class: MagicMock, provider: FredProvider
    ) -> None:
        """Test that empty observations list raises ProviderError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"observations": []}
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError, match="No observations returned"):
            provider.get_observations("VIXCLS", date(2024, 1, 2), date(2024, 1, 4))

    @patch("src.modules.data.providers.fred.httpx.Client")
    def test_http_error_raises_provider_error(
        self, mock_client_class: MagicMock, provider: FredProvider
    ) -> None:
        """Test that HTTP errors raise ProviderError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError, match="HTTP 400"):
            provider.get_observations("VIXCLS", date(2024, 1, 2), date(2024, 1, 4))

    @patch("src.modules.data.providers.fred.httpx.Client")
    def test_request_error_raises_provider_error(
        self, mock_client_class: MagicMock, provider: FredProvider
    ) -> None:
        """Test that network errors raise ProviderError."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Timeout")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError, match="Timeout"):
            provider.get_observations("VIXCLS", date(2024, 1, 2), date(2024, 1, 4))

    @patch("src.modules.data.providers.fred.httpx.Client")
    def test_data_sorted_by_date(
        self, mock_client_class: MagicMock, provider: FredProvider
    ) -> None:
        """Test that returned data is sorted by date ascending."""
        reversed_response = {
            "observations": list(reversed(SAMPLE_FRED_RESPONSE["observations"]))
        }

        mock_response = MagicMock()
        mock_response.json.return_value = reversed_response
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        df = provider.get_observations("VIXCLS", date(2024, 1, 2), date(2024, 1, 4))

        dates = list(df.index)
        assert dates == sorted(dates)

    def test_normalize_skips_invalid_values(self, provider: FredProvider) -> None:
        """Test that _normalize skips non-numeric values."""
        observations = [
            {"date": "2024-01-02", "value": "16.50"},
            {"date": "2024-01-03", "value": "invalid"},
            {"date": "2024-01-04", "value": "15.80"},
        ]

        df = provider._normalize(observations)

        assert len(df) == 2

    def test_normalize_skips_missing_keys(self, provider: FredProvider) -> None:
        """Test that _normalize skips observations missing keys."""
        observations = [
            {"date": "2024-01-02", "value": "16.50"},
            {"date": "2024-01-03"},  # Missing value key
        ]

        df = provider._normalize(observations)

        assert len(df) == 1
