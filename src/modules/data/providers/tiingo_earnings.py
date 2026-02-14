"""Tiingo Earnings Calendar Provider.

Fetches historical quarterly statement release dates from the
Tiingo Fundamentals API to support the Event Guard (earnings blackout).
"""

from datetime import date

import httpx

from src.modules.data.protocols import ProviderError
from src.shared.logger import get_logger

logger = get_logger(__name__)


class TiingoEarningsProvider:
    """Tiingo Fundamentals earnings calendar provider.

    Uses the Tiingo Fundamentals statements endpoint to fetch
    quarterly statement release dates for equity assets.
    """

    def __init__(self, api_key: str) -> None:
        """Initialize TiingoEarningsProvider.

        Args:
            api_key: Tiingo API key.
        """
        self._api_key = api_key
        self._base_url = "https://api.tiingo.com/tiingo/fundamentals"

    @property
    def name(self) -> str:
        """Provider name."""
        return "TiingoEarnings"

    def get_statement_dates(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        """Fetch quarterly statement release dates from Tiingo Fundamentals.

        Args:
            ticker: Stock symbol (e.g., 'AAPL').
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            Sorted list of dates when quarterly statements were released.
            Annual reports (quarter=0) are excluded.

        Raises:
            ProviderError: If the API call fails or returns no data.
        """
        logger.info(
            "Fetching earnings dates from Tiingo",
            extra={
                "ticker": ticker,
                "start": str(start_date),
                "end": str(end_date),
            },
        )

        url = f"{self._base_url}/{ticker}/statements"
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "token": self._api_key,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data: list[dict[str, object]] = response.json()
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

        return self._extract_quarterly_dates(data, ticker)

    def _extract_quarterly_dates(
        self,
        data: list[dict[str, object]],
        ticker: str,
    ) -> list[date]:
        """Extract quarterly statement dates from raw API response.

        Args:
            data: Raw Tiingo Fundamentals API response.
            ticker: Ticker symbol for logging.

        Returns:
            Sorted list of quarterly statement release dates.
        """
        quarterly_dates: list[date] = []

        for statement in data:
            quarter = statement.get("quarter")
            # Skip annual reports (quarter == 0 or missing)
            if not quarter or quarter == 0:
                continue

            date_str = statement.get("date")
            if not isinstance(date_str, str):
                continue

            try:
                # Tiingo returns ISO datetime strings
                parsed = date.fromisoformat(date_str[:10])
                quarterly_dates.append(parsed)
            except (ValueError, IndexError):
                logger.warning(
                    f"Skipping unparseable date for {ticker}: {date_str}"
                )

        quarterly_dates.sort()
        return quarterly_dates
