"""Data Provider Protocols.

Defines the interfaces for market data and macro data providers.
"""

from datetime import date
from typing import Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    """Protocol for market data providers.

    All providers (Tiingo, Yahoo, etc.) must implement this interface
    to ensure consistent behavior and easy fallback switching.
    """

    @property
    def name(self) -> str:
        """Provider name for logging and error messages."""
        ...

    def get_daily_candles(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV candles for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'AAPL').
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            DataFrame with columns:
                - date (index): Trading date
                - open: Opening price
                - high: High price
                - low: Low price
                - close: Closing price
                - volume: Trading volume
                - adjusted_close: Adjusted closing price

        Raises:
            ProviderError: If the provider fails to fetch data.
        """
        ...


class MacroDataProvider(Protocol):
    """Protocol for macro/economic data providers (non-OHLCV).

    FRED and similar providers return single-value time series
    (date, value) rather than OHLCV candles.
    """

    @property
    def name(self) -> str:
        """Provider name for logging and error messages."""
        ...

    def get_observations(
        self,
        series_id: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch time series observations for a macro indicator.

        Args:
            series_id: FRED series ID (e.g., 'VIXCLS', 'T10Y2Y').
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            DataFrame with columns:
                - date (index): Observation date
                - value: Observation value (float)

        Raises:
            ProviderError: If the provider fails to fetch data.
        """
        ...


class ProviderError(Exception):
    """Exception raised when a provider fails to fetch data."""

    def __init__(self, provider: str, ticker: str, message: str) -> None:
        """Initialize ProviderError.

        Args:
            provider: Name of the failing provider.
            ticker: Ticker that was being fetched.
            message: Error description.
        """
        self.provider = provider
        self.ticker = ticker
        super().__init__(f"[{provider}] Failed to fetch {ticker}: {message}")
