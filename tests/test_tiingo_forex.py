"""Tests for Tiingo Forex data provider."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.modules.data.protocols import ProviderError
from src.modules.data.providers.tiingo_forex import TiingoForexProvider


@pytest.fixture
def provider() -> TiingoForexProvider:
    """Create a TiingoForexProvider instance."""
    return TiingoForexProvider(api_key="test-key")


SAMPLE_FOREX_RESPONSE = [
    {
        "date": "2024-01-02T00:00:00+00:00",
        "open": 2060.50,
        "high": 2075.30,
        "low": 2055.10,
        "close": 2070.00,
    },
    {
        "date": "2024-01-03T00:00:00+00:00",
        "open": 2070.00,
        "high": 2082.40,
        "low": 2065.00,
        "close": 2078.50,
    },
]


class TestTiingoForexProvider:
    """Tests for TiingoForexProvider."""

    def test_name_property(self, provider: TiingoForexProvider) -> None:
        """Test provider name is TiingoForex."""
        assert provider.name == "TiingoForex"

    @patch("src.modules.data.providers.tiingo_forex.httpx.Client")
    def test_get_daily_candles_success(
        self, mock_client_class: MagicMock, provider: TiingoForexProvider
    ) -> None:
        """Test successful forex data fetch and normalization."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_FOREX_RESPONSE
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        df = provider.get_daily_candles("XAUUSD", date(2024, 1, 2), date(2024, 1, 3))

        assert len(df) == 2
        assert list(df.columns) == [
            "open", "high", "low", "close", "volume", "adjusted_close",
        ]
        # Volume should be 0 for forex
        assert (df["volume"] == 0).all()
        # adjusted_close should equal close
        assert (df["adjusted_close"] == df["close"]).all()
        # Verify actual values
        assert df.iloc[0]["close"] == 2070.00
        assert df.iloc[1]["close"] == 2078.50

    @patch("src.modules.data.providers.tiingo_forex.httpx.Client")
    def test_ticker_is_lowercased_in_url(
        self, mock_client_class: MagicMock, provider: TiingoForexProvider
    ) -> None:
        """Test that ticker is lowercased when building the API URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_FOREX_RESPONSE
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        provider.get_daily_candles("XAUUSD", date(2024, 1, 2), date(2024, 1, 3))

        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert "xauusd" in url
        assert "XAUUSD" not in url

    @patch("src.modules.data.providers.tiingo_forex.httpx.Client")
    def test_resample_freq_is_1day(
        self, mock_client_class: MagicMock, provider: TiingoForexProvider
    ) -> None:
        """Test that resampleFreq=1day is sent as a query parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_FOREX_RESPONSE
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        provider.get_daily_candles("XAUUSD", date(2024, 1, 2), date(2024, 1, 3))

        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["params"]["resampleFreq"] == "1day"

    @patch("src.modules.data.providers.tiingo_forex.httpx.Client")
    def test_empty_response_raises_provider_error(
        self, mock_client_class: MagicMock, provider: TiingoForexProvider
    ) -> None:
        """Test that empty response raises ProviderError."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError, match="No data returned"):
            provider.get_daily_candles("XAUUSD", date(2024, 1, 2), date(2024, 1, 3))

    @patch("src.modules.data.providers.tiingo_forex.httpx.Client")
    def test_http_error_raises_provider_error(
        self, mock_client_class: MagicMock, provider: TiingoForexProvider
    ) -> None:
        """Test that HTTP errors raise ProviderError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError, match="HTTP 404"):
            provider.get_daily_candles("XAUUSD", date(2024, 1, 2), date(2024, 1, 3))

    @patch("src.modules.data.providers.tiingo_forex.httpx.Client")
    def test_request_error_raises_provider_error(
        self, mock_client_class: MagicMock, provider: TiingoForexProvider
    ) -> None:
        """Test that network errors raise ProviderError."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ProviderError, match="Connection failed"):
            provider.get_daily_candles("XAUUSD", date(2024, 1, 2), date(2024, 1, 3))

    @patch("src.modules.data.providers.tiingo_forex.httpx.Client")
    def test_data_sorted_by_date(
        self, mock_client_class: MagicMock, provider: TiingoForexProvider
    ) -> None:
        """Test that returned data is sorted by date ascending."""
        reversed_data = list(reversed(SAMPLE_FOREX_RESPONSE))

        mock_response = MagicMock()
        mock_response.json.return_value = reversed_data
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        df = provider.get_daily_candles("XAUUSD", date(2024, 1, 2), date(2024, 1, 3))

        dates = list(df.index)
        assert dates == sorted(dates)

    def test_normalize_volume_zero(self, provider: TiingoForexProvider) -> None:
        """Test that _normalize sets volume to 0 for all rows."""
        df = provider._normalize(SAMPLE_FOREX_RESPONSE)
        assert (df["volume"] == 0).all()

    def test_normalize_adjusted_close_equals_close(
        self, provider: TiingoForexProvider
    ) -> None:
        """Test that _normalize sets adjusted_close = close."""
        df = provider._normalize(SAMPLE_FOREX_RESPONSE)
        assert (df["adjusted_close"] == df["close"]).all()
