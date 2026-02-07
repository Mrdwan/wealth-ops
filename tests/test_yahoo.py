"""Tests for Yahoo Finance market data provider."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.modules.data.protocols import ProviderError
from src.modules.data.providers.yahoo import YahooProvider


@pytest.fixture
def provider() -> YahooProvider:
    """Create a YahooProvider instance for testing."""
    return YahooProvider()


@pytest.fixture
def sample_yfinance_df() -> pd.DataFrame:
    """Sample yfinance DataFrame."""
    data = {
        "Open": [150.0, 154.0],
        "High": [155.0, 158.0],
        "Low": [149.0, 153.0],
        "Close": [154.0, 157.0],
        "Volume": [1000000, 1100000],
        "Adj Close": [154.0, 157.0],
    }
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(data, index=index)


class TestYahooProvider:
    """Tests for YahooProvider."""

    def test_name_property(self, provider: YahooProvider) -> None:
        """Test provider name."""
        assert provider.name == "Yahoo"

    @patch("src.modules.data.providers.yahoo.yf.Ticker")
    def test_get_daily_candles_success(
        self,
        mock_ticker_class: MagicMock,
        provider: YahooProvider,
        sample_yfinance_df: pd.DataFrame,
    ) -> None:
        """Test successful data fetch."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_df
        mock_ticker_class.return_value = mock_ticker

        df = provider.get_daily_candles(
            ticker="AAPL",
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 3),
        )

        assert len(df) == 2
        assert "close" in df.columns
        assert "adjusted_close" in df.columns
        assert df.iloc[0]["close"] == 154.0

    @patch("src.modules.data.providers.yahoo.yf.Ticker")
    def test_get_daily_candles_empty_response(
        self,
        mock_ticker_class: MagicMock,
        provider: YahooProvider,
    ) -> None:
        """Test empty response raises ProviderError."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        with pytest.raises(ProviderError) as exc_info:
            provider.get_daily_candles(
                ticker="INVALID",
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 3),
            )

        assert "No data returned" in str(exc_info.value)

    @patch("src.modules.data.providers.yahoo.yf.Ticker")
    def test_get_daily_candles_exception(
        self,
        mock_ticker_class: MagicMock,
        provider: YahooProvider,
    ) -> None:
        """Test generic exception raises ProviderError."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("Network error")
        mock_ticker_class.return_value = mock_ticker

        with pytest.raises(ProviderError) as exc_info:
            provider.get_daily_candles(
                ticker="AAPL",
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 3),
            )

        assert "Yahoo" in str(exc_info.value)
        assert "Network error" in str(exc_info.value)
