"""Tiingo Market Data Provider.

Primary data source for high-quality OHLCV data with official API access.
"""

from datetime import date

import httpx
import pandas as pd

from src.modules.data.protocols import ProviderError
from src.shared.logger import get_logger

logger = get_logger(__name__)


class TiingoProvider:
    """Tiingo market data provider (Primary).

    Uses the official Tiingo API for reliable, high-quality market data.
    Free tier allows 500 requests/hour.
    """

    def __init__(self, api_key: str) -> None:
        """Initialize TiingoProvider.

        Args:
            api_key: Tiingo API key.
        """
        self._api_key = api_key
        self._base_url = "https://api.tiingo.com/tiingo/daily"

    @property
    def name(self) -> str:
        """Provider name."""
        return "Tiingo"

    def get_daily_candles(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV candles from Tiingo.

        Args:
            ticker: Stock symbol (e.g., 'AAPL').
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            Normalized DataFrame with OHLCV data.

        Raises:
            ProviderError: If Tiingo API fails.
        """
        logger.info(
            "Fetching data from Tiingo",
            extra={"ticker": ticker, "start": str(start_date), "end": str(end_date)},
        )

        url = f"{self._base_url}/{ticker}/prices"
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
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
        """Normalize Tiingo response to standard schema.

        Args:
            data: Raw Tiingo API response.

        Returns:
            Normalized DataFrame.
        """
        df = pd.DataFrame(data)

        # Rename columns to standard schema
        df = df.rename(
            columns={
                "adjClose": "adjusted_close",
                "adjHigh": "adjusted_high",
                "adjLow": "adjusted_low",
                "adjOpen": "adjusted_open",
                "adjVolume": "adjusted_volume",
            }
        )

        # Parse date and set as index
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.set_index("date")

        # Select standard columns
        standard_cols = ["open", "high", "low", "close", "volume", "adjusted_close"]
        available_cols = [col for col in standard_cols if col in df.columns]

        return df[available_cols].sort_index()
