"""Tiingo Forex Data Provider.

Provides daily OHLC data for forex instruments (XAU/USD, XAG/USD, etc.)
via Tiingo's Forex API. Forex data has no centralized volume.
"""

from datetime import date

import httpx
import pandas as pd

from src.modules.data.protocols import ProviderError
from src.shared.logger import get_logger

logger = get_logger(__name__)


class TiingoForexProvider:
    """Tiingo Forex data provider for precious metals and currency pairs.

    Uses the Tiingo Forex API endpoint which returns daily bars
    from tier-1 bank pricing. Forex instruments have no centralized
    volume, so volume is set to 0 and adjusted_close equals close.
    """

    def __init__(self, api_key: str) -> None:
        """Initialize TiingoForexProvider.

        Args:
            api_key: Tiingo API key.
        """
        self._api_key = api_key
        self._base_url = "https://api.tiingo.com/tiingo/fx"

    @property
    def name(self) -> str:
        """Provider name."""
        return "TiingoForex"

    def get_daily_candles(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch daily OHLC data from Tiingo Forex API.

        Args:
            ticker: Forex pair (e.g., 'XAUUSD', 'XAGUSD').
                Automatically lowercased for the Tiingo API.
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            Normalized DataFrame with OHLCV schema.
            Volume is 0 (no centralized forex volume).
            adjusted_close equals close (no corporate actions).

        Raises:
            ProviderError: If the Tiingo Forex API fails.
        """
        logger.info(
            "Fetching forex data from Tiingo",
            extra={"ticker": ticker, "start": str(start_date), "end": str(end_date)},
        )

        url = f"{self._base_url}/{ticker.lower()}/prices"
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "resampleFreq": "1day",
            "token": self._api_key,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                self.name,
                ticker,
                f"HTTP {e.response.status_code}: {e.response.text}",
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(self.name, ticker, str(e)) from e

        if not data:
            raise ProviderError(self.name, ticker, "No data returned")

        return self._normalize(data)

    def _normalize(self, data: list[dict[str, object]]) -> pd.DataFrame:
        """Normalize Tiingo Forex response to standard OHLCV schema.

        Tiingo Forex returns: date, open, high, low, close.
        We add volume=0 and adjusted_close=close to match the
        MarketDataProvider protocol.

        Args:
            data: Raw Tiingo Forex API response.

        Returns:
            Normalized DataFrame with standard columns.
        """
        df = pd.DataFrame(data)

        # Parse date and set as index
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.set_index("date")

        # Forex has no centralized volume
        df["volume"] = 0

        # No corporate actions for forex
        df["adjusted_close"] = df["close"]

        # Select standard columns in protocol order
        standard_cols = ["open", "high", "low", "close", "volume", "adjusted_close"]

        return df[standard_cols].sort_index()
