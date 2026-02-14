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


class EarningsDataProvider(Protocol):
    """Protocol for earnings calendar data providers.

    Implementations fetch historical quarterly statement release dates
    from financial data APIs (e.g., Tiingo Fundamentals, Alpha Vantage).
    """

    @property
    def name(self) -> str:
        """Provider name for logging and error messages."""
        ...

    def get_statement_dates(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        """Fetch historical quarterly statement release dates.

        Args:
            ticker: Stock symbol (e.g., 'AAPL').
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            List of dates when quarterly statements were released,
            sorted ascending. Annual reports are excluded.

        Raises:
            ProviderError: If the provider fails to fetch data.
        """
        ...


class EconomicCalendarProvider(Protocol):
    """Protocol for economic calendar data providers.

    Implementations provide dates of major macro events
    (FOMC meetings, NFP releases, CPI releases) that drive
    the Macro Event Guard for COMMODITY and FOREX assets.
    """

    @property
    def name(self) -> str:
        """Provider name for logging and error messages."""
        ...

    def get_event_dates(self, event_type: str, year: int) -> list[date]:
        """Fetch scheduled dates for a macro event type in a given year.

        Args:
            event_type: Event identifier ('FOMC', 'NFP', or 'CPI').
            year: Calendar year to fetch dates for.

        Returns:
            Sorted list of event dates for the given year.

        Raises:
            ProviderError: If event_type is unknown or year is unsupported.
        """
        ...
